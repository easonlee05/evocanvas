/**
 * @file index.jsx
 * @description 归档与回收站管理页面组件。用户可以在此查看和管理已归档的任务、已删除的材料文件，包含：
 *   - 页签切换：归档任务 (tasks) 与已删文件 (files)。
 *   - 列表项的多选/单选控制，支持批量恢复、批量彻底/永久删除。
 *   - 调用对应的后端 API 接口进行业务操作，并采用状态集合进行前端的乐观状态过滤。
 */

import React, { useEffect, useState } from 'react';
import { Trash2, RotateCcw, AlertTriangle, FileText, FolderOpen, Archive } from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../../api';
import './recycle-bin.css';

/**
 * 初始静态演示回收站条目列表数据
 * @type {Array<{id: number, name: string, type: 'doc'|'img'|'task', size: string, deletedAt: string, deletedBy: string}>}
 */
const items = [
  { id: 1, name: '旧版产品需求文档 v1.0.md', type: 'doc', size: '32 KB', deletedAt: '今天 09:20', deletedBy: 'PM Agent' },
  { id: 2, name: '废弃架构方案草稿.md', type: 'doc', size: '18 KB', deletedAt: '昨天 16:30', deletedBy: 'Tech Agent' },
  { id: 3, name: '测试用例临时文件.md', type: 'doc', size: '8 KB', deletedAt: '昨天 14:10', deletedBy: 'QA Agent' },
  { id: 4, name: '竞品分析初稿（未完成）.md', type: 'doc', size: '22 KB', deletedAt: '3 天前', deletedBy: 'Expert' },
  { id: 5, name: '旧版系统架构图.png', type: 'img', size: '980 KB', deletedAt: '5 天前', deletedBy: 'Tech Agent' },
];

/**
 * 不同类型回收项的 Lucide 图标主题配置
 * @type {Object.<string, React.ReactNode>}
 */
const typeIcon = { doc: <FileText size={15} />, img: <FolderOpen size={15} />, task: <Archive size={15} /> };

/**
 * 不同类型回收项的色彩映射配置
 * @type {Object.<string, string>}
 */
const typeColor = { doc: '#2563eb', img: '#7c3aed', task: '#10b981' };

/**
 * RecycleBin 归档与回收站组件
 * @component
 */
