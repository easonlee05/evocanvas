import React, { useEffect, useRef, useState } from 'react';
import './Canvas.css';
import { ListTodo, MoreHorizontal, ChevronRight, ChevronDown, ChevronUp, Paperclip, HelpCircle, Scale, AlertTriangle, Sparkles, X, Pin, MousePointer, Square, MoveUpRight, Type } from 'lucide-react';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';
import { apiPost, apiDelete, apiUrl } from '../../api';
import { collectCanvasArrows, getArrowKey, getArrowPresentation, getFocusedRelationColors, getRelatedCardIds } from './canvasRelations.js';
import {
  createInitialCanvasSections,
  describeCanvasMove,
  getCardLocation,
  isMoveAllowed,
  moveCanvasCard,
  SECTION_META,
  updateCanvasCard,
} from './canvasEditing.js';
import {
  getCanvasViewStateStorageKey,
  readStoredCanvasViewState,
} from './workspaceSession';

const LANE_DEFINITIONS = [
  { sectionKey: 'clarify', laneTitle: '待澄清项', clusterTitle: '问题与不确定性' },
  { sectionKey: 'rules', laneTitle: '规则约束', clusterTitle: '核心业务规则' },
  { sectionKey: 'options', laneTitle: '方案与决策', clusterTitle: '备选方案与拍板' },
  { sectionKey: 'evidence', laneTitle: '探索发现', clusterTitle: '原始证据池' },
  { sectionKey: 'problems', laneTitle: '焦点问题', clusterTitle: '问题定义' },
  { sectionKey: 'planning', laneTitle: '落地交接', clusterTitle: '结构化交接物' },
];

function CustomArrow({
  start,
  end,
  transform,
  visualState = 'muted',
  accentColor,
  outIndex = 0,
  outCount = 1,
  inIndex = 0,
  inCount = 1,
  onDelete,
}) {
  const [path, setPath] = useState('');
  const [midPoint, setMidPoint] = useState(null);
  const [isHovered, setIsHovered] = useState(false);
  
  useEffect(() => {
    const update = () => {
      const s = document.getElementById(start);
      const e = document.getElementById(end);
      const container = document.querySelector('.canvas-lanes');
      if (!s || !e || !container) return;
      
      const sRect = s.getBoundingClientRect();
      const eRect = e.getBoundingClientRect();
      const cRect = container.getBoundingClientRect();
      
      const scale = transform.scale;
      const sRight = (sRect.right - cRect.left) / scale;
      const sTop = (sRect.top - cRect.top) / scale;
      const sBottom = (sRect.bottom - cRect.top) / scale;
      const eLeft = (eRect.left - cRect.left) / scale;
      const eRight = (eRect.right - cRect.left) / scale;
      const eTop = (eRect.top - cRect.top) / scale;
      const eBottom = (eRect.bottom - cRect.top) / scale;

      const isSameColumn = Math.abs(sRect.left - eRect.left) < 10;

      const startX = sRight;
      const endX = isSameColumn ? eRight : eLeft;
      const startYBase = (sTop + sBottom) / 2;
      const endYBase = (eTop + eBottom) / 2;
      
      const outOffset = outCount > 1 ? (outIndex - (outCount - 1) / 2) * 16 : 0;
      const startY = startYBase + outOffset;
      
      const inOffset = inCount > 1 ? (inIndex - (inCount - 1) / 2) * 16 : 0;
      const endY = endYBase + inOffset;

      let midX = 0;
      if (isSameColumn) {
        midX = startX + 24 + outIndex * 12;
      } else {
        const midXBase = startX + (endX - startX) / 2;
        const midOffset = (outIndex - inIndex) * 12;
        midX = midXBase + midOffset;
        
        const minMidX = startX + 12;
        const maxMidX = endX - 12;
        if (minMidX < maxMidX) {
          midX = Math.max(minMidX, Math.min(maxMidX, midX));
        } else {
          midX = midXBase;
        }
      }

      setMidPoint({ x: midX, y: (startY + endY) / 2 });

      const signY = endY > startY ? 1 : -1;
      const r = Math.min(12, Math.abs(midX - startX), Math.abs(endX - midX), Math.abs(endY - startY) / 2);

      if (r > 0 && Math.abs(endY - startY) > 2) {
        setPath(
          `M ${startX} ${startY} ` +
          `L ${midX - r} ${startY} ` +
          `Q ${midX} ${startY}, ${midX} ${startY + r * signY} ` +
          `L ${midX} ${endY - r * signY} ` +
          `Q ${midX} ${endY}, ${midX + r} ${endY} ` +
          `L ${endX} ${endY}`
        );
      } else {
        setPath(`M ${startX} ${startY} L ${endX} ${endY}`);
      }
    };

    update();
    const interval = window.setInterval(update, 50);
    return () => window.clearInterval(interval);
  }, [start, end, transform, outIndex, outCount, inIndex, inCount]);

  if (!path) return null;

  let opacity = 1;
  let strokeColor = '#94a3b8';
  let strokeWidth = 1.8;
  const markerId = `arrowhead-${start}-${end}`;

  if (visualState === 'active' || visualState === 'focused') {
    opacity = 1;
    strokeColor = accentColor || '#1f6fff';
    strokeWidth = 2.8;
  } else if (visualState === 'hidden') {
    opacity = 0.18;
    strokeColor = '#cbd5e1';
    strokeWidth = 1.5;
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: 0,
        height: 0,
        overflow: 'visible',
        zIndex: 1
      }}
    >
      <svg 
        className="canvas-arrow-svg"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          overflow: 'visible'
        }}
      >
        <defs>
          <marker id={markerId} markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
            <polygon points="0 0, 6 2, 0 4" fill={strokeColor} />
          </marker>
        </defs>
        <path
          d={path}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          fill="none"
          markerEnd={`url(#${markerId})`}
          style={{ opacity, transition: 'stroke 0.2s, stroke-width 0.2s, opacity 0.2s' }}
        />
        <path
          d={path}
          stroke="transparent"
          strokeWidth="10"
          fill="none"
          style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        />
      </svg>
      {isHovered && midPoint && onDelete && (
        <button
          style={{
            position: 'absolute',
            left: midPoint.x - 10,
            top: midPoint.y - 10,
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: '#ef4444',
            color: '#ffffff',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '10px',
            fontWeight: 'bold',
            lineHeight: 1,
            zIndex: 99,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            pointerEvents: 'auto',
          }}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(start, end);
          }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          title="删除连接线"
        >
          ✕
        </button>
      )}
    </div>
  );
}

function CardPersonaRow({ meta }) {
  if (!meta) return null;
  return (
    <div className="card-persona-row">
      <span className="owner-label">{meta.label || '负责人'}</span>
      <div className={`card-avatar card-avatar-${meta.avatarTone || 'slate'}`}>{meta.avatar}</div>
      <span className="owner-name">{meta.name}</span>
    </div>
  );
}

