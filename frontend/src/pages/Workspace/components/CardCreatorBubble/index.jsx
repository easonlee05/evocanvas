import React, { useState } from 'react';

export function CardCreatorBubble({ x, y, stage, onClose, onSubmit }) {
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [kind, setKind] = useState(() => {
    if (stage === 'define') return 'problems';
    if (stage === 'handoff') return 'planning';
    return 'evidence';
  });

  return (
    <div
      className="floating-card-creator"
      style={{ left: x + 10, top: y + 10 }}
      onClick={(event) => event.stopPropagation()}
      onPointerDown={(event) => event.stopPropagation()}
      onPointerUp={(event) => event.stopPropagation()}
    >
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)' }}>添加新画布卡片</div>
      <input placeholder="卡片标题" value={title} onChange={(event) => setTitle(event.target.value)} autoFocus />
      <textarea placeholder="一句话摘要说明..." value={desc} onChange={(event) => setDesc(event.target.value)} rows={3} />
      <select value={kind} onChange={(event) => setKind(event.target.value)}>
        <option value="evidence">发现 ➔ 证据卡</option>
        <option value="problems">定义 ➔ 问题定义卡</option>
        <option value="clarify">定义 ➔ 待澄清卡</option>
        <option value="rules">定义 ➔ 约束卡</option>
        <option value="options">定义 ➔ 待决策卡</option>
        <option value="planning">交付 ➔ 结构化交接物</option>
      </select>
      <div className="btn-row">
        <button className="cancel" onClick={onClose}>取消</button>
        <button className="save" onClick={() => onSubmit({ title, desc, kind })}>创建</button>
      </div>
    </div>
  );
}
