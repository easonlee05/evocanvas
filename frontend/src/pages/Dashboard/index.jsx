/**
 * @file index.jsx
 * @description 仪表盘页面。聚合展示 EvoCanvas 工作区的状态监控指标，包括：
 *   - 运行中任务、本周完成任务数、Agent 调用量等指标卡片。
 *   - 当前进行中的任务列表与具体进度。
 *   - 团队内部各 Agent 角色当前的繁忙/空闲状态。
 */

import React from 'react';
import {
  TrendingUp, CheckCircle2, Clock, AlertCircle,
  ArrowUpRight, MoreHorizontal, Zap, Users, Brain,
  Activity, ChevronRight, Play, Pause
} from 'lucide-react';
import './dashboard.css';

/**
 * 仪表盘核心统计指标数据
 * @type {Array<{label: string, value: string, delta: string, trend: 'up'|'down'|'neutral', icon: React.ReactNode}>}
 */
const stats = [
  { label: '进行中任务', value: '12', delta: '+3', trend: 'up', icon: <Activity size={16} /> },
  { label: '本周完成', value: '28', delta: '+12%', trend: 'up', icon: <CheckCircle2 size={16} /> },
  { label: 'Agent 调用', value: '1,847', delta: '+24%', trend: 'up', icon: <Brain size={16} /> },
  { label: '团队成员', value: '6', delta: '在线', trend: 'neutral', icon: <Users size={16} /> },
];

/**
 * 任务列表展示用模拟数据
 * @type {Array<{id: string, title: string, status: 'running'|'review'|'pending'|'done', agent: string, progress: number, priority: 'high'|'medium'|'low'}>}
 */
const tasks = [
  { id: 'T-0421', title: '产品需求文档评审', status: 'running', agent: 'PM + Tech + QA', progress: 68, priority: 'high' },
  { id: 'T-0420', title: '用户增长策略 analysis 报告', status: 'review', agent: 'Intern + Reviewer', progress: 92, priority: 'medium' },
  { id: 'T-0419', title: '云原生架构迁移方案', status: 'pending', agent: '待分配', progress: 0, priority: 'high' },
  { id: 'T-0418', title: '竞品功能对比分析', status: 'done', agent: 'Expert', progress: 100, priority: 'low' },
  { id: 'T-0417', title: '法则库季度审查', status: 'done', agent: 'Reviewer', progress: 100, priority: 'medium' },
];

/**
 * Agent 状态信息数据
 * @type {Array<{name: string, role: string, status: 'busy'|'idle', task: string|null}>}
 */
const agents = [
  { name: 'PM Agent', role: '产品经理', status: 'busy', task: 'T-0421' },
  { name: 'Tech Lead', role: '架构师', status: 'busy', task: 'T-0421' },
  { name: 'QA Agent', role: '测试专家', status: 'busy', task: 'T-0421' },
  { name: 'Intern', role: '实习生', status: 'idle', task: null },
  { name: 'Reviewer', role: '审查员', status: 'idle', task: null },
  { name: 'Expert', role: '专家顾问', status: 'idle', task: null },
];

/**
 * 状态角标的样式与文本映射配置
 * @type {Object.<string, {label: string, color: string, bg: string}>}
 */
const statusConfig = {
  running: { label: '运行中', color: '#5c5cf0', bg: 'rgba(92,92,240,0.08)' },
  review:  { label: '审查中', color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
  pending: { label: '待启动', color: '#9898b0', bg: 'rgba(152,152,176,0.08)' },
  done:    { label: '已完成', color: '#10b981', bg: 'rgba(16,185,129,0.08)' },
};

/**
 * 优先级显示的颜色与文本映射配置
 * @type {Object.<string, {label: string, color: string}>}
 */
const priorityConfig = {
  high:   { label: '高', color: '#ef4444' },
  medium: { label: '中', color: '#f59e0b' },
  low:    { label: '低', color: '#10b981' },
};

/**
 * Dashboard 仪表盘页面组件
 * @component
 */
export default function Dashboard() {
  return (
    <div className="dashboard">
      {/* 顶部统计卡片行 */}
      <div className="stats-row">
        {stats.map((s, i) => (
          <div key={i} className="stat-card">
            <div className="stat-card-header">
              <span className="stat-card-label">{s.label}</span>
              <span className="stat-card-icon">{s.icon}</span>
            </div>
            <div className="stat-card-value">{s.value}</div>
            <div className="stat-card-delta" data-trend={s.trend}>
              {s.trend === 'up' && <TrendingUp size={11} />}
              <span>{s.delta}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-body">
        {/* 左侧任务列表面板 */}
        <div className="panel task-panel">
          <div className="panel-header">
            <span className="panel-title">任务列表</span>
            <button className="panel-action">查看全部 <ChevronRight size={13} /></button>
          </div>
          <div className="task-list">
            {tasks.map((t, i) => {
              const sc = statusConfig[t.status];
              const pc = priorityConfig[t.priority];
              return (
                <div key={i} className="task-row">
                  <div className="task-id">{t.id}</div>
                  <div className="task-main">
                    <div className="task-title">{t.title}</div>
                    <div className="task-meta">
                      <span className="task-agent">{t.agent}</span>
                    </div>
                  </div>
                  {/* 仅在运行中状态下，渲染进度条 */}
                  {t.status === 'running' && (
                    <div className="task-progress-wrap">
                      <div className="task-progress-bar">
                        <div className="task-progress-fill" style={{ width: `${t.progress}%` }} />
                      </div>
                      <span className="task-progress-pct">{t.progress}%</span>
                    </div>
                  )}
                  <span className="task-priority" style={{ color: pc.color }}>
                    {pc.label}
                  </span>
                  <span className="task-status-badge" style={{ color: sc.color, background: sc.bg }}>
                    {sc.label}
                  </span>
                  <button className="task-more"><MoreHorizontal size={14} /></button>
                </div>
              );
            })}
          </div>
        </div>

        {/* 右侧 Agent 状态列表面板 */}
        <div className="panel agent-panel">
          <div className="panel-header">
            <span className="panel-title">Agent 状态</span>
            <span className="panel-badge">6 个</span>
          </div>
          <div className="agent-list">
            {agents.map((a, i) => (
              <div key={i} className="agent-row">
                {/* 头像左侧指示灯标识忙碌状态 */}
                <div className="agent-avatar" data-status={a.status}>
                  {a.name[0]}
                </div>
                <div className="agent-info">
                  <div className="agent-name">{a.name}</div>
                  <div className="agent-role">{a.role}</div>
                </div>
                <div className="agent-status" data-status={a.status}>
                  <span className="agent-dot" />
                  <span>{a.status === 'busy' ? `执行 ${a.task}` : '空闲'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