function StructuredContent({ kind = 'list', items = [] }) {
  if (!items?.length) return null;

  if (kind === 'quote') {
    return (
      <div className="structured-block structured-quote">
        {items.map((item) => (
          <div key={item} className="structured-quote-item">
            <span className="structured-quote-text">{item}</span>
            <span className="structured-quote-mark">”</span>
          </div>
        ))}
      </div>
    );
  }

  if (kind === 'checkpoints') {
    return (
      <div className="structured-block structured-checkpoints">
        {items.map((item) => (
          <div key={`${item.text}-${item.date || ''}`} className="structured-checkpoint-item">
            <span className={`checkpoint-dot checkpoint-dot-${item.state || 'pending'}`} />
            <div className="checkpoint-copy">
              <span className="checkpoint-text">{item.text}</span>
            </div>
            {item.date && <span className="checkpoint-date">{item.date}</span>}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="structured-block structured-list">
      {items.map((item) => (
        <div key={item} className="structured-list-item">
          <span className="fact-dot" />
          <span className="structured-list-text">{item}</span>
        </div>
      ))}
    </div>
  );
}

function CanvasCard({
  data,
  onSelect,
  onPreviewStart,
  onPreviewEnd,
  onStartEdit,
  onSaveEdit,
  editingState,
  isSelectedSelf,
  isSelectedRelated,
  isPreviewSelf,
  isPreviewRelated,
  relationAccent,
  isDimmed,
  onPointerDown,
  onDeleteCard,
  activeCardMenuId,
  setActiveCardMenuId,
  activeTool,
  onConnectStart,
}) {
  const primaryTag = data.tags?.[0];
  const secondaryTags = data.tags?.slice(1) || [];
  const hasTags = primaryTag || data.statusPill;

  const isEditingTitle = editingState?.cardId === data.id && editingState?.field === 'title';
  const isEditingDesc = editingState?.cardId === data.id && editingState?.field === 'desc';

  const cardClassName = `canvas-card${isSelectedSelf ? ' selected-self' : ''}${isSelectedRelated && !isSelectedSelf ? ' selected-related' : ''}${isPreviewSelf ? ' preview-self' : ''}${isPreviewRelated && !isPreviewSelf && !isSelectedRelated ? ' preview-related' : ''}${isDimmed ? ' is-dimmed' : ''}`;

  const anchorBaseStyle = {
    position: 'absolute',
    width: '10px',
    height: '10px',
    background: '#ffffff',
    border: '2px solid #1f6fff',
    borderRadius: '50%',
    zIndex: 10,
    cursor: 'crosshair',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  };

  return (
    <div 
      className={cardClassName} 
      id={data.id}
      onClick={(e) => {
        // 防止在编辑态下误触发 select
        if (editingState?.cardId === data.id) return;
        onSelect(data.id);
      }}
      onMouseEnter={() => onPreviewStart(data.id)}
      onMouseLeave={onPreviewEnd}
      style={relationAccent ? { '--relation-accent': relationAccent } : undefined}
      onPointerDown={onPointerDown}
    >
      <div className="canvas-card-header-group">
        <div className="canvas-card-header">
          <div
            className="canvas-card-title-wrap"
            onClick={(event) => {
              if (editingState?.cardId === data.id) return;
              event.stopPropagation();
              onStartEdit(data.id, 'title', data.title);
            }}
          >
            {isEditingTitle ? (
              <input
                className="canvas-card-title-input"
                type="text"
                autoFocus
                defaultValue={data.title}
                onClick={(event) => event.stopPropagation()}
                onBlur={(event) => onSaveEdit(data.id, 'title', event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    onSaveEdit(data.id, 'title', data.title);
                  }

                  if (event.key === 'Enter') {
                    event.preventDefault();
                    onSaveEdit(data.id, 'title', event.target.value);
                  }
                }}
              />
            ) : (
              <span className="canvas-card-title">{data.title}</span>
            )}
          </div>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <button 
              className="icon-btn" 
              style={{ width: 20, height: 20 }}
              onClick={(event) => {
                event.stopPropagation();
                setActiveCardMenuId(activeCardMenuId === data.id ? null : data.id);
              }}
              title="更多操作"
            >
              <MoreHorizontal size={14} />
            </button>
            {activeCardMenuId === data.id && (
              <div className="card-more-menu" onClick={(event) => event.stopPropagation()}>
                <button 
                  className="card-more-menu-item danger" 
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteCard(data.id);
                    setActiveCardMenuId(null);
                  }}
                >
                  删除卡片
                </button>
              </div>
            )}
          </div>
        </div>

        {hasTags && (
          <div className="card-tags-row">
            {primaryTag && (
              <span className={`canvas-tag tag-${primaryTag.color}`}>{primaryTag.label}</span>
            )}
            {secondaryTags.length > 0 && secondaryTags.map((tag, index) => (
              <span key={index} className={`canvas-tag tag-${tag.color}`}>{tag.label}</span>
            ))}
            {data.statusPill && (
              <span className={`canvas-tag tag-${data.statusPill.color}`}>{data.statusPill.label}</span>
            )}
          </div>
        )}
      </div>

      <div 
        className={`canvas-card-desc-wrap${isEditingDesc ? ' is-editing' : ''}`}
        onClick={(event) => {
          if (editingState?.cardId === data.id) return;
          event.stopPropagation();
          onStartEdit(data.id, 'desc', data.desc || '');
        }}
      >
        {isEditingDesc ? (
          <textarea
            className="canvas-card-desc-input"
            autoFocus
            defaultValue={data.desc || ''}
            onClick={(event) => event.stopPropagation()}
            onBlur={(event) => onSaveEdit(data.id, 'desc', event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.preventDefault();
                onSaveEdit(data.id, 'desc', data.desc || '');
              }

              if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                event.preventDefault();
                onSaveEdit(data.id, 'desc', event.target.value);
              }
            }}
          />
        ) : data.desc ? (
          <div className="canvas-card-desc">{data.desc}</div>
        ) : (
          <div className="canvas-card-desc">点击补充摘要</div>
        )}
      </div>

      <StructuredContent kind={data.structureKind} items={data.structuredItems} />

      {data.attachments && (
        <div className="card-attachments">
          {data.attachments.map((attachment, index) => (
            <div key={index} className="attachment-pill">
              <span className="att-icon">{attachment.icon || '📎'}</span>
              <span title={attachment.label || attachment.name}>{attachment.label || attachment.name}</span>
            </div>
          ))}
        </div>
      )}

      <div className="canvas-card-bottom">
        {(data.source || data.owner) && (
          <div className="card-meta-stack">
            <CardPersonaRow meta={data.source} />
            <CardPersonaRow meta={data.owner} />
          </div>
        )}

        {typeof data.confidence === 'number' && (
          <div className="card-confidence-row">
            <div className="card-confidence-copy">
              <span className="owner-label">置信度</span>
              <span className="confidence-value">{data.confidence}%</span>
            </div>
            <div className="confidence-meter" aria-label={`置信度 ${data.confidence}%`}>
              <div className="confidence-meter-fill" style={{ width: `${data.confidence}%` }} />
            </div>
          </div>
        )}
      </div>

      {activeTool === 'connector' && onConnectStart && (
        <>
          <div 
            style={{ ...anchorBaseStyle, top: '-5px', left: 'calc(50% - 5px)' }} 
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('top', e); }} 
            title="向上连线"
          />
          <div 
            style={{ ...anchorBaseStyle, bottom: '-5px', left: 'calc(50% - 5px)' }} 
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('bottom', e); }} 
            title="向下连线"
          />
          <div 
            style={{ ...anchorBaseStyle, left: '-5px', top: 'calc(50% - 5px)' }} 
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('left', e); }} 
            title="向左连线"
          />
          <div 
            style={{ ...anchorBaseStyle, right: '-5px', top: 'calc(50% - 5px)' }} 
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('right', e); }} 
            title="向右连线"
          />
        </>
      )}
    </div>
  );
}

