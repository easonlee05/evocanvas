import React, { useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  ListTodo,
  Paperclip,
  Pin,
  Scale,
} from 'lucide-react';

export function TimelineScrubber({
  isPinned = true,
  onPinToggle,
  onDragStart,
  isCollapsed = true,
  onCollapsedChange,
  style,
}) {
  const collapsed = isCollapsed;

  const containerStyle = isPinned ? {
    position: 'absolute',
    left: '12px',
    bottom: '12px',
    width: collapsed ? '140px' : '720px',
    height: collapsed ? '34px' : '160px',
    background: 'rgba(255, 255, 255, 0.95)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border: '1px solid var(--border)',
    borderRadius: collapsed ? '17px' : '12px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
    padding: collapsed ? '6px 12px' : '14px 20px var(--sp-4) 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: collapsed ? 0 : 10,
    zIndex: 95,
    overflow: 'hidden',
    cursor: collapsed ? 'pointer' : 'default',
    transition: 'width 0.35s cubic-bezier(0.4, 0, 0.2, 1), height 0.35s cubic-bezier(0.4, 0, 0.2, 1), border-radius 0.35s, padding 0.35s, gap 0.35s',
    ...style,
  } : {
    width: '100%',
    height: '160px',
    background: 'rgba(255, 255, 255, 0.95)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
    padding: '14px 20px var(--sp-4) 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    overflow: 'hidden',
  };

  return (
    <div
      className={`timeline-scrubber-fixed ${isPinned ? 'pinned' : 'unpinned'} ${collapsed ? 'collapsed' : ''}`}
      style={containerStyle}
      onClick={(isPinned && collapsed) ? () => onCollapsedChange?.(false) : undefined}
      onPointerDown={isPinned ? (event) => event.stopPropagation() : undefined}
    >
      {(isPinned && collapsed) ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            width: '100%',
            height: '100%',
            color: 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '11px',
            whiteSpace: 'nowrap',
          }}
        >
          <span>显示项目时间轴</span>
          <ChevronUp size={12} style={{ color: 'var(--text-tertiary)' }} />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%', width: '100%' }}>
          <div
            className="timeline-header"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              width: '100%',
              cursor: !isPinned ? 'move' : 'default',
            }}
            onPointerDown={!isPinned ? onDragStart : undefined}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>时间轴：项目里程碑</span>
            <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                className="icon-btn"
                onClick={(event) => { event.stopPropagation(); onPinToggle(); }}
                title={isPinned ? '取消固定，移入画布漂移' : '固定在左下角'}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  color: isPinned ? 'var(--text-primary)' : 'var(--text-secondary)',
                  transition: 'color 0.2s',
                }}
              >
                <Pin size={13} style={!isPinned ? { transform: 'rotate(-45deg)' } : {}} fill={isPinned ? 'var(--text-primary)' : 'none'} />
              </button>
              {isPinned && (
                <button
                  className="icon-btn"
                  onClick={(event) => { event.stopPropagation(); onCollapsedChange?.(true); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}
                  title="收起时间轴"
                >
                  <ChevronDown size={14} className="text-tertiary" />
                </button>
              )}
            </div>
          </div>

          <div className="timeline-body" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div className="timeline-ticks">
              <div className="tick-item" style={{ left: '12.5%' }}>
                <span className="tick-label">Q2 - 4月</span>
                <div className="tick-line" />
              </div>
              <div className="tick-item" style={{ left: '25%' }}>
                <span className="tick-label">5月</span>
                <div className="tick-line" />
              </div>
              <div className="tick-item" style={{ left: '70%' }}>
                <span className="tick-label">6月</span>
                <div className="tick-line" />
              </div>
              <div className="tick-item" style={{ left: '92%' }}>
                <span className="tick-label">Q3 - 7月</span>
                <div className="tick-line" />
              </div>
            </div>

            <div className="timeline-segmented-track" style={{ marginTop: 8 }}>
              <div className="track-segment segment-gray" style={{ width: '25%' }}>
                <span>阶段</span>
              </div>
              <div className="track-segment segment-blue" style={{ width: '45%' }}>
                <span>内测发布</span>
              </div>
              <div className="track-segment segment-gray" style={{ width: '30%' }}>
                <span>MVP 上线</span>
              </div>

              <div className="timeline-current-pointer" style={{ left: '51%' }}>
                <div className="pointer-line" />
                <span className="pointer-label">当前日期：5月18日</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function ActiveBacklogPanel({
  isChatOpen,
  isPinned = true,
  onPinToggle,
  onDragStart,
  isCollapsed = false,
  onCollapsedChange,
  canvasSections = {},
  selectedCardId,
  setSelectedCardId,
  uploadedMaterials = [],
  style,
}) {
  const cards = Object.values(canvasSections).flat();
  const activeClarifications = cards.filter((card) => card.kind === 'clarification' && ['open', 'draft', 'pending', 'active'].includes(card.status));
  const activeDecisions = cards.filter((card) => card.kind === 'decision' && ['pending', 'active', 'draft'].includes(card.status));
  const blockedCards = cards.filter((card) => card.status === 'blocked');
  const activeCount = activeClarifications.length + activeDecisions.length + blockedCards.length;

  const containerStyle = isPinned ? {
    position: 'absolute',
    top: '24px',
    right: isChatOpen ? '452px' : '156px',
    width: isCollapsed ? 'auto' : '280px',
    height: isCollapsed ? '36px' : 'auto',
    maxHeight: isCollapsed ? '36px' : 'calc(100vh - 64px)',
    background: '#ffffff',
    border: '1px solid var(--border)',
    borderRadius: isCollapsed ? '999px' : '12px',
    zIndex: 90,
    padding: isCollapsed ? '8px 16px' : '16px',
    boxShadow: isCollapsed ? '0 4px 12px rgba(0,0,0,0.06)' : '0 10px 30px rgba(0,0,0,0.1)',
    display: 'flex',
    flexDirection: isCollapsed ? 'row' : 'column',
    alignItems: isCollapsed ? 'center' : 'stretch',
    gap: isCollapsed ? 6 : 16,
    overflowY: isCollapsed ? 'hidden' : 'auto',
    boxSizing: 'border-box',
    cursor: isCollapsed ? 'pointer' : 'default',
    transition: 'width 0.3s ease, height 0.3s ease, max-height 0.3s ease, border-radius 0.3s, padding 0.3s, gap 0.3s',
    ...style,
  } : {
    width: '280px',
    height: 'auto',
    maxHeight: '450px',
    background: '#ffffff',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    zIndex: 10,
    padding: '16px',
    boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    overflowY: 'auto',
    boxSizing: 'border-box',
  };

  return (
    <div
      className={`active-backlog-sidepanel ${isPinned ? 'pinned' : 'unpinned'} ${isCollapsed ? 'collapsed' : ''}`}
      style={containerStyle}
      onClick={(isPinned && isCollapsed) ? () => onCollapsedChange?.(false) : undefined}
      onPointerDown={isPinned ? (event) => event.stopPropagation() : undefined}
    >
      {(isPinned && isCollapsed) ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            width: '100%',
            height: '100%',
            color: 'var(--text-secondary)',
            fontWeight: 600,
            fontSize: '12px',
            whiteSpace: 'nowrap',
          }}
        >
          <ListTodo size={14} color="var(--text-secondary)" style={{ flexShrink: 0 }} />
          <span>活跃缺口 ({activeCount})</span>
        </div>
      ) : (
        <>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid #f1f5f9',
              paddingBottom: 10,
              cursor: !isPinned ? 'move' : 'default',
            }}
            onPointerDown={!isPinned ? onDragStart : undefined}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
              <ListTodo size={16} color="var(--text-secondary)" /> 活跃缺口看板
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="canvas-badge" style={{ fontSize: 10, padding: '2px 6px', background: 'var(--bg-subtle)', border: '1px solid var(--border)', color: 'var(--text-secondary)', borderRadius: '4px', fontWeight: '600' }}>
                {activeCount} 活跃
              </span>
              <button
                onClick={(event) => { event.stopPropagation(); onPinToggle(); }}
                title={isPinned ? '取消固定，移入画布漂移' : '固定在右上角'}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 2,
                  display: 'flex',
                  alignItems: 'center',
                  color: isPinned ? 'var(--text-primary)' : 'var(--text-secondary)',
                  transition: 'color 0.2s',
                }}
              >
                <Pin size={13} style={!isPinned ? { transform: 'rotate(-45deg)' } : {}} fill={isPinned ? 'var(--text-primary)' : 'none'} />
              </button>
              {isPinned && (
                <button
                  onClick={(event) => { event.stopPropagation(); onCollapsedChange?.(true); }}
                  title="收起看板"
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 2,
                    display: 'flex',
                    alignItems: 'center',
                    color: 'var(--text-tertiary)',
                  }}
                >
                  <ChevronDown size={14} className="text-tertiary" />
                </button>
              )}
            </div>
          </div>

          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              待澄清问题 (Clarification)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {activeClarifications.map((item) => (
                <BacklogCard key={item.id} icon={<HelpCircle size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />} item={item} selectedCardId={selectedCardId} setSelectedCardId={setSelectedCardId} />
              ))}
              {activeClarifications.length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无活跃待澄清</div>
              )}
            </div>
          </div>

          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              待决策事项 (Decision)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {activeDecisions.map((item) => (
                <BacklogCard key={item.id} icon={<Scale size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />} item={item} selectedCardId={selectedCardId} setSelectedCardId={setSelectedCardId} />
              ))}
              {activeDecisions.length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无活跃决策</div>
              )}
            </div>
          </div>

          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              阻塞项 (Blocked)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {blockedCards.map((item) => (
                <BacklogCard key={item.id} icon={<AlertTriangle size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />} item={item} selectedCardId={selectedCardId} setSelectedCardId={setSelectedCardId} />
              ))}
              {blockedCards.length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无阻塞项</div>
              )}
            </div>
          </div>

          <div style={{ marginTop: 8, borderTop: '1px solid #f1f5f9', paddingTop: 16, textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              当前关联物料
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {uploadedMaterials.length === 0 ? (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>
                  暂无物料输入
                </div>
              ) : (
                uploadedMaterials.map((item) => (
                  <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                    <Paperclip size={14} color="#64748b" style={{ flexShrink: 0 }} />
                    <span style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, textAlign: 'left' }} title={item.name}>
                      {item.name}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BacklogCard({ icon, item, selectedCardId, setSelectedCardId }) {
  return (
    <div
      onClick={() => setSelectedCardId(item.id)}
      className={`backlog-item ${selectedCardId === item.id ? 'active' : ''}`}
      style={{
        display: 'flex',
        gap: 8,
        padding: 8,
        borderRadius: 8,
        fontSize: 12,
        cursor: 'pointer',
        background: selectedCardId === item.id ? 'var(--bg-hover)' : 'rgba(0,0,0,0.01)',
        border: selectedCardId === item.id ? '1px solid var(--border)' : '1px solid transparent',
        transition: 'all 0.2s',
        textAlign: 'left',
        color: selectedCardId === item.id ? 'var(--text-primary)' : 'var(--text-secondary)',
      }}
    >
      {icon}
      <span style={{ fontWeight: 500 }}>{item.title}</span>
    </div>
  );
}

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
      <input
        placeholder="卡片标题"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        autoFocus
      />
      <textarea
        placeholder="一句话摘要说明..."
        value={desc}
        onChange={(event) => setDesc(event.target.value)}
        rows={3}
      />
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