export default function RecycleBin() {
  const [list, setList] = useState(items);
  const [selected, setSelected] = useState(new Set()); // 被勾选的行 ID 集合
  const [restored, setRestored] = useState(new Set()); // 已执行恢复动作的行 ID 集合（前端乐观隐藏）
  const [permDeleted, setPermDeleted] = useState(new Set()); // 已执行彻底删除的行 ID 集合（前端乐观隐藏）
  const [activeTab, setActiveTab] = useState('tasks'); // 当前激活的 tab 页签，'tasks' (归档任务) | 'files' (已删文件)

  // 挂载时拉取回收列表，若接口不通则 fallback 展示本地 items
  useEffect(() => {
    apiGet('/api/recycle', { items }).then(data => setList(data.items || items));
  }, []);

  // 过滤掉已被恢复或已被彻底删除的数据
  const visibleList = list.filter(i => !restored.has(i.id) && !permDeleted.has(i.id));
  
  // 依据当前处于归档任务 tab 还是已删文件 tab，分别筛选出 task 数据或非 task 数据进行展示
  const visible = visibleList.filter(i => activeTab === 'tasks' ? i.type === 'task' : i.type !== 'task');

  /**
   * 勾选状态切换
   * @param {number|string} id - 条目 ID
   */
  const toggle = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  /**
   * 恢复单项数据
   * @param {number|string} id - 条目 ID
   */
  const restore = (id) => {
    apiPost(`/api/recycle/${id}/restore`, {}, null);
    // 乐观更新：将 ID 加入 restored 状态集，并在勾选列表中移除
    setRestored(prev => new Set([...prev, id]));
    setSelected(prev => { const n = new Set(prev); n.delete(id); return n; });
  };

  /**
   * 彻底永久删除单项数据
   * @param {number|string} id - 条目 ID
   */
  const permanentDelete = (id) => {
    apiDelete(`/api/recycle/${id}`, null);
    // 乐观更新：将 ID 加入 permDeleted 状态集，并在勾选列表中移除
    setPermDeleted(prev => new Set([...prev, id]));
    setSelected(prev => { const n = new Set(prev); n.delete(id); return n; });
  };

  /**
   * 批量恢复已勾选的条目
   */
  const restoreSelected = () => {
    setRestored(prev => new Set([...prev, ...selected]));
    setSelected(new Set()); // 清空勾选态
  };

  return (
    <div className="recycle-page">
      {/* 头部信息与批量操作条 */}
      <div className="recycle-top">
        <div>
          <h1 className="page-title">归档与回收</h1>
          <p className="page-sub">
            {activeTab === 'tasks' ? '归档的任务会永久保留，直到你彻底删除它' : '文件将在 30 天后自动永久删除'}
          </p>
        </div>
        {selected.size > 0 && (
          <div className="recycle-bulk">
            <span className="bulk-count">已选 {selected.size} 项</span>
            <button className="btn-restore" onClick={restoreSelected}><RotateCcw size={13} />恢复</button>
            <button className="btn-delete-perm" onClick={() => { selected.forEach(permanentDelete); }}>
              <Trash2 size={13} />{activeTab === 'tasks' ? '彻底删除' : '永久删除'}
            </button>
          </div>
        )}
      </div>

      {/* Tab 页签 */}
      <div className="recycle-tabs">
        <button 
          className={`recycle-tab ${activeTab === 'tasks' ? 'active' : ''}`}
          onClick={() => { setActiveTab('tasks'); setSelected(new Set()); }}
        >
          归档任务
        </button>
        <button 
          className={`recycle-tab ${activeTab === 'files' ? 'active' : ''}`}
          onClick={() => { setActiveTab('files'); setSelected(new Set()); }}
        >
          已删文件
        </button>
      </div>

      {/* 列表渲染与空状态控制 */}
      {visible.length === 0 ? (
        <div className="recycle-empty">
          {activeTab === 'tasks' ? <Archive size={32} className="empty-icon" /> : <Trash2 size={32} className="empty-icon" />}
          <div>{activeTab === 'tasks' ? '暂无归档任务' : '回收站为空'}</div>
        </div>
      ) : (
        <div className="recycle-table">
          <div className="recycle-head">
            <div className="rcol-check">
              {/* 全选 / 取消全选逻辑 */}
              <input type="checkbox"
                checked={selected.size === visible.length && visible.length > 0}
                onChange={e => setSelected(e.target.checked ? new Set(visible.map(i => i.id)) : new Set())}
              />
            </div>
            <div className="rcol-name">{activeTab === 'tasks' ? '项目名' : '文件名'}</div>
            <div className="rcol-by">{activeTab === 'tasks' ? '归档者' : '删除者'}</div>
            <div className="rcol-size">大小</div>
            <div className="rcol-time">{activeTab === 'tasks' ? '归档时间' : '删除时间'}</div>
            <div className="rcol-action" />
          </div>

          {visible.map(item => (
            <div key={item.id} className={`recycle-row${selected.has(item.id) ? ' selected' : ''}`}>
              <div className="rcol-check">
                <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggle(item.id)} />
              </div>
              <div className="rcol-name">
                <span className="file-icon" style={{ color: typeColor[item.type] }}>{typeIcon[item.type]}</span>
                <span className="file-name">{item.name}</span>
              </div>
              <div className="rcol-by file-meta">{item.deletedBy}</div>
              <div className="rcol-size file-meta">{item.size}</div>
              <div className="rcol-time file-meta">{item.deletedAt}</div>
              <div className="rcol-action">
                <button className="row-action-btn restore" onClick={() => restore(item.id)}>
                  <RotateCcw size={13} />恢复
                </button>
                <button className="row-action-btn danger" onClick={() => permanentDelete(item.id)}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 回收站已删文件的额外警示 */}
      {visible.length > 0 && activeTab === 'files' && (
        <div className="recycle-notice">
          <AlertTriangle size={13} />
          <span>回收站中的文件将在 30 天后自动永久删除，无法恢复</span>
        </div>
      )}
    </div>
  );
}