function TimelineScrubber({ 
  isChatOpen, 
  isPinned = true,
  onPinToggle,
  onDragStart,
  isCollapsedOverride,
  style,
}) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const collapsed = isCollapsedOverride !== undefined ? isCollapsedOverride : isCollapsed;

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
    ...style
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
      onClick={(isPinned && collapsed) ? () => setIsCollapsed(false) : undefined}
      onPointerDown={isPinned ? (e) => e.stopPropagation() : undefined}
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
            whiteSpace: 'nowrap'
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
              cursor: !isPinned ? 'move' : 'default'
            }}
            onPointerDown={!isPinned ? onDragStart : undefined}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>时间轴：项目里程碑</span>
            <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {/* 大头针 Pin 切换 */}
              <button 
                className="icon-btn" 
                onClick={(e) => { e.stopPropagation(); onPinToggle(); }} 
                title={isPinned ? "取消固定，移入画布漂移" : "固定在左下角"}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  color: isPinned ? 'var(--text-primary)' : 'var(--text-secondary)',
                  transition: 'color 0.2s'
                }}
              >
                <Pin size={13} style={!isPinned ? { transform: 'rotate(-45deg)' } : {}} fill={isPinned ? 'var(--text-primary)' : 'none'} />
              </button>
              {isPinned && (
                <button 
                  className="icon-btn" 
                  onClick={(e) => { e.stopPropagation(); setIsCollapsed(true); }} 
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
                <div className="tick-line"></div>
              </div>
              <div className="tick-item" style={{ left: '25%' }}>
                <span className="tick-label">5月</span>
                <div className="tick-line"></div>
              </div>
              <div className="tick-item" style={{ left: '70%' }}>
                <span className="tick-label">6月</span>
                <div className="tick-line"></div>
              </div>
              <div className="tick-item" style={{ left: '92%' }}>
                <span className="tick-label">Q3 - 7月</span>
                <div className="tick-line"></div>
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
                <div className="pointer-line"></div>
                <span className="pointer-label">当前日期：5月18日</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ActiveBacklogPanel({
  isChatOpen,
  isPinned = true,
  onPinToggle,
  onDragStart,
  canvasSections = {},
  selectedCardId,
  setSelectedCardId,
  uploadedMaterials = [],
  style,
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  // 活跃项计数
  const activeCount = (Object.values(canvasSections).flat().filter(c => c.kind === 'clarification' && ['open', 'draft', 'pending', 'active'].includes(c.status)).length +
    Object.values(canvasSections).flat().filter(c => c.kind === 'decision' && ['pending', 'active', 'draft'].includes(c.status)).length +
    Object.values(canvasSections).flat().filter(c => c.status === 'blocked').length);

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
    ...style
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
      onClick={(isPinned && isCollapsed) ? () => setIsCollapsed(false) : undefined}
      onPointerDown={isPinned ? (e) => e.stopPropagation() : undefined}
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
            whiteSpace: 'nowrap'
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
              cursor: !isPinned ? 'move' : 'default'
            }}
            onPointerDown={!isPinned ? onDragStart : undefined}
          >
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
              <ListTodo size={16} color="var(--text-secondary)" /> 活跃缺口看板
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="canvas-badge" style={{ 
                fontSize: 10, 
                padding: '2px 6px',
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)',
                borderRadius: '4px',
                fontWeight: '600'
              }}>
                {activeCount} 活跃
              </span>
              <button 
                onClick={(e) => { e.stopPropagation(); onPinToggle(); }}
                title={isPinned ? "取消固定，移入画布漂移" : "固定在右上角"}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 2,
                  display: 'flex',
                  alignItems: 'center',
                  color: isPinned ? 'var(--text-primary)' : 'var(--text-secondary)',
                  transition: 'color 0.2s'
                }}
              >
                <Pin size={13} style={!isPinned ? { transform: 'rotate(-45deg)' } : {}} fill={isPinned ? 'var(--text-primary)' : 'none'} />
              </button>
              {isPinned && (
                <button 
                  onClick={(e) => { e.stopPropagation(); setIsCollapsed(true); }}
                  title="收起看板"
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 2,
                    display: 'flex',
                    alignItems: 'center',
                    color: 'var(--text-tertiary)'
                  }}
                >
                  <ChevronDown size={14} className="text-tertiary" />
                </button>
              )}
            </div>
          </div>

          {/* 1. 待澄清问题 */}
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              待澄清问题 (Clarification)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.values(canvasSections).flat()
                .filter(c => c.kind === 'clarification' && ['open', 'draft', 'pending', 'active'].includes(c.status))
                .map(item => (
                  <div 
                    key={item.id}
                    onClick={() => setSelectedCardId(item.id)}
                    className={`backlog-item ${selectedCardId === item.id ? 'active' : ''}`}
                    style={{
                      display: 'flex', gap: 8, padding: 8, borderRadius: 8, fontSize: 12,
                      cursor: 'pointer', 
                      background: selectedCardId === item.id ? 'var(--bg-hover)' : 'rgba(0,0,0,0.01)',
                      border: selectedCardId === item.id ? '1px solid var(--border)' : '1px solid transparent',
                      transition: 'all 0.2s', textAlign: 'left',
                      color: selectedCardId === item.id ? 'var(--text-primary)' : 'var(--text-secondary)'
                    }}
                  >
                    <HelpCircle size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />
                    <span style={{ fontWeight: 500 }}>{item.title}</span>
                  </div>
                ))}
              {Object.values(canvasSections).flat().filter(c => c.kind === 'clarification' && ['open', 'draft', 'pending', 'active'].includes(c.status)).length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无活跃待澄清</div>
              )}
            </div>
          </div>

          {/* 2. 待决策拍板 */}
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              待决策事项 (Decision)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.values(canvasSections).flat()
                .filter(c => c.kind === 'decision' && ['pending', 'active', 'draft'].includes(c.status))
                .map(item => (
                  <div 
                    key={item.id}
                    onClick={() => setSelectedCardId(item.id)}
                    className={`backlog-item ${selectedCardId === item.id ? 'active' : ''}`}
                    style={{
                      display: 'flex', gap: 8, padding: 8, borderRadius: 8, fontSize: 12,
                      cursor: 'pointer', 
                      background: selectedCardId === item.id ? 'var(--bg-hover)' : 'rgba(0,0,0,0.01)',
                      border: selectedCardId === item.id ? '1px solid var(--border)' : '1px solid transparent',
                      transition: 'all 0.2s', textAlign: 'left',
                      color: selectedCardId === item.id ? 'var(--text-primary)' : 'var(--text-secondary)'
                    }}
                  >
                    <Scale size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />
                    <span style={{ fontWeight: 500 }}>{item.title}</span>
                  </div>
                ))}
              {Object.values(canvasSections).flat().filter(c => c.kind === 'decision' && ['pending', 'active', 'draft'].includes(c.status)).length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无活跃决策</div>
              )}
            </div>
          </div>

          {/* 3. 阻塞项 */}
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
              阻塞项 (Blocked)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.values(canvasSections).flat()
                .filter(c => c.status === 'blocked')
                .map(item => (
                  <div 
                    key={item.id}
                    onClick={() => setSelectedCardId(item.id)}
                    className={`backlog-item ${selectedCardId === item.id ? 'active' : ''}`}
                    style={{
                      display: 'flex', gap: 8, padding: 8, borderRadius: 8, fontSize: 12,
                      cursor: 'pointer', 
                      background: selectedCardId === item.id ? 'var(--bg-hover)' : 'rgba(0,0,0,0.01)',
                      border: selectedCardId === item.id ? '1px solid var(--border)' : '1px solid transparent',
                      transition: 'all 0.2s', textAlign: 'left',
                      color: selectedCardId === item.id ? 'var(--text-primary)' : 'var(--text-secondary)'
                    }}
                  >
                    <AlertTriangle size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />
                    <span style={{ fontWeight: 500 }}>{item.title}</span>
                  </div>
                ))}
              {Object.values(canvasSections).flat().filter(c => c.status === 'blocked').length === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无阻塞项</div>
              )}
            </div>
          </div>

          {/* 4. 来源物料 */}
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
                uploadedMaterials.map(m => (
                  <div key={m.id} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: 6,
                    fontSize: 12, color: 'var(--text-secondary)'
                  }}>
                    <Paperclip size={14} color="#64748b" style={{ flexShrink: 0 }} />
                    <span style={{
                      fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1,
                      textAlign: 'left'
                    }} title={m.name}>{m.name}</span>
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

function estimateCardHeight(card) {
  let height = 32; // 上下 padding (16 * 2)

  // 1. Header (标题 + Tags)
  const titleLen = card.title?.length || 0;
  const titleRows = Math.max(1, Math.ceil(titleLen / 13)); // 一行约 13 个汉字
  height += titleRows * 20;
  
  const hasTags = card.tags?.length > 0 || card.statusPill;
  if (hasTags) {
    height += 24;
    height += 8;
  }
  height += 8;

  // 2. Description (摘要)
  if (card.desc) {
    const descLen = card.desc.length;
    const descRows = Math.max(1, Math.ceil(descLen / 15)); // 一行约 15 个汉字
    height += descRows * 18;
  } else {
    height += 18;
  }
  height += 8;

  // 3. StructuredContent (结构化列表)
  if (card.structuredItems && card.structuredItems.length > 0) {
    const itemCount = card.structuredItems.length;
    let structHeight = 16;
    if (card.structureKind === 'quote') {
      structHeight += itemCount * 40;
    } else if (card.structureKind === 'checkpoints') {
      structHeight += itemCount * 38;
    } else {
      structHeight += itemCount * 28;
    }
    height += structHeight;
    height += 8;
  }

  // 4. Attachments (附件)
  if (card.attachments && card.attachments.length > 0) {
    height += 32;
    height += 8;
  }

  // 5. Bottom (Meta 信息 / 置信度)
  let bottomHeight = 0;
  if (card.source) bottomHeight += 24;
  if (card.owner) bottomHeight += 24;
  if (typeof card.confidence === 'number') bottomHeight += 32;
  if (bottomHeight > 0) {
    height += bottomHeight;
    height += 8;
  }

  // 引入 1.15 的高度安全膨胀系数，并加上 24px 的保底高度
  const finalHeight = Math.round(height * 1.15) + 24;

  return Math.max(160, finalHeight);
}

