/**
 * @file index.jsx
 * @description 法则审核页面组件。用于数字产品经理或安全审核员对 AI 在迭代演进过程中根据修改自动提取的法则 (Rule/Guardrail) 进行审核裁决，包含：
 *   - 待审核、已批准、已驳回三类状态的页签切换。
 *   - 批准、驳回、修改并入库三个动作的控制。
 *   - 调用 API 进行审核数据保存，并通过前端 statuses 状态集合进行乐观隐藏及数量统计更新。
 */

import React, { useEffect, useState } from 'react';
import { CheckCircle2, Edit3, XCircle, X } from 'lucide-react';
import { apiGet, apiPost } from '../../api';
import './rule-audit.css';

/**
 * 过滤页签配置列表
 * @type {Array<string>}
 */
const tabs = ['待审核', '已批准', '已驳回'];

/**
 * 待审核候选法则静态演示数据
 * @type {Array<{id: string, title: string, desc: string, source: string, sourceId: string, extractedAt: string, confidence: number, status: 'pending'}>}
 */
const rules = [
  {
    id: 'R-0021',
    title: '技术方案必须包含熔断降级策略',
    desc: 'AI 发现用户在 7 次评审中均手动补充了熔断降级方案，建议将其纳入技术方案的强制输出项。',
    source: '进化引擎技术方案评审',
    sourceId: 'T-0420',
    extractedAt: '今天 10:32',
    confidence: 94,
    status: 'pending',
  },
  {
    id: 'R-0020',
    title: 'PRD 成功指标需包含可量化的数值目标',
    desc: '对比 12 份 PRD 修改记录，用户始终将模糊描述替换为带具体数值的指标，如"提升用户满意度"改为"NPS ≥ 45"。',
    source: '产品需求文档评审',
    sourceId: 'T-0421',
    extractedAt: '今天 09:15',
    confidence: 88,
    status: 'pending',
  },
  {
    id: 'R-0019',
    title: 'Agent 协作轮次超过 3 轮时需人工介入',
    desc: '统计显示，当 PM/Tech/QA 三方讨论超过 3 轮仍未收敛时，人工介入后的方案质量显著高于继续自动推演。',
    source: 'Agent 协作流程设计',
    sourceId: 'T-0418',
    extractedAt: '昨天 16:45',
    confidence: 79,
    status: 'pending',
  },
  {
    id: 'R-0018',
    title: '安全相关需求必须经过 QA Agent 二次确认',
    desc: '发现 4 次安全漏洞均出现在 QA 未参与的评审环节，建议将安全类需求标记为 QA 强制参与。',
    source: '法则库季度审查',
    sourceId: 'T-0417',
    extractedAt: '昨天 14:20',
    confidence: 91,
    status: 'pending',
  },
];

/**
 * 已批准法则静态演示数据
 * @type {Array<{id: string, title: string, source: string, approvedAt: string, status: 'approved'}>}
 */
const approvedRules = [
  { id: 'R-0017', title: '文档标题需包含版本号', source: 'T-0415', approvedAt: '3 天前', status: 'approved' },
  { id: 'R-0016', title: '技术选型需列出备选方案及取舍理由', source: 'T-0414', approvedAt: '5 天前', status: 'approved' },
];

/**
 * 已驳回法则静态演示数据
 * @type {Array<{id: string, title: string, source: string, rejectedAt: string, status: 'rejected'}>}
 */
const rejectedRules = [
  { id: 'R-0015', title: '所有任务默认启用深度思考模式', source: 'T-0413', rejectedAt: '1 周前', status: 'rejected' },
];

/**
 * 根据置信度数值计算展示颜色的辅助函数
 * @param {number} v - 置信度（百分比数值 0-100）
 * @returns {string} 十六进制颜色代码
 */
const confidenceColor = (v) => v >= 90 ? '#16a34a' : v >= 75 ? '#d97706' : '#dc2626';

