/**
 * @file index.jsx
 * @description 文件中心页面组件。展示 Evoloop 项目在运行过程中产生的所有文档产物（如 PRD、操作手册、架构方案等）以及图片或其它形式的附件，包含：
 *   - 文件大类标签页切换 (文档/图片/其他)。
 *   - 搜索输入过滤。
 *   - 视图切换机制（表格列表视图 vs 网格卡片视图）。
 *   - 文件上传（支持多文件，调用 apiUpload）。
 */

import React, { useState, useRef } from 'react';
import { Search, Plus, FileText, FolderOpen, MoreHorizontal, Clock, Download, Trash2, Grid, List } from 'lucide-react';
import './file-center.css';
import { apiUpload } from '../../api';

/**
 * 分类 tab 列表
 * @type {Array<string>}
 */
const tabs = ['全部', '文档', '图片', '其他'];

/**
 * 模拟文件中心文件列表数据
 * @type {Array<{id: number, name: string, type: 'doc'|'img', size: string, updated: string, author: string, task: string}>}
 */
const files = [
  { id: 1, name: '产品需求文档 v2.0.md', type: 'doc', size: '48 KB', updated: '10 分钟前', author: 'PM Agent', task: 'T-0421' },
  { id: 2, name: 'EvoLoop 架构设计文档.md', type: 'doc', size: '92 KB', updated: '2 小时前', author: 'Tech Agent', task: 'T-0420' },
  { id: 3, name: '用户增长策略分析报告.md', type: 'doc', size: '64 KB', updated: '昨天', author: 'Intern', task: 'T-0420' },
  { id: 4, name: '竞品功能对比分析.md', type: 'doc', size: '36 KB', updated: '昨天', author: 'Expert', task: 'T-0418' },
  { id: 5, name: 'API 网关压测报告.md', type: 'doc', size: '28 KB', updated: '2 天前', author: 'QA Agent', task: 'T-0416' },
  { id: 6, name: '系统架构图 v1.png', type: 'img', size: '1.2 MB', updated: '3 天前', author: 'Tech Agent', task: 'T-0416' },
  { id: 7, name: '法则库季度审查报告.md', type: 'doc', size: '52 KB', updated: '5 天前', author: 'Reviewer', task: 'T-0417' },
  { id: 8, name: '新用户引导流程图.png', type: 'img', size: '860 KB', updated: '1 周前', author: 'PM Agent', task: 'T-0415' },
];

/**
 * 文件类型对应的中文名称映射
 * @type {Object.<string, string>}
 */
const typeMap = { doc: '文档', img: '图片' };

/**
 * 不同文件类型所使用的 Lucide 图标映射
 * @type {Object.<string, React.ReactNode>}
 */
const typeIcon = { doc: <FileText size={15} />, img: <FolderOpen size={15} /> };

/**
 * 不同文件类型对应的色彩配色映射
 * @type {Object.<string, string>}
 */
const typeColor = { doc: '#2563eb', img: '#7c3aed' };

/**
 * FileCenter 文件中心组件
 * @component
 */
export default function FileCenter() {
  const [tab, setTab] = useState('全部'); // 当前激活的分类页签
  const [query, setQuery] = useState(''); // 搜索关键词
  const [view, setView] = useState('list'); // 视图模式: 'list' (列表) | 'grid' (网格)
  const fileInputRef = useRef(null);

  /**
   * 上传文件处理函数，支持选中多个文件并串行上传
   * @param {React.ChangeEvent<HTMLInputElement>} e - 文件变更事件对象
   */
  const handleUpload = async (e) => {
    const picked = Array.from(e.target.files);
    e.target.value = ''; // 重置文件输入框的值，以触发下一次同名文件上传
    for (const file of picked) {
      await apiUpload('/api/materials', file, null);
    }
  };

  // 根据当前激活的 tab 以及搜索框中 query 输入，进行前端内存级文件数据过滤
  const filtered = files.filter(f => {
    const matchTab = tab === '全部' || typeMap[f.type] === tab;
    const matchQuery = !query || f.name.includes(query);
    return matchTab && matchQuery;
  });

  return (
    <div className="file-page">
      {/* 头部标题与上传按钮 */}
      <div className="file-top">
        <div>
          <h1 className="page-title">文件中心</h1>
          <p className="page-sub">任务产出的所有文档与附件</p>
        </div>
        <button className="btn-primary-sm" onClick={() => fileInputRef.current?.click()}>
          <Plus size={13} />上传文件
        </button>
        {/* 隐藏的上传文件节点 */}
        <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleUpload} />
      </div>

      {/* 搜索过滤与布局切换工具栏 */}
      <div className="file-toolbar">
        <div className="file-tabs">
          {tabs.map(t => (
            <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>
        <div className="file-toolbar-right">
          <div className="file-search">
            <Search size={13} className="search-icon" />
            <input className="search-input" placeholder="搜索文件…" value={query} onChange={e => setQuery(e.target.value)} />
          </div>
          <div className="view-toggle">
            <button className={`view-btn${view === 'list' ? ' active' : ''}`} onClick={() => setView('list')}><List size={14} /></button>
            <button className={`view-btn${view === 'grid' ? ' active' : ''}`} onClick={() => setView('grid')}><Grid size={14} /></button>
          </div>
        </div>
      </div>

      {/* 内容区域：根据列表模式 or 网格模式切换不同的 DOM 渲染逻辑 */}
      {view === 'list' ? (
        <div className="file-table">
          <div className="file-table-head">
            <div className="fcol-name">文件名</div>
            <div className="fcol-task">来源任务</div>
            <div className="fcol-author">创建者</div>
            <div className="fcol-size">大小</div>
            <div className="fcol-time">更新时间</div>
            <div className="fcol-action" />
          </div>
          {filtered.map(f => (
            <div key={f.id} className="file-row">
              <div className="fcol-name">
                <span className="file-icon" style={{ color: typeColor[f.type] }}>{typeIcon[f.type]}</span>
                <span className="file-name">{f.name}</span>
              </div>
              <div className="fcol-task file-task">{f.task}</div>
              <div className="fcol-author file-meta">{f.author}</div>
              <div className="fcol-size file-meta">{f.size}</div>
              <div className="fcol-time file-meta">{f.updated}</div>
              <div className="fcol-action">
                <button className="row-action"><Download size={13} /></button>
                <button className="row-action"><MoreHorizontal size={13} /></button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="file-grid">
          {filtered.map(f => (
            <div key={f.id} className="file-card">
              <div className="file-card-icon" style={{ color: typeColor[f.type], background: typeColor[f.type] + '10' }}>
                {typeIcon[f.type]}
              </div>
              <div className="file-card-name">{f.name}</div>
              <div className="file-card-meta">{f.size} · {f.updated}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