function resolveCollisions(positions, allCards) {
  const resolved = {};
  allCards.forEach(card => {
    resolved[card.id] = positions[card.id] ? { ...positions[card.id] } : { x: 0, y: 0 };
  });

  const VERTICAL_GAP = 28;

  const columns = [];
  allCards.forEach(card => {
    const pos = resolved[card.id];
    let placed = false;
    for (const col of columns) {
      if (Math.abs(col[0].x - pos.x) < 220) {
        col.push({ id: card.id, x: pos.x, y: pos.y, height: estimateCardHeight(card) });
        placed = true;
        break;
      }
    }
    if (!placed) {
      columns.push([{ id: card.id, x: pos.x, y: pos.y, height: estimateCardHeight(card) }]);
    }
  });

  columns.forEach(col => {
    col.sort((a, b) => a.y - b.y);

    for (let i = 1; i < col.length; i++) {
      const prev = col[i - 1];
      const curr = col[i];

      const prevBottom = prev.y + prev.height + VERTICAL_GAP;
      if (curr.y < prevBottom) {
        curr.y = Math.ceil(prevBottom / 24) * 24;
        resolved[curr.id].y = curr.y;
      }
    }
  });

  return resolved;
}

function buildCompactSectionLayout(canvasSections) {
  const SECTION_LAYOUT = {
    evidence: { x: 72, y: 88 },
    rules: { x: 472, y: 88 },
    planning: { x: 872, y: 88 },
    problems: { x: 472, y: 356 },
    clarify: { x: 472, y: 648 },
    options: { x: 872, y: 356 },
  };
  const CARD_WIDTH = 320;
  const CARD_GAP = 24;
  const COLUMN_WRAP_THRESHOLD = 4;
  const COLUMN_OFFSET_X = 352;

  const positions = {};

  Object.entries(canvasSections).forEach(([sectionKey, sectionCards]) => {
    const anchor = SECTION_LAYOUT[sectionKey] || { x: 72, y: 88 };
    let columnIndex = 0;
    let cursorY = anchor.y;

    sectionCards.forEach((card, index) => {
      if (index > 0 && index % COLUMN_WRAP_THRESHOLD === 0) {
        columnIndex += 1;
        cursorY = anchor.y;
      }

      positions[card.id] = {
        x: anchor.x + columnIndex * COLUMN_OFFSET_X,
        y: cursorY,
      };

      cursorY += estimateCardHeight(card) + CARD_GAP;
    });
  });

  return positions;
}

function getCanvasBounds(cardPositions, cards) {
  let maxX = 1440;
  let maxY = 960;

  cards.forEach((card) => {
    const pos = cardPositions[card.id];
    if (!pos) return;

    maxX = Math.max(maxX, pos.x + 320 + 160);
    maxY = Math.max(maxY, pos.y + estimateCardHeight(card) + 200);
  });

  return { width: maxX, height: maxY };
}