/**
 * RuleAudit 法则审核组件
 * @component
 */
export default function RuleAudit() {
  const [tab, setTab] = useState('待审核');
  const [statuses, setStatuses] = useState({}); // 临时保存本次操作处理的规则 ID 及其裁决状态映射，形如：{ 'R-0021': 'approved' }
  const [pendingRules, setPendingRules] = useState(rules);
  const [approvedList, setApprovedList] = useState(approvedRules);
  const [rejectedList, setRejectedList] = useState(rejectedRules);

  const [editingRule, setEditingRule] = useState(null); // 当前正在执行模态编辑的 Rule 对象，若为 null 则关闭编辑框
  const [editTitle, setEditTitle] = useState(''); // 编辑弹窗中绑定的临时标题状态
  const [editDesc, setEditDesc] = useState(''); // 编辑弹窗中绑定的临时描述状态

  /**
   * 处理快速批准或驳回操作
   * @param {string} id - 规则 ID
   * @param {'approved'|'rejected'} action - 处理动作
   */
  const handle = (id, action) => {
    if (action === 'rejected') apiPost(`/api/rules/${id}/reject`, {}, null);
    else apiPost(`/api/rules/${id}/approve`, {}, null);
    
    // 乐观更新：将规则的操作保存到状态字典中
    setStatuses(prev => ({ ...prev, [id]: action }));
  };

  /**
   * 打开编辑法则的模态框
   * @param {Object} rule - 要修改的目标法则
   */
  const openEditModal = (rule) => {
    setEditingRule(rule);
    setEditTitle(rule.title);
    setEditDesc(rule.desc);
  };

  /**
   * 保存并批准已编辑修改的法则
   */
  const handleSaveEdit = () => {
    if (!editingRule) return;
    const id = editingRule.id;
    // 乐观同步更新待审核数据，把被修改过的内容写回 pending 列表中
    setPendingRules(prev => prev.map(r => r.id === id ? { ...r, title: editTitle, desc: editDesc } : r));
    // 发送带有修改后 title/desc 的批准 API
    apiPost(`/api/rules/${id}/approve`, { title: editTitle, desc: editDesc }, null);
    
    // 将状态标为已批准，从待审核流中剔除并转入已批准列表中
    setStatuses(prev => ({ ...prev, [id]: 'approved' }));
    setEditingRule(null);
  };

  // 挂载时并行加载待审核、已批准、已驳回数据，若失败则退回演示数据
  useEffect(() => {
    apiGet('/api/rules?status=pending', { rules }).then(data => setPendingRules(data.rules || rules));
    apiGet('/api/rules?status=approved', { rules: approvedRules }).then(data => setApprovedList(data.rules || approvedRules));
    apiGet('/api/rules?status=rejected', { rules: rejectedRules }).then(data => setRejectedList(data.rules || rejectedRules));
  }, []);

  // 过滤当前页面未进行任何操作处理的待审核列表数据
  const pendingList = pendingRules.filter(r => !statuses[r.id]);
  
  // 计算各状态标签显示的数量计数（本地拉取的数据量 + 本次交互中产生的改变数）
  const counts = {
    '待审核': pendingList.length,
    '已批准': approvedList.length + Object.values(statuses).filter(s => s === 'approved').length,
    '已驳回': rejectedList.length + Object.values(statuses).filter(s => s === 'rejected').length,
  };

  return (
    <div className="rule-page">
      {/* 头部标题与置信数据统计 */}
      <div className="rule-top">
        <div>
          <h1 className="page-title">法则审核</h1>
          <p className="page-sub">AI 从任务修改中提炼的候选法则，等待你的裁决</p>
        </div>
        <div className="rule-stats">
          {Object.entries(counts).map(([label, count]) => (
            <div key={label} className="rule-stat">
              <span className="rule-stat-num">{count}</span>
              <span className="rule-stat-label">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 状态页签 */}
      <div className="rule-tabs">
        {tabs.map(t => (
          <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t}
            {counts[t] > 0 && <span className="tab-count">{counts[t]}</span>}
          </button>
        ))}
      </div>

      {/* 法则列表展示区 */}
      <div className="rule-list">
        {/* 1. 待审核页签渲染逻辑 */}
        {tab === '待审核' && pendingList.map(rule => (
          <div key={rule.id} className="rule-card">
            <div className="rule-card-body">
              <div className="rule-card-header">
                <span className="rule-id">{rule.id}</span>
                <span className="rule-confidence" style={{ color: confidenceColor(rule.confidence) }}>
                  置信度 {rule.confidence}%
                </span>
              </div>
              <div className="rule-title">{rule.title}</div>
              <div className="rule-desc">{rule.desc}</div>
              <div className="rule-meta">
                来源：<span className="rule-source">{rule.source}</span>
                <span className="rule-dot">·</span>
                {rule.extractedAt}
              </div>
            </div>
            <div className="rule-actions">
              <button className="rule-btn approve" onClick={() => handle(rule.id, 'approved')}>
                <CheckCircle2 size={14} />批准入库
              </button>
              <button className="rule-btn edit" onClick={() => openEditModal(rule)}>
                <Edit3 size={14} />修改后入库
              </button>
              <button className="rule-btn reject" onClick={() => handle(rule.id, 'rejected')}>
                <XCircle size={14} />驳回
              </button>
            </div>
          </div>
        ))}

        {tab === '待审核' && pendingList.length === 0 && (
          <div className="rule-empty">
            <CheckCircle2 size={32} className="empty-icon" />
            <div>全部处理完毕</div>
          </div>
        )}

        {/* 2. 已批准页签渲染逻辑 */}
        {tab === '已批准' && [...approvedList, ...pendingRules.filter(r => statuses[r.id] === 'approved')].map(rule => (
          <div key={rule.id} className="rule-card rule-card-done">
            <div className="rule-card-body">
              <div className="rule-card-header">
                <span className="rule-id">{rule.id}</span>
                <span className="rule-done-badge approved">已批准</span>
              </div>
              <div className="rule-title">{rule.title}</div>
              <div className="rule-meta">来源：{rule.source} · {rule.approvedAt || '刚刚'}</div>
            </div>
          </div>
        ))}

        {/* 3. 已驳回页签渲染逻辑 */}
        {tab === '已驳回' && [...rejectedList, ...pendingRules.filter(r => statuses[r.id] === 'rejected')].map(rule => (
          <div key={rule.id} className="rule-card rule-card-done">
            <div className="rule-card-body">
              <div className="rule-card-header">
                <span className="rule-id">{rule.id}</span>
                <span className="rule-done-badge rejected">已驳回</span>
              </div>
              <div className="rule-title">{rule.title}</div>
              <div className="rule-meta">来源：{rule.source} · {rule.rejectedAt || '刚刚'}</div>
            </div>
          </div>
        ))}
      </div>

      {/* 修改规则入库弹窗 */}
      {editingRule && (
        <div className="modal-overlay" onClick={() => setEditingRule(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">修改法则并入库</span>
              <button className="modal-close" onClick={() => setEditingRule(null)}><X size={15} /></button>
            </div>
            <div className="modal-body">
              <div className="form-field">
                <label className="form-label">法则标题</label>
                <input className="form-input" value={editTitle} onChange={e => setEditTitle(e.target.value)} />
              </div>
              <div className="form-field">
                <label className="form-label">法则描述</label>
                <textarea className="form-textarea" rows={4} value={editDesc} onChange={e => setEditDesc(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="modal-btn-cancel" onClick={() => setEditingRule(null)}>取消</button>
              <button className="modal-btn-submit" onClick={handleSaveEdit} disabled={!editTitle.trim() || !editDesc.trim()}>入库</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
