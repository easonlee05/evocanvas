/**
 * @file Sidebar.jsx
 * @description EvoCanvas 侧边栏组件。保留最小导航与最近会话历史，
 * 不再承载 EvoLoop 旧版任务大厅、知识库、法则审核等产品入口。
 */

import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate, useParams } from 'react-router-dom';
import { MessageSquarePlus, Archive, Settings, ChevronRight, LayoutDashboard } from 'lucide-react';
import { apiGet, apiDelete } from '../../api';
import { flattenConversationGroups } from './sidebarHistory';
import './sidebar.css';

/**
 * 侧边栏主导航项配置
 * @type {Array<{icon: React.ReactNode, label: string, path: string, primary?: boolean, badge?: boolean|string}>}
 */
const navItems = [
  { icon: <MessageSquarePlus size={15} />, label: '新建对话', path: '/', primary: true },
  { icon: <LayoutDashboard size={15} />, label: '示例工作台', path: '/workspace/demo' },
];

/**
 * Sidebar 侧边栏组件
 * @component
 */
export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  // 从 URL 参数中获取当前选中的 activeTaskId 以高亮显示最近对话项
  const { id: activeTaskId } = useParams();
  
  // 对话历史分类状态：今天、昨天、更早
  const [today, setToday] = useState([]);
  const [yesterday, setYesterday] = useState([]);
  const [older, setOlder] = useState([]);
  const [historyError, setHistoryError] = useState(false);
  
  // 将按时间分好的对话历史，扁平化为带分组标签的数组供 JSX 渲染使用
  const historyItems = flattenConversationGroups({ today, yesterday, older });

  /**
   * 拉取最近对话/任务历史列表
   */
  const fetchChats = () => {
    apiGet('/api/conversations/recent', null).then(data => {
      if (!data) {
        setHistoryError(true);
        setToday([]);
        setYesterday([]);
        setOlder([]);
        return;
      }
      setHistoryError(false);
      setToday(data.today || []);
      setYesterday(data.yesterday || []);
      setOlder(data.older || []);
    });
  };

  // 当页面路由路径 (location.pathname) 发生改变时，自动重新加载最近对话历史
  useEffect(() => {
    fetchChats();
  }, [location.pathname]);

  /**
   * 删除/归档任务
   * @param {React.MouseEvent} e - 事件对象
   * @param {string} id - 任务 ID
   */
  const handleDeleteTask = async (e, id) => {
    // 阻止事件冒泡，防止触发外层 chat-item 的 onClick 路由跳转
    e.stopPropagation();
    await apiDelete(`/api/tasks/${id}`);
    fetchChats();
  };

  return (
    <aside className="sidebar">
      {/* Logo 区域 */}
      <div className="sidebar-logo">
        <div className="logo-sq">E</div>
        <span className="logo-text">EvoCanvas</span>
      </div>

      {/* 主导航链接列表 */}
      <nav className="sidebar-nav">
        {navItems.map((item, i) => (
          <NavLink
            key={i}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}${item.primary ? ' nav-primary' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
            {item.badge === true ? (
              <span className="nav-badge-dot"></span>
            ) : item.badge ? (
              <span className="nav-badge">{item.badge}</span>
            ) : null}
          </NavLink>
        ))}
      </nav>

      {/* 最近对话历史区域 */}
      <div className="sidebar-section">
        <div className="section-row">
          <span className="section-label">最近对话</span>
          <ChevronRight size={12} className="section-arrow" />
        </div>
        <div className="sidebar-history-scroll">
          {historyError && (
            <div className="chat-empty">任务历史暂时无法加载</div>
          )}
          {!historyError && historyItems.length === 0 && (
            <div className="chat-empty">暂无任务历史</div>
          )}
          {/* 循环渲染历史项，可以是时间分组标题(type === 'group')，也可以是具体的对话项 */}
          {!historyError && historyItems.map((entry, index) => entry.type === 'group' ? (
            <div key={`${entry.label}-${index}`} className="chat-group-label">{entry.label}</div>
          ) : (
            <div
              key={entry.id}
              className={`chat-item${entry.id === activeTaskId ? ' active' : ''}`}
              onClick={() => navigate(`/workspace/${entry.id}`)}
            >
              <span className="chat-label">{entry.label}</span>
              <span className="chat-time">{entry.time}</span>
              <div className="chat-actions">
                <button className="chat-action-btn" onClick={(e) => handleDeleteTask(e, entry.id)} title="归档任务">
                  <Archive size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部用户信息栏 */}
      <div className="sidebar-footer">
        <div className="user-row">
          <div className="user-av">E</div>
          <span className="user-name">Eason</span>
          <Settings size={13} className="user-settings" />
        </div>
      </div>
    </aside>
  );
}