export default function Canvas({ 
  isChatOpen = true,
  workspaceId,
  cards = [],
  relations = [],
  todos = [],
  confirmations = [],
  selectedCardId,
  setSelectedCardId,
  onRefresh,
  uploadedMaterials = [],
}) {
  const [viewMode, setViewMode] = useState('convergence'); // convergence | problem | option | decision | handoff
  const [activeTool, setActiveTool] = useState('select'); // select | card | connector | text
  const [activeConnector, setActiveConnector] = useState(null); // { startCardId, startPort, endX, endY }
  const [canvasTexts, setCanvasTexts] = useState([]);
  const [creatorState, setCreatorState] = useState(null); // { x, y, canvasX, canvasY, stage }
  const [isBacklogOpen, setIsBacklogOpen] = useState(true);
  const [cardOffsets, setCardOffsets] = useState({});
  const [isPinned, setIsPinned] = useState(true);
  const [timelinePos, setTimelinePos] = useState({ x: 80, y: 800 });
  const [isBacklogPinned, setIsBacklogPinned] = useState(true);
  const [backlogPos, setBacklogPos] = useState({ x: 1200, y: 300 });
  const [activeCardMenuId, setActiveCardMenuId] = useState(null);

  const [canvasSections, setCanvasSections] = useState(() => createInitialCanvasSections(DEMO_CANVAS_SECTIONS));
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [hoveredCardId, setHoveredCardId] = useState(null);
  const [editingState, setEditingState] = useState(null);
  const [draggingCardId, setDraggingCardId] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [moveError, setMoveError] = useState(null);
  const [hasHydratedCanvasView, setHasHydratedCanvasView] = useState(false);
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const dragSession = useRef(null);
  const hasRestoredViewStateRef = useRef(false);

  const canvasViewStorageKey = getCanvasViewStateStorageKey(workspaceId);

  function mapSectionToBackendStage(sectionKey) {
    if (sectionKey === 'evidence') return 'discovery';
    if (sectionKey === 'problems' || sectionKey === 'clarify' || sectionKey === 'rules' || sectionKey === 'options') return 'define';
    if (sectionKey === 'planning') return 'handoff';
    return sectionKey;
  }

  function mapBackendCardsToSections(backendCards, backendRelations) {
    const sections = {
      evidence: [],
      problems: [],
      clarify: [],
      rules: [],
      options: [],
      planning: [],
    };

    const nextMap = {};
    (backendRelations || []).forEach(rel => {
      const sourceId = rel.from_card_id || rel.source_id;
      const targetId = rel.to_card_id || rel.target_id;
      if (sourceId && targetId) {
        if (!nextMap[sourceId]) nextMap[sourceId] = [];
        nextMap[sourceId].push(targetId);
      }
    });

    (backendCards || []).forEach(card => {
      let sectionKey = 'evidence';
      if (card.kind === 'problem') sectionKey = 'problems';
      else if (card.kind === 'clarification') sectionKey = 'clarify';
      else if (card.kind === 'constraint') sectionKey = 'rules';
      else if (card.kind === 'decision' || card.kind === 'option') sectionKey = 'options';
      else if (card.kind === 'handoff') sectionKey = 'planning';

      const mappedTags = (card.tags || []).map(t => {
        let col = 'slate';
        if (t.color === 'red') col = 'red';
        else if (t.color === 'yellow') col = 'orange';
        else if (t.color === 'blue') col = 'blue';
        else if (t.color === 'green') col = 'green';
        else if (t.color === 'purple') col = 'purple';
        return { label: t.label, color: col };
      });

      sections[sectionKey].push({
        id: card.id,
        kind: card.kind,
        title: card.title,
        desc: card.summary || card.desc,
        tags: mappedTags,
        status: card.status,
        confidence: card.confidence,
        structureKind: card.metadata?.structured_kind || 'list',
        structuredItems: card.metadata?.structured_items || [],
        next: nextMap[card.id] || [],
        source: card.metadata?.source_persona ? {
          label: '来源',
          name: card.metadata.source_persona.name,
          avatar: card.metadata.source_persona.avatar || card.metadata.source_persona.name?.[0],
          avatarTone: card.metadata.source_persona.avatar_tone || 'slate'
        } : null,
        owner: card.metadata?.owner_persona ? {
          label: card.metadata.owner_persona.label || '负责人',
          name: card.metadata.owner_persona.name,
          avatar: card.metadata.owner_persona.avatar || card.metadata.owner_persona.name?.[0],
          avatarTone: card.metadata.owner_persona.avatar_tone || 'slate'
        } : null
      });
    });

    return sections;
  }

  useEffect(() => {
    if (workspaceId === 'demo') {
      setCanvasSections({
        options: [],
        ...createInitialCanvasSections(DEMO_CANVAS_SECTIONS)
      });
      return;
    }

    if (cards && cards.length > 0) {
      setCanvasSections(current => {
        const storedState = readStoredCanvasViewState(canvasViewStorageKey) || {};
        const deletedCardIds = new Set(storedState.deletedCardIds || []);
        
        const filteredBackendCards = cards.filter(c => !deletedCardIds.has(c.id));
        const backendSections = mapBackendCardsToSections(filteredBackendCards, relations);

        const allCurrentCards = Object.values(current).flat();
        if (allCurrentCards.length === 0) {
          return backendSections;
        }

        const localCardIds = new Set(allCurrentCards.map(c => c.id));
        const newBackendCards = filteredBackendCards.filter(c => !localCardIds.has(c.id));

        if (newBackendCards.length === 0) {
          return current;
        }

        const nextSections = { ...current };
        const newSections = mapBackendCardsToSections(newBackendCards, relations);

        Object.entries(newSections).forEach(([key, newCards]) => {
          nextSections[key] = [...(nextSections[key] || []), ...newCards];
        });

        return nextSections;
      });
    } else {
      setCanvasSections(current => {
        const allCurrentCards = Object.values(current).flat();
        if (allCurrentCards.length === 0) {
          return {
            evidence: [],
            problems: [],
            clarify: [],
            rules: [],
            options: [],
            planning: [],
          };
        }
        return current;
      });
    }
  }, [cards, relations, workspaceId, canvasViewStorageKey]);

  useEffect(() => {
    hasRestoredViewStateRef.current = false;
    setHasHydratedCanvasView(false);
    setIsBacklogOpen(true);
    setCardOffsets({});
    setIsPinned(true);
    setTimelinePos({ x: 80, y: 800 });
    setIsBacklogPinned(true);
    setBacklogPos({ x: 1200, y: 300 });
    setTransform({ x: 0, y: 0, scale: 1 });
    setCanvasTexts([]);
  }, [workspaceId]);

  useEffect(() => {
    if (hasRestoredViewStateRef.current) return;

    const storedState = readStoredCanvasViewState(canvasViewStorageKey);
    if (!storedState) {
      hasRestoredViewStateRef.current = true;
      setHasHydratedCanvasView(true);
      return;
    }

    if (typeof storedState.isBacklogOpen === 'boolean') {
      setIsBacklogOpen(storedState.isBacklogOpen);
    }

    if (
      storedState.cardOffsets &&
      typeof storedState.cardOffsets === 'object' &&
      !Array.isArray(storedState.cardOffsets)
    ) {
      setCardOffsets(storedState.cardOffsets);
    }

    if (typeof storedState.isPinned === 'boolean') {
      setIsPinned(storedState.isPinned);
    }

    if (
      storedState.timelinePos &&
      typeof storedState.timelinePos.x === 'number' &&
      typeof storedState.timelinePos.y === 'number'
    ) {
      setTimelinePos(storedState.timelinePos);
    }

    if (typeof storedState.isBacklogPinned === 'boolean') {
      setIsBacklogPinned(storedState.isBacklogPinned);
    }

    if (
      storedState.backlogPos &&
      typeof storedState.backlogPos.x === 'number' &&
      typeof storedState.backlogPos.y === 'number'
    ) {
      setBacklogPos(storedState.backlogPos);
    }

    if (
      storedState.transform &&
      typeof storedState.transform.x === 'number' &&
      typeof storedState.transform.y === 'number' &&
      typeof storedState.transform.scale === 'number'
    ) {
      setTransform(storedState.transform);
    }

    if (
      storedState.canvasSections &&
      typeof storedState.canvasSections === 'object' &&
      !Array.isArray(storedState.canvasSections)
    ) {
      setCanvasSections(storedState.canvasSections);
    }

    if (Array.isArray(storedState.canvasTexts)) {
      setCanvasTexts(storedState.canvasTexts);
    } else {
      setCanvasTexts([]);
    }

    hasRestoredViewStateRef.current = true;
    setHasHydratedCanvasView(true);
  }, [canvasViewStorageKey]);

  useEffect(() => {
    if (!canvasViewStorageKey || !hasHydratedCanvasView) return;

    const currentState = readStoredCanvasViewState(canvasViewStorageKey) || {};
    const nextState = {
      ...currentState,
      isBacklogOpen,
      cardOffsets,
      isPinned,
      timelinePos,
      isBacklogPinned,
      backlogPos,
      transform,
      canvasSections,
      canvasTexts,
    };
    localStorage.setItem(canvasViewStorageKey, JSON.stringify(nextState));
  }, [canvasViewStorageKey, hasHydratedCanvasView, isBacklogOpen, cardOffsets, isPinned, timelinePos, isBacklogPinned, backlogPos, transform, canvasSections, canvasTexts]);

  const handleAutoLayout = () => {
    setCardOffsets({});
    setTimelinePos({ x: 80, y: 800 });
    setBacklogPos({ x: 1200, y: 300 });
    setTransform({ x: 0, y: 0, scale: 1 });
  };

  const containerRef = useRef(null);
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (event) => {
      event.preventDefault();
      
      const rect = container.getBoundingClientRect();
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;

      const canvasX = (mouseX - transform.x) / transform.scale;
      const canvasY = (mouseY - transform.y) / transform.scale;

      const scaleFactor = 1.1;
      let newScale = transform.scale;
      if (event.deltaY < 0) {
        newScale = Math.min(newScale * scaleFactor, 3);
      } else {
        newScale = Math.max(newScale / scaleFactor, 0.2);
      }

      const newX = mouseX - canvasX * newScale;
      const newY = mouseY - canvasY * newScale;

      setTransform({ x: newX, y: newY, scale: newScale });
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, [transform]);

  const handlePointerDown = (event) => {
    setActiveCardMenuId(null);
    if (event.button !== 0) return;
    if (draggingCardId) return;

    if (activeTool === 'card') {
      event.stopPropagation();
      const rect = containerRef.current.getBoundingClientRect();
      const clientX = event.clientX;
      const clientY = event.clientY;
      const canvasX = (clientX - rect.left - transform.x) / transform.scale;
      const canvasY = (clientY - rect.top - transform.y) / transform.scale;
      
      let stage = 'discovery';
      if (canvasX > 400 && canvasX < 850) stage = 'define';
      else if (canvasX >= 850) stage = 'handoff';

      setCreatorState({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        canvasX,
        canvasY,
        stage
      });
      return;
    }

    if (activeTool === 'text') {
      event.stopPropagation();
      const rect = containerRef.current.getBoundingClientRect();
      const clientX = event.clientX;
      const clientY = event.clientY;
      const canvasX = (clientX - rect.left - transform.x) / transform.scale;
      const canvasY = (clientY - rect.top - transform.y) / transform.scale;

      const newText = {
        id: 'text-' + Date.now(),
        x: canvasX,
        y: canvasY,
        text: '',
        isEditing: true
      };

      setCanvasTexts(prev => [...prev, newText]);
      setActiveTool('select');
      return;
    }

    if (activeTool !== 'select') return;
    
    let target = event.target;
    while (target && target !== containerRef.current) {
      if (target.className?.includes?.('canvas-card') || target.className?.includes?.('timeline-scrubber') || target.tagName === 'BUTTON' || target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.className?.includes?.('canvas-text-label')) {
        return;
      }
      target = target.parentNode;
    }

    if (selectedCardId !== null) {
      setSelectedCardId(null);
    }

    isDragging.current = true;
    dragStart.current = {
      x: event.clientX - transform.x,
      y: event.clientY - transform.y
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event) => {
    if (!isDragging.current) return;
    const newX = event.clientX - dragStart.current.x;
    const newY = event.clientY - dragStart.current.y;
    setTransform(prev => ({ ...prev, x: newX, y: newY }));
  };

  const handlePointerUp = (event) => {
    if (isDragging.current) {
      isDragging.current = false;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const beginFreeDrag = (type, id, event) => {
    if (activeTool !== 'select') return;
    if (editingState?.cardId) return;
    if (event.target.closest('button, input, textarea')) return;
    event.stopPropagation();
    setSelectedCardId((current) => (type === 'card' ? (current === id ? current : id) : current));
    if (type === 'card') setDraggingCardId(id);

    let source;
    if (type === 'card') {
      source = cardOffsets[id] || { x: 0, y: 0 };
    } else if (type === 'timeline') {
      source = timelinePos;
    } else if (type === 'backlog') {
      source = backlogPos;
    } else if (type === 'text') {
      const textItem = canvasTexts.find(t => t.id === id);
      source = textItem ? { x: textItem.x, y: textItem.y } : { x: 0, y: 0 };
    }

    dragSession.current = {
      type,
      id,
      pointerX: event.clientX,
      pointerY: event.clientY,
      startX: source.x,
      startY: source.y,
    };
  };

  const hoveredCardIdRef = useRef(null);
  useEffect(() => {
    hoveredCardIdRef.current = hoveredCardId;
  }, [hoveredCardId]);

  useEffect(() => {
    const handleWindowPointerMove = (event) => {
      const session = dragSession.current;
      if (!session) return;

      const deltaX = (event.clientX - session.pointerX) / transform.scale;
      const deltaY = (event.clientY - session.pointerY) / transform.scale;

      if (session.type === 'card') {
        setCardOffsets((current) => ({
          ...current,
          [session.id]: {
            x: session.startX + deltaX,
            y: session.startY + deltaY,
          },
        }));
      } else if (session.type === 'timeline') {
        setTimelinePos({
          x: session.startX + deltaX,
          y: session.startY + deltaY,
        });
      } else if (session.type === 'backlog') {
        setBacklogPos({
          x: session.startX + deltaX,
          y: session.startY + deltaY,
        });
      } else if (session.type === 'text') {
        setCanvasTexts((current) => current.map(t => t.id === session.id ? {
          ...t,
          x: session.startX + deltaX,
          y: session.startY + deltaY,
        } : t));
      } else if (session.type === 'connector') {
        const lanesEl = document.querySelector('.canvas-lanes');
        if (lanesEl) {
          const lanesRect = lanesEl.getBoundingClientRect();
          const endX = (event.clientX - lanesRect.left) / transform.scale;
          const endY = (event.clientY - lanesRect.top) / transform.scale;
          setActiveConnector(prev => prev ? { ...prev, endX, endY } : null);
        }
      }
    };

    const handleWindowPointerUp = () => {
      const session = dragSession.current;
      if (session && session.type === 'connector') {
        const targetId = hoveredCardIdRef.current;
        if (targetId && targetId !== session.startCardId) {
          handleAddConnection(session.startCardId, targetId);
        }
        setActiveConnector(null);
        setActiveTool('select');
      }

      dragSession.current = null;
      setDraggingCardId(null);
    };

    window.addEventListener('pointermove', handleWindowPointerMove);
    window.addEventListener('pointerup', handleWindowPointerUp);
    return () => {
      window.removeEventListener('pointermove', handleWindowPointerMove);
      window.removeEventListener('pointerup', handleWindowPointerUp);
    };
  }, [transform.scale, cardOffsets, timelinePos, canvasTexts]);

  const startEdit = (cardId, field, currentValue) => {
    setEditingState({ cardId, field, value: currentValue });
  };

  const saveEdit = async (cardId, field, newValue) => {
    if (!editingState) return;
    setEditingState(null);

    const allCards = Object.values(canvasSections).flat();
    const targetCard = allCards.find(c => c.id === cardId);
    if (!targetCard) return;

    if (newValue.trim() === (targetCard[field] || '').trim()) return;

    setCanvasSections((current) =>
      updateCanvasCard(current, cardId, { [field]: newValue }),
    );

    if (workspaceId && workspaceId !== 'demo') {
      try {
        await apiPost(`/api/canvas/workspaces/${workspaceId}/cards/${cardId}`, {
          title: field === 'title' ? newValue : targetCard.title,
          summary: field === 'desc' ? newValue : targetCard.desc,
          kind: targetCard.kind,
          status: targetCard.status,
        }, null);
        if (onRefresh) onRefresh();
      } catch (err) {
        setMoveError('保存修改失败，请刷新页面');
      }
    }
  };

  const handleAddConnection = (startId, endId) => {
    setCanvasSections(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(key => {
        next[key] = next[key].map(c => {
          if (c.id === startId) {
            const currentNext = Array.isArray(c.next) ? c.next : (c.next ? [c.next] : []);
            if (!currentNext.includes(endId)) {
              return {
                ...c,
                next: [...currentNext, endId]
              };
            }
          }
          return c;
        });
      });
      return next;
    });
  };

  const handleDeleteConnection = (startId, endId) => {
    setCanvasSections(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(key => {
        next[key] = next[key].map(c => {
          if (c.id === startId && c.next) {
            return {
              ...c,
              next: (Array.isArray(c.next) ? c.next : [c.next]).filter(id => id !== endId)
            };
          }
          return c;
        });
      });
      return next;
    });
  };

  const handleConnectStart = (cardId, port, event) => {
    event.stopPropagation();
    event.preventDefault();
    const lanesEl = document.querySelector('.canvas-lanes');
    if (!lanesEl) return;

    const lanesRect = lanesEl.getBoundingClientRect();
    const currentX = (event.clientX - lanesRect.left) / transform.scale;
    const currentY = (event.clientY - lanesRect.top) / transform.scale;

    setActiveConnector({
      startCardId: cardId,
      startPort: port,
      endX: currentX,
      endY: currentY,
    });

    dragSession.current = {
      type: 'connector',
      startCardId: cardId,
      startPort: port,
      pointerX: event.clientX,
      pointerY: event.clientY,
    };
  };

  const handleCreateCardSubmit = async (formData) => {
    if (!formData.title) return;
    const { title, desc, kind } = formData;
    const { canvasX, canvasY } = creatorState;
    setCreatorState(null);
    setActiveTool('select');

    let backendKind = 'evidence';
    if (kind === 'problems') backendKind = 'problem';
    else if (kind === 'clarify') backendKind = 'clarification';
    else if (kind === 'rules') backendKind = 'constraint';
    else if (kind === 'options') backendKind = 'decision';
    else if (kind === 'planning') backendKind = 'handoff';

    const tempId = `temp-${Date.now()}`;
    const newLocalCard = {
      id: tempId,
      kind: backendKind,
      title,
      desc,
      tags: [],
      status: 'open',
      structuredItems: [],
      next: []
    };

    setCanvasSections(prev => ({
      ...prev,
      [kind]: [...(prev[kind] || []), newLocalCard]
    }));

    setCardOffsets(prev => ({
      ...prev,
      [tempId]: { x: canvasX - 160, y: canvasY - 80 }
    }));

    if (workspaceId && workspaceId !== 'demo') {
      try {
        const res = await apiPost(`/api/canvas/workspaces/${workspaceId}/cards`, {
          kind: backendKind,
          title,
          summary: desc,
          stage: mapSectionToBackendStage(kind)
        });
        if (res && res.card_id) {
          setCardOffsets(prev => {
            const next = { ...prev };
            next[res.card_id] = next[tempId];
            delete next[tempId];
            return next;
          });
          setCanvasSections(prev => {
            const next = { ...prev };
            next[kind] = next[kind].map(c => c.id === tempId ? { ...c, id: res.card_id } : c);
            return next;
          });
        }
        if (onRefresh) onRefresh();
      } catch (err) {
        console.warn("保存新增卡片到后端失败，将在本地保留", err);
      }
    }
  };

  const handleDeleteCard = async (cardId) => {
    if (!window.confirm("确定要删除这张卡片吗？相关的关联关系也会一并被断开。")) return;

    setCanvasSections(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(key => {
        next[key] = next[key].filter(c => c.id !== cardId).map(c => {
          if (c.next) {
            return {
              ...c,
              next: (Array.isArray(c.next) ? c.next : [c.next]).filter(id => id !== cardId)
            };
          }
          return c;
        });
      });
      return next;
    });

    const currentState = readStoredCanvasViewState(canvasViewStorageKey) || {};
    const deletedCardIds = currentState.deletedCardIds || [];
    if (!deletedCardIds.includes(cardId)) {
      deletedCardIds.push(cardId);
      localStorage.setItem(canvasViewStorageKey, JSON.stringify({
        ...currentState,
        deletedCardIds,
      }));
    }

    if (workspaceId && workspaceId !== 'demo') {
      try {
        await apiDelete(`/api/canvas/workspaces/${workspaceId}/cards/${cardId}`);
        if (onRefresh) onRefresh();
      } catch (err) {
        console.warn("在后端删除卡片失败，已在本地做删除处理", err);
      }
    }
  };

  const checkCardActiveState = (cardId) => {
    const activeId = selectedCardId || hoveredCardId;
    if (!activeId) {
      return { isSelectedSelf: false, isSelectedRelated: false, isPreviewSelf: false, isPreviewRelated: false };
    }

    const allArrows = collectCanvasArrows(canvasSections);
    const selectedRelatedCardIds = getRelatedCardIds(selectedCardId, allArrows);
    const previewRelatedCardIds = getRelatedCardIds(hoveredCardId, allArrows);

    const isSelectedSelf = selectedCardId === cardId;
    const isSelectedRelated = selectedRelatedCardIds.has(cardId);
    const isPreviewSelf = hoveredCardId === cardId;
    const isPreviewRelated = previewRelatedCardIds.has(cardId);

    return { isSelectedSelf, isSelectedRelated, isPreviewSelf, isPreviewRelated };
  };

  const getCardRelationAccent = (cardId) => {
    const activeId = selectedCardId || hoveredCardId;
    if (!activeId || activeId === cardId) return null;

    const allArrows = collectCanvasArrows(canvasSections);
    const activeRelationColors = getFocusedRelationColors(allArrows, activeId);
    return activeRelationColors[cardId] || null;
  };

  const focusedCardId = selectedCardId;
  const allArrows = collectCanvasArrows(canvasSections);
  const selectedRelatedCardIds = getRelatedCardIds(selectedCardId, allArrows);
  const previewRelatedCardIds = new Set();
  const relationColors = getFocusedRelationColors(allArrows, focusedCardId);

  const renderCard = (card) => {
    const { isSelectedSelf, isSelectedRelated, isPreviewSelf, isPreviewRelated } = checkCardActiveState(card.id);
    const offset = cardOffsets[card.id] || { x: 0, y: 0 };

    const isDimmed = (() => {
      if (viewMode === 'convergence') return false;
      if (viewMode === 'problem') return card.kind !== 'problem' && card.kind !== 'clarification';
      if (viewMode === 'option') return card.kind !== 'option' && card.kind !== 'constraint';
      if (viewMode === 'decision') return card.kind !== 'decision';
      if (viewMode === 'handoff') return card.kind !== 'handoff';
      return false;
    })();

    return (
      <div
        key={card.id}
        className={`canvas-card-slot${draggingCardId === card.id ? ' is-dragging' : ''}`}
        style={{ transform: `translate(${offset.x}px, ${offset.y}px)` }}
      >
        <CanvasCard
          data={card}
          onSelect={(cardId) => setSelectedCardId(cardId)}
          onPreviewStart={(cardId) => setHoveredCardId(cardId)}
          onPreviewEnd={() => setHoveredCardId(null)}
          onStartEdit={startEdit}
          onSaveEdit={saveEdit}
          editingState={editingState?.cardId === card.id ? editingState : null}
          isSelectedSelf={isSelectedSelf}
          isSelectedRelated={isSelectedRelated}
          isPreviewSelf={isPreviewSelf}
          isPreviewRelated={isPreviewRelated}
          relationAccent={getCardRelationAccent(card.id)}
          isDimmed={isDimmed}
          onPointerDown={(event) => beginFreeDrag('card', card.id, event)}
          onDeleteCard={handleDeleteCard}
          activeCardMenuId={activeCardMenuId}
          setActiveCardMenuId={setActiveCardMenuId}
          activeTool={activeTool}
          onConnectStart={handleConnectStart}
        />
      </div>
    );
  };

  return (
    <div 
      className="canvas-container" 
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        backgroundPosition: `${transform.x}px ${transform.y}px`,
        backgroundSize: `${24 * transform.scale}px ${24 * transform.scale}px`,
        cursor: activeTool === 'select' 
          ? (isDragging.current ? 'grabbing' : 'grab') 
          : (activeTool === 'text' ? 'text' : 'crosshair')
      }}
    >
      {/* 顶部操作提示 */}
      {activeTool !== 'select' && (
        <div className="active-tool-hint">
          {activeTool === 'card' && '卡片工具激活：点击画布空白处以添加新卡片'}
          {activeTool === 'connector' && '连接线工具激活：拖动卡片边缘锚点以建立关联'}
          {activeTool === 'text' && '文本工具激活：点击画布空白处添加注释文本'}
        </div>
      )}

      {creatorState && (
        <CardCreatorBubble 
          x={creatorState.x} 
          y={creatorState.y} 
          stage={creatorState.stage}
          onClose={() => {
            setCreatorState(null);
            setActiveTool('select');
          }} 
          onSubmit={handleCreateCardSubmit} 
        />
      )}

      {/* 底部悬浮工具栏 */}
      <div className="figma-toolbar" onClick={(e) => e.stopPropagation()}>
        <button
          className={`figma-toolbar-btn${activeTool === 'select' ? ' active' : ''}`}
          title="选择与拖拽 (V)"
          onClick={() => setActiveTool('select')}
        >
          <MousePointer size={16} />
        </button>
        <button
          className={`figma-toolbar-btn${activeTool === 'card' ? ' active' : ''}`}
          title="添加卡片 (C)"
          onClick={() => setActiveTool('card')}
        >
          <Square size={16} />
        </button>
        <button
          className={`figma-toolbar-btn${activeTool === 'connector' ? ' active' : ''}`}
          title="连接线工具 (L)"
          onClick={() => setActiveTool('connector')}
        >
          <MoveUpRight size={16} />
        </button>
        <button
          className={`figma-toolbar-btn${activeTool === 'text' ? ' active' : ''}`}
          title="注释文本 (T)"
          onClick={() => setActiveTool('text')}
        >
          <Type size={16} />
        </button>
        
        <div className="figma-toolbar-divider" />
        
        <button
          className="figma-toolbar-btn"
          title="一键整理布局"
          onClick={() => {
            handleAutoLayout();
            setActiveTool('select');
          }}
        >
          <Sparkles size={16} />
        </button>
      </div>



      {/* 无限缩放平面 */}
      <div 
        className="canvas-lanes"
        style={{
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
          transformOrigin: '0 0'
        }}
      >
          {LANE_DEFINITIONS.map(({ sectionKey }) => (
            <div className="canvas-lane" key={sectionKey} style={{ gridArea: sectionKey }}>
              <div className="lane-header">
                <h3>{LANE_DEFINITIONS.find((lane) => lane.sectionKey === sectionKey)?.laneTitle}</h3>
              </div>
              <div className="lane-content">
                <div className="module-cluster">
                  <div className="cluster-title">{LANE_DEFINITIONS.find((lane) => lane.sectionKey === sectionKey)?.clusterTitle}</div>
                  <div className="cluster-cards">
                    {(canvasSections[sectionKey] || []).map((card) => renderCard(card))}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* 渲染所有关系连线 */}
          {allArrows.map((arr, i) => {
            if (!selectedCardId) return null;

            const allCards = Object.values(canvasSections).flat();
            const startCard = allCards.find(c => c.id === arr.start);
            const endCard = allCards.find(c => c.id === arr.end);
            
            let arrowIsDimmed = false;
            if (startCard && endCard) {
              if (viewMode === 'problem') {
                arrowIsDimmed = (startCard.kind !== 'problem' && startCard.kind !== 'clarification') || 
                                (endCard.kind !== 'problem' && endCard.kind !== 'clarification');
              } else if (viewMode === 'option') {
                arrowIsDimmed = (startCard.kind !== 'option' && startCard.kind !== 'constraint') || 
                                (endCard.kind !== 'option' && endCard.kind !== 'constraint');
              } else if (viewMode === 'decision') {
                arrowIsDimmed = startCard.kind !== 'decision' || endCard.kind !== 'decision';
              } else if (viewMode === 'handoff') {
                arrowIsDimmed = startCard.kind !== 'handoff' || endCard.kind !== 'handoff';
              } else if (selectedCardId || hoveredCardId) {
                const activeId = selectedCardId || hoveredCardId;
                const isStartRelated = activeId === arr.start || selectedRelatedCardIds.has(arr.start) || previewRelatedCardIds.has(arr.start);
                const isEndRelated = activeId === arr.end || selectedRelatedCardIds.has(arr.end) || previewRelatedCardIds.has(arr.end);
                arrowIsDimmed = (viewMode !== 'convergence') && (!isStartRelated || !isEndRelated);
              }
            } else {
              arrowIsDimmed = true;
            }

            return (
              <CustomArrow
                key={i}
                start={arr.start}
                end={arr.end}
                transform={transform}
                visualState={arrowIsDimmed ? 'hidden' : getArrowPresentation(arr, focusedCardId).visualState}
                accentColor={relationColors[getArrowKey(arr)]}
                outIndex={arr.startOffsetIndex}
                outCount={arr.startOffsetTotal}
                inIndex={arr.endOffsetIndex}
                inCount={arr.endOffsetTotal}
                onDelete={handleDeleteConnection}
              />
            );
          })}

          {activeConnector && (
            <TempConnectionLine
              startCardId={activeConnector.startCardId}
              startPort={activeConnector.startPort}
              endX={activeConnector.endX}
              endY={activeConnector.endY}
              transform={transform}
            />
          )}

          {/* 渲染自由文本标签 */}
          {canvasTexts.map((item) => (
            <div
              key={item.id}
              style={{
                position: 'absolute',
                left: item.x,
                top: item.y,
                zIndex: 20,
              }}
              onPointerDown={(event) => beginFreeDrag('text', item.id, event)}
            >
              {item.isEditing ? (
                <textarea
                  style={{
                    background: '#ffffff',
                    border: '1px dashed #1f6fff',
                    outline: 'none',
                    fontFamily: 'inherit',
                    fontSize: '13px',
                    color: 'var(--text-primary)',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    resize: 'both',
                    minWidth: '120px',
                    minHeight: '36px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  }}
                  autoFocus
                  defaultValue={item.text}
                  placeholder="输入注释文字..."
                  onBlur={(e) => {
                    const val = e.target.value.trim();
                    if (!val) {
                      setCanvasTexts(prev => prev.filter(t => t.id !== item.id));
                    } else {
                      setCanvasTexts(prev => prev.map(t => t.id === item.id ? { ...t, text: val, isEditing: false } : t));
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      const val = e.target.value.trim();
                      if (!val) {
                        setCanvasTexts(prev => prev.filter(t => t.id !== item.id));
                      } else {
                        setCanvasTexts(prev => prev.map(t => t.id === item.id ? { ...t, text: val, isEditing: false } : t));
                      }
                    } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                      const val = e.target.value.trim();
                      if (!val) {
                        setCanvasTexts(prev => prev.filter(t => t.id !== item.id));
                      } else {
                        setCanvasTexts(prev => prev.map(t => t.id === item.id ? { ...t, text: val, isEditing: false } : t));
                      }
                    }
                  }}
                />
              ) : (
                <div
                  className="canvas-text-label"
                  style={{
                    background: 'transparent',
                    border: '1px solid transparent',
                    color: 'var(--text-primary)',
                    padding: '6px 10px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'text',
                    whiteSpace: 'pre-wrap',
                    userSelect: 'none',
                    lineHeight: '1.4',
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                  }}
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    setCanvasTexts(prev => prev.map(t => t.id === item.id ? { ...t, isEditing: true } : t));
                  }}
                  title="双击编辑，拖拽移动"
                >
                  {item.text}
                </div>
              )}
            </div>
          ))}
          {/* 画布内漂移时间轴 */}
          {!isPinned && (
            <div 
              style={{
                position: 'absolute',
                left: timelinePos.x,
                top: timelinePos.y,
                width: '720px',
                zIndex: 10,
              }}
            >
              <TimelineScrubber 
                isChatOpen={isChatOpen}
                isPinned={false}
                isCollapsedOverride={false}
                onPinToggle={() => setIsPinned(true)}
                onDragStart={(event) => beginFreeDrag('timeline', 'timeline', event)}
              />
            </div>
          )}

          {/* 画布内漂移活跃缺口看板 */}
          {isBacklogOpen && !isBacklogPinned && (
            <div 
              style={{
                position: 'absolute',
                left: backlogPos.x,
                top: backlogPos.y,
                width: '280px',
                zIndex: 10,
              }}
            >
              <ActiveBacklogPanel 
                isChatOpen={isChatOpen}
                isPinned={false}
                onPinToggle={() => setIsBacklogPinned(true)}
                onDragStart={(event) => beginFreeDrag('backlog', 'backlog', event)}
                canvasSections={canvasSections}
                selectedCardId={selectedCardId}
                setSelectedCardId={setSelectedCardId}
                uploadedMaterials={uploadedMaterials}
              />
            </div>
          )}
        </div>

      {pendingMove && (
        <div className="canvas-move-confirm">
          <div className="canvas-move-confirm-copy">
            <span className="canvas-move-confirm-title">确认迁移</span>
            <span className="canvas-move-confirm-text">{pendingMove.message}</span>
          </div>
          <div className="canvas-move-confirm-actions">
            <button className="move-confirm-secondary" onClick={() => setPendingMove(null)}>取消</button>
            <button className="move-confirm-primary" onClick={confirmPendingMove}>确认</button>
          </div>
        </div>
      )}

      {moveError && <div className="canvas-move-toast">{moveError}</div>}
      {/* 底部时间轴 (钉住状态下固定在屏幕左下角偏极边缘) */}
      {isPinned && (
        <TimelineScrubber 
          isChatOpen={isChatOpen} 
          isPinned={true}
          onPinToggle={() => setIsPinned(false)}
        />
      )}

      {/* 活跃缺口 (Active Backlog) 悬浮卡片看板 (钉住状态下固定在右上角) */}
      {isBacklogOpen && isBacklogPinned && (
        <ActiveBacklogPanel 
          isChatOpen={isChatOpen}
          isPinned={true}
          onPinToggle={() => setIsBacklogPinned(false)}
          canvasSections={canvasSections}
          selectedCardId={selectedCardId}
          setSelectedCardId={setSelectedCardId}
          uploadedMaterials={uploadedMaterials}
        />
      )}
    </div>
  );
}

