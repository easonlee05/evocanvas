/**
 * @file index.jsx
 * @description 开发沙盒控制台组件。用于开发人员和 Agent 进行代码、法则校验和仿真运行时的状态看板，包含：
 *   - 左侧沙盒实例管理器列表（支持切换激活态）。
 *   - 实例工具栏（启动/停止、重启、克隆等动作交互区域）。
 *   - 硬件指标（CPU、内存利用率进度条，仅在运行状态下展示）。
 *   - 实时控制台终端日志回显。
 */

import React, { useState } from 'react';
import {
  Terminal, Play, Square, RotateCcw, Copy,
  ChevronRight, Circle, CheckCircle2, AlertCircle,
  Clock, Cpu, MemoryStick, Wifi
} from 'lucide-react';
import './dev-sandbox.css';

/**
 * 仿真沙盒环境实例列表数据
 * @type {Array<{id: string, name: string, status: 'running'|'stopped'|'error', uptime: string, cpu: number, mem: number}>}
 */
const sandboxes = [
  { id: 'SB-001', name: '产品 PRD 验证沙盒', status: 'running', uptime: '2h 14m', cpu: 34, mem: 512 },
  { id: 'SB-002', name: '架构方案压测环境', status: 'stopped', uptime: '—', cpu: 0, mem: 0 },
  { id: 'SB-003', name: '知识库迁移测试', status: 'error', uptime: '0m', cpu: 0, mem: 0 },
];

/**
 * 终端展示的模拟系统日志数据
 * @type {Array<{time: string, level: 'info'|'warn'|'error', msg: string}>}
 */
const logs = [
  { time: '14:32:01', level: 'info',  msg: '[PM] 正在分析需求文档，识别核心用户故事...' },
  { time: '14:32:04', level: 'info',  msg: '[Tech] 收到 PM 草案，开始架构可行性评估' },
  { time: '14:32:09', level: 'warn',  msg: '[Tech] 发现潜在并发瓶颈：消息队列吞吐量不足' },
  { time: '14:32:11', level: 'info',  msg: '[QA] 注入异常场景：断网 + 脏数据并发写入' },
  { time: '14:32:15', level: 'error', msg: '[QA] 致命用例：事务回滚未覆盖分布式场景' },
  { time: '14:32:18', level: 'info',  msg: '[PM] 收到挑战，修订方案中... (轮次 2/3)' },
  { time: '14:32:22', level: 'info',  msg: '[Reviewer] 执行 Gate A~D 质量门禁检查' },
  { time: '14:32:25', level: 'info',  msg: '[Reviewer] Gate A: PASS | Gate B: PASS | Gate C: WARN' },
];

/**
 * 沙盒状态的徽章标签配置
 * @type {Object.<string, {label: string, color: string, icon: React.ReactNode}>}
 */
const statusConfig = {
  running: { label: '运行中', color: '#10b981', icon: <Circle size={8} fill="#10b981" /> },
  stopped: { label: '已停止', color: '#9898b0', icon: <Circle size={8} /> },
  error:   { label: '异常',   color: '#ef4444', icon: <AlertCircle size={12} /> },
};

/**
 * 终端日志等级的高亮色彩映射
 * @type {Object.<string, {color: string, prefix: string}>}
 */
const levelConfig = {
  info:  { color: '#5a5a72', prefix: 'INFO ' },
  warn:  { color: '#f59e0b', prefix: 'WARN ' },
  error: { color: '#ef4444', prefix: 'ERR  ' },
};

/**
 * DevSandbox 开发沙盒管理页面组件
 * @component
 */
export default function DevSandbox() {
  // 当前处于选中激活态的沙盒 ID
  const [activeId, setActiveId] = useState('SB-001');
  
  // 根据激活 ID 计算匹配的沙盒元数据
  const active = sandboxes.find(s => s.id === activeId);

  return (
    <div className="dev-sandbox">
      {/* 左侧侧边栏列表 */}
      <div className="sandbox-list-panel">
        <div className="sandbox-list-header">
          <span>沙盒实例</span>
          <button className="new-sandbox-btn">+ 新建</button>
        </div>
        {sandboxes.map(sb => {
          const sc = statusConfig[sb.status];
          return (
            <div
              key={sb.id}
              className={`sandbox-item${activeId === sb.id ? ' active' : ''}`}
              onClick={() => setActiveId(sb.id)}
            >
              <div className="sandbox-item-dot" style={{ color: sc.color }}>{sc.icon}</div>
              <div className="sandbox-item-body">
                <div className="sandbox-item-name">{sb.name}</div>
                <div className="sandbox-item-id">{sb.id} · {sc.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 右侧主工作区 */}
      <div className="sandbox-main">
        {/* 工具操作栏 */}
        <div className="sandbox-toolbar">
          <div className="sandbox-toolbar-left">
            <span className="sandbox-name">{active?.name}</span>
            <span className="sandbox-id-badge">{active?.id}</span>
          </div>
          <div className="sandbox-toolbar-right">
            {active?.status === 'running' ? (
              <button className="toolbar-btn danger"><Square size={13} /> 停止</button>
            ) : (
              <button className="toolbar-btn primary"><Play size={13} /> 启动</button>
            )}
            <button className="toolbar-btn"><RotateCcw size={13} /> 重启</button>
            <button className="toolbar-btn"><Copy size={13} /> 克隆</button>
          </div>
        </div>

        {/* 性能指标栏：仅在沙盒运行中时渲染 */}
        {active?.status === 'running' && (
          <div className="sandbox-metrics">
            <div className="metric-item">
              <Cpu size={13} />
              <span className="metric-label">CPU</span>
              <div className="metric-bar">
                <div className="metric-fill" style={{ width: `${active.cpu}%`, background: '#5c5cf0' }} />
              </div>
              <span className="metric-val">{active.cpu}%</span>
            </div>
            <div className="metric-item">
              <MemoryStick size={13} />
              <span className="metric-label">内存</span>
              <div className="metric-bar">
                {/* 假设最大内存为 1024MB，用于计算内存条比例 */}
                <div className="metric-fill" style={{ width: `${active.mem / 1024 * 100}%`, background: '#10b981' }} />
              </div>
              <span className="metric-val">{active.mem} MB</span>
            </div>
            <div className="metric-item">
              <Clock size={13} />
              <span className="metric-label">运行时长</span>
              <span className="metric-val">{active.uptime}</span>
            </div>
          </div>
        )}

        {/* 虚拟实时日志终端组件 */}
        <div className="terminal">
          <div className="terminal-header">
            <Terminal size={13} />
            <span>实时日志</span>
            <span className="terminal-live">● LIVE</span>
          </div>
          <div className="terminal-body">
            {logs.map((log, i) => {
              const lc = levelConfig[log.level];
              return (
                <div key={i} className="log-line">
                  <span className="log-time">{log.time}</span>
                  <span className="log-level" style={{ color: lc.color }}>{lc.prefix}</span>
                  <span className="log-msg" style={{ color: lc.color === '#5a5a72' ? '#c8c8e0' : lc.color }}>
                    {log.msg}
                  </span>
                </div>
              );
            })}
            <div className="log-cursor">█</div>
          </div>
        </div>
      </div>
    </div>
  );
}