function CardCreatorBubble({ x, y, stage, onClose, onSubmit }) {
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
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
      onPointerUp={(e) => e.stopPropagation()}
    >
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)' }}>添加新画布卡片</div>
      <input 
        placeholder="卡片标题" 
        value={title} 
        onChange={e => setTitle(e.target.value)} 
        autoFocus
      />
      <textarea 
        placeholder="一句话摘要说明..." 
        value={desc} 
        onChange={e => setDesc(e.target.value)} 
        rows={3}
      />
      <select value={kind} onChange={e => setKind(e.target.value)}>
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

function TempConnectionLine({ startCardId, startPort, endX, endY, transform }) {
  const [startPos, setStartPos] = useState(null);

  useEffect(() => {
    const el = document.getElementById(startCardId);
    const container = document.querySelector('.canvas-lanes');
    if (!el || !container) return;

    const sRect = el.getBoundingClientRect();
    const cRect = container.getBoundingClientRect();
    const scale = transform.scale;

    let x = (sRect.left + sRect.right) / 2 - cRect.left;
    let y = (sRect.top + sRect.bottom) / 2 - cRect.top;

    if (startPort === 'top') {
      x = (sRect.left + sRect.right) / 2 - cRect.left;
      y = sRect.top - cRect.top;
    } else if (startPort === 'bottom') {
      x = (sRect.left + sRect.right) / 2 - cRect.left;
      y = sRect.bottom - cRect.top;
    } else if (startPort === 'left') {
      x = sRect.left - cRect.left;
      y = (sRect.top + sRect.bottom) / 2 - cRect.top;
    } else if (startPort === 'right') {
      x = sRect.right - cRect.left;
      y = (sRect.top + sRect.bottom) / 2 - cRect.top;
    }

    setStartPos({ x: x / scale, y: y / scale });
  }, [startCardId, startPort, transform]);

  if (!startPos) return null;

  return (
    <svg 
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 100,
        overflow: 'visible'
      }}
    >
      <defs>
        <marker id="temp-arrowhead" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill="#1f6fff" />
        </marker>
      </defs>
      <line 
        x1={startPos.x} 
        y1={startPos.y} 
        x2={endX} 
        y2={endY} 
        stroke="#1f6fff" 
        strokeWidth="2" 
        strokeDasharray="4 4"
        markerEnd="url(#temp-arrowhead)"
      />
    </svg>
  );
}
