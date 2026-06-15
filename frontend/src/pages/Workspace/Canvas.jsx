import React, { useEffect, useRef, useState } from 'react';
import './Canvas.css';
import { ListTodo, MoreHorizontal, ChevronRight, ChevronDown, ChevronUp, Paperclip, Terminal, Circle, CheckCircle2 } from 'lucide-react';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';
import { apiPost, apiUrl } from '../../api';
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

const LANE_DEFINITIONS = [
  { sectionKey: 'evidence', laneTitle: '1. 探索发现', clusterTitle: '用户反馈' },
  { sectionKey: 'problems', laneTitle: '2. 需求定义', clusterTitle: '功能设计' },
  { sectionKey: 'clarify', laneTitle: '3. 问题澄清', clusterTitle: '待澄清问题' },
  { sectionKey: 'rules', laneTitle: '4. 方案规划', clusterTitle: '决策确认' },
  { sectionKey: 'planning', laneTitle: '5. 落地执行', clusterTitle: '迭代计划' },
];

function CustomArrow({ start, end, transform, visualState = 'muted', accentColor, outIndex = 0, outCount = 1, inIndex = 0, inCount = 1 }) {
  const [path, setPath] = useState('');
  
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

      let startX = sRight;
      let endX = isSameColumn ? eRight : eLeft;
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
    const interval = setInterval(update, 50);
    return () => clearInterval(interval);
  }, [start, end, transform, outIndex, outCount, inIndex, inCount]);
  
  if (!path) return null;

  let opacity = 0.26;
  let strokeColor = '#b8c4d4';
  let strokeWidth = 1.6;

  if (visualState === 'active') {
    opacity = 1;
    strokeColor = accentColor || '#1f6fff';
    strokeWidth = 2.6;
  } else if (visualState === 'hidden') {
    opacity = 0.06;
    strokeColor = '#d7dfeb';
    strokeWidth = 1.2;
  }

  return (
    <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1, overflow: 'visible' }}>
      <defs>
        <marker id={`arrowhead-${start}-${end}`} markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill={strokeColor} />
        </marker>
      </defs>
      <path 
        d={path} 
        fill="none" 
        stroke={strokeColor} 
        strokeWidth={strokeWidth} 
        opacity={opacity}
        style={{ transition: 'stroke 0.2s, stroke-width 0.2s, opacity 0.2s' }}
        markerEnd={`url(#arrowhead-${start}-${end})`} 
      />
    </svg>
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
  draggable,
  onDragStart,
  onDragEnd,
}) {
  const primaryTag = data.tags?.[0];
  const secondaryTags = data.tags?.slice(1) || [];
  const hasTags = primaryTag || data.statusPill;
  const isEditingTitle = editingState?.cardId === data.id && editingState?.field === 'title';
  const isEditingDesc = editingState?.cardId === data.id && editingState?.field === 'desc';

  const cardClassName = `canvas-card${isSelectedSelf ? ' selected-self' : ''}${isSelectedRelated && !isSelectedSelf ? ' selected-related' : ''}${isPreviewSelf ? ' preview-self' : ''}${isPreviewRelated && !isPreviewSelf && !isSelectedRelated ? ' preview-related' : ''}`;

  return (
    <div 
      className={cardClassName} 
      id={data.id}
      draggable={draggable}
      style={relationAccent ? { '--relation-accent': relationAccent } : undefined}
      onMouseEnter={() => onPreviewStart(data.id)}
      onMouseLeave={onPreviewEnd}
      onDragStart={(event) => onDragStart(event, data.id)}
      onDragEnd={onDragEnd}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(data.id);
      }}
    >
      <div className="canvas-card-header-group">
        <div className="canvas-card-header">
          <div
            className="canvas-card-title-wrap"
            onDoubleClick={(event) => {
              event.stopPropagation();
              onStartEdit(data.id, 'title', data.title);
            }}
          >
            {isEditingTitle ? (
              <input
                className="canvas-card-title-input"
                autoFocus
                value={editingState.draft}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => onStartEdit(data.id, 'title', event.target.value, true)}
                onBlur={() => onSaveEdit(data.id, 'title', editingState.draft, { commit: true })}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    onSaveEdit(data.id, 'title', data.title, { commit: false });
                  }

                  if (event.key === 'Enter') {
                    event.preventDefault();
                    onSaveEdit(data.id, 'title', editingState.draft, { commit: true });
                  }
                }}
              />
            ) : (
              <span className="canvas-card-title">{data.title}</span>
            )}
          </div>
          <button className="icon-btn" style={{width: 20, height: 20}}><MoreHorizontal size={14}/></button>
        </div>

        {hasTags && (
          <div className="card-tags-row">
            {primaryTag && (
              <span className={`canvas-tag tag-${primaryTag.color}`}>{primaryTag.label}</span>
            )}
            {secondaryTags.length > 0 && secondaryTags.map((t, i) => (
              <span key={i} className={`canvas-tag tag-${t.color}`}>{t.label}</span>
            ))}
            {data.statusPill && (
              <span className={`canvas-tag tag-${data.statusPill.color}`}>{data.statusPill.label}</span>
            )}
          </div>
        )}
      </div>

      <div
        className={`canvas-card-desc-wrap${isEditingDesc ? ' is-editing' : ''}`}
        onDoubleClick={(event) => {
          event.stopPropagation();
          onStartEdit(data.id, 'desc', data.desc || '');
        }}
      >
        {isEditingDesc ? (
          <>
            <textarea
              className="canvas-card-desc-input"
              autoFocus
              value={editingState.draft}
              onClick={(event) => event.stopPropagation()}
              onChange={(event) => onStartEdit(data.id, 'desc', event.target.value, true)}
              onBlur={() => onSaveEdit(data.id, 'desc', editingState.draft, { commit: true })}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', data.desc || '', { commit: false });
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', editingState.draft, { commit: true });
                }
              }}
            />
            <div className="card-editor-hint">`Cmd/Ctrl + Enter` 保存，`Esc` 取消</div>
          </>
        ) : (
          <div className="canvas-card-desc">{data.desc || '双击补充摘要'}</div>
        )}
      </div>

      <StructuredContent kind={data.structureKind} items={data.structuredItems} />

      {data.attachments && (
        <div className="card-attachments">
          {data.attachments.map((att, i) => (
            <div key={i} className="attachment-pill">
              <span className="att-icon">{att.icon}</span>
              <span>{att.label}</span>
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
    </div>
  );
}

function TimelineScrubber({ isChatOpen }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (isCollapsed) {
    return (
      <div className={`timeline-scrubber collapsed${isChatOpen ? ' chat-open' : ''}`} onClick={() => setIsCollapsed(false)} style={{
        padding: '8px var(--sp-6)',
        cursor: 'pointer',
        width: 'auto',
        maxWidth: '200px',
        height: 'auto',
        gap: 0,
        borderRadius: 'var(--r-xl)'
      }}>
        <div className="timeline-header" style={{ margin: 0, justifyContent: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600 }}>显示项目时间轴</span>
          <ChevronUp size={14} className="text-tertiary" />
        </div>
      </div>
    );
  }

  return (
    <div className={`timeline-scrubber${isChatOpen ? ' chat-open' : ''}`}>
      <div className="timeline-header">
        <span>时间轴：项目里程碑</span>
        <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="icon-btn" title="更多选项" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>
            <MoreHorizontal size={14} />
          </button>
          <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setIsCollapsed(true); }} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>
            <ChevronDown size={14} className="text-tertiary" />
          </button>
        </div>
      </div>

      <div className="timeline-body">
        {/* 顶部的日期和刻度线 */}
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

        {/* 分段轨道 */}
        <div className="timeline-segmented-track">
          <div className="track-segment segment-gray" style={{ width: '25%' }}>
            <span>阶段</span>
          </div>
          <div className="track-segment segment-blue" style={{ width: '45%' }}>
            <span>内测发布</span>
          </div>
          <div className="track-segment segment-gray" style={{ width: '30%' }}>
            <span>MVP 上线</span>
          </div>

          {/* 黑色当前日期指示针 */}
          <div className="timeline-current-pointer" style={{ left: '51%' }}>
            <div className="pointer-line"></div>
            <span className="pointer-label">当前日期：5月18日</span>
          </div>
        </div>
      </div>
    </div>
  );
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
  const [showTodos, setShowTodos] = useState(false);
  const [localTodos, setLocalTodos] = useState([
    { id: 1, text: '启动前后端联调环境并确认健康状态', checked: false },
    { id: 2, text: '构造一个真实问题场景，准备材料与数据引用输入', checked: false },
    { id: 3, text: '按用户路径逐步执行输入编译、澄清、约束/待决策、交接物刷新', checked: false },
    { id: 4, text: '记录链路中的实际问题、修复阻塞项并复测', checked: false }
  ]);

  const toggleTodo = (id) => {
    setLocalTodos(prev => prev.map(t => t.id === id ? { ...t, checked: !t.checked } : t));
  };
  const [canvasSections, setCanvasSections] = useState(() => createInitialCanvasSections(DEMO_CANVAS_SECTIONS));
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [hoveredCardId, setHoveredCardId] = useState(null);
  const [editingState, setEditingState] = useState(null);
  const [draggingCardId, setDraggingCardId] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [moveError, setMoveError] = useState(null);
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });

  function mapSectionToBackendStage(sectionKey) {
    if (sectionKey === 'evidence') return 'discovery';
    if (sectionKey === 'problems' || sectionKey === 'clarify' || sectionKey === 'rules') return 'define';
    if (sectionKey === 'planning') return 'handoff';
    return sectionKey;
  }

  function mapBackendCardsToSections(backendCards, backendRelations) {
    const sections = {
      evidence: [],
      problems: [],
      clarify: [],
      rules: [],
      planning: [],
    };

    const nextMap = {};
    (backendRelations || []).forEach(rel => {
      const fromId = rel.from_card_id;
      const toId = rel.to_card_id;
      if (fromId && toId) {
        if (!nextMap[fromId]) nextMap[fromId] = [];
        nextMap[fromId].push(toId);
      }
    });

    (backendCards || []).forEach(card => {
      let sectionKey = 'evidence';
      if (card.kind === 'problem') sectionKey = 'problems';
      else if (card.kind === 'clarification') sectionKey = 'clarify';
      else if (card.kind === 'constraint' || card.kind === 'decision') sectionKey = 'rules';
      else if (card.kind === 'handoff') sectionKey = 'planning';

      const mappedTags = (card.tags || []).map(t => {
        let color = 'blue';
        if (t.includes('高') || t.includes('风险') || t.includes('冲突')) color = 'red';
        else if (t.includes('数据') || t.includes('参考')) color = 'blue';
        else if (t.includes('已确认') || t.includes('已生效')) color = 'green';
        else if (t.includes('待澄清') || t.includes('待决策')) color = 'yellow';
        return { label: t, color };
      });

      const source = card.metadata?.source || (card.kind === 'evidence' ? { label: '来源', name: card.metadata?.created_by || 'AI 提炼', avatar: 'A', avatarTone: 'violet' } : null);
      const owner = card.metadata?.owner || (card.metadata?.owner_name ? { label: '负责人', name: card.metadata.owner_name, avatar: (card.metadata.owner_name[0] || 'U'), avatarTone: 'slate' } : null);

      const mappedCard = {
        id: card.card_id,
        title: card.title,
        desc: card.summary,
        tags: mappedTags,
        statusPill: card.status ? { 
          label: card.status === 'open' ? '激活中' : card.status === 'draft' ? '草稿' : card.status === 'pending' ? '待确认' : card.status === 'confirmed' || card.status === 'effective' ? '已确认' : card.status, 
          color: card.status === 'confirmed' || card.status === 'effective' || card.status === 'resolved' ? 'green' : card.status === 'pending' ? 'yellow' : 'gray' 
        } : null,
        structureKind: card.metadata?.structure_kind || null,
        structuredItems: card.metadata?.structured_items || [],
        attachments: card.metadata?.attachments || null,
        confidence: card.metadata?.confidence || null,
        source,
        owner,
        next: nextMap[card.card_id] || [],
      };

      sections[sectionKey].push(mappedCard);
    });

    return sections;
  }

  useEffect(() => {
    if (workspaceId === 'demo') {
      setCanvasSections(createInitialCanvasSections(DEMO_CANVAS_SECTIONS));
    } else if (cards && cards.length > 0) {
      setCanvasSections(mapBackendCardsToSections(cards, relations));
    } else {
      setCanvasSections({
        evidence: [],
        problems: [],
        clarify: [],
        rules: [],
        planning: [],
      });
    }
  }, [cards, relations, workspaceId]);

  // 绑定原生 wheel 事件以防止 default scroll
  const containerRef = useRef(null);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handleWheel = (e) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const zoomFactor = -e.deltaY * 0.01;
        setTransform(t => {
          let newScale = t.scale * (1 + zoomFactor);
          newScale = Math.min(Math.max(newScale, 0.1), 3);
          return { ...t, scale: newScale };
        });
      } else {
        setTransform(t => ({
          ...t,
          x: t.x - e.deltaX,
          y: t.y - e.deltaY
        }));
      }
    };
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  useEffect(() => {
    if (!moveError) return undefined;

    const timer = window.setTimeout(() => setMoveError(null), 2200);
    return () => window.clearTimeout(timer);
  }, [moveError]);

  const handlePointerDown = (e) => {
    if (
      editingState ||
      draggingCardId ||
      e.target.closest('.canvas-card') ||
      e.target.closest('.todos-trigger') ||
      e.target.closest('.timeline-scrubber') ||
      e.target.closest('input, textarea, button')
    ) {
      return;
    }
    if (selectedCardId !== null) setSelectedCardId(null);
    isDragging.current = true;
    dragStart.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
    e.target.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e) => {
    if (!isDragging.current) return;
    setTransform(t => ({
      ...t,
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y
    }));
  };

  const handlePointerUp = (e) => {
    isDragging.current = false;
    e.target.releasePointerCapture(e.pointerId);
  };

  const arrows = collectCanvasArrows(canvasSections);
  const focusedCardId = selectedCardId ?? hoveredCardId;
  const selectedRelatedCardIds = getRelatedCardIds(selectedCardId, arrows);
  const previewRelatedCardIds = selectedCardId ? new Set() : getRelatedCardIds(hoveredCardId, arrows);
  const relationColors = getFocusedRelationColors(arrows, focusedCardId);

  // 辅助函数判断卡片高亮关系
  const checkCardActiveState = (cardId) => {
    return {
      isSelectedSelf: selectedCardId === cardId,
      isSelectedRelated: selectedCardId !== null && selectedRelatedCardIds.has(cardId),
      isPreviewSelf: selectedCardId === null && hoveredCardId === cardId,
      isPreviewRelated: selectedCardId === null && previewRelatedCardIds.has(cardId),
    };
  };

  const getCardRelationAccent = (cardId) => {
    if (!focusedCardId || cardId === focusedCardId) return null;
    const edge = arrows.find((arrow) =>
      (arrow.start === focusedCardId && arrow.end === cardId) ||
      (arrow.end === focusedCardId && arrow.start === cardId),
    );
    return edge ? relationColors[getArrowKey(edge)] : null;
  };

  const startEdit = (cardId, field, draft, preserve = false) => {
    setEditingState((current) => {
      if (preserve && current?.cardId === cardId && current?.field === field) {
        return { ...current, draft };
      }

      return { cardId, field, draft };
    });
  };

  const saveEdit = async (cardId, field, value, { commit }) => {
    if (commit) {
      const normalized = value.trim();
      if (workspaceId && workspaceId !== 'demo') {
        const payload = {
          [field === 'desc' ? 'summary' : field]: normalized || (field === 'title' ? '未命名卡片' : '')
        };
        await fetch(apiUrl(`/api/canvas/workspaces/${workspaceId}/cards/${cardId}`), {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (onRefresh) onRefresh();
      } else {
        setCanvasSections((current) =>
          updateCanvasCard(current, cardId, {
            [field]: normalized || (field === 'title' ? '未命名卡片' : ''),
          }),
        );
      }
    }

    setEditingState(null);
  };

  const handleCardDragStart = (event, cardId) => {
    if (editingState?.cardId === cardId) {
      event.preventDefault();
      return;
    }

    event.stopPropagation();
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', cardId);
    setDraggingCardId(cardId);
    setSelectedCardId(cardId);
    setDropTarget(null);
  };

  const handleCardDragEnd = () => {
    setDraggingCardId(null);
    setDropTarget(null);
  };

  const queueDropTarget = (sectionKey, index) => {
    if (!draggingCardId) return;

    const fromLocation = getCardLocation(canvasSections, draggingCardId);
    if (!fromLocation) return;

    const legal = isMoveAllowed({ fromSection: fromLocation.sectionKey, toSection: sectionKey });
    setDropTarget({
      cardId: draggingCardId,
      fromSection: fromLocation.sectionKey,
      sectionKey,
      index,
      legal,
    });
  };

  const handleCardDragOver = (event, sectionKey, index) => {
    if (!draggingCardId) return;
    event.preventDefault();
    event.stopPropagation();

    const rect = event.currentTarget.getBoundingClientRect();
    const insertAfter = event.clientY > rect.top + rect.height / 2;
    queueDropTarget(sectionKey, index + (insertAfter ? 1 : 0));
  };

  const handleClusterDragOver = (event, sectionKey) => {
    if (!draggingCardId) return;
    event.preventDefault();
    event.stopPropagation();
    queueDropTarget(sectionKey, canvasSections[sectionKey].length);
  };

  const applyDropTarget = () => {
    if (!dropTarget?.cardId) return;

    if (!dropTarget.legal) {
      setMoveError('当前卡片不能迁移到这个阶段，请放到高亮的合法区域。');
      setDropTarget(null);
      return;
    }

    const fromLocation = getCardLocation(canvasSections, dropTarget.cardId);
    if (!fromLocation) return;

    if (fromLocation.sectionKey === dropTarget.sectionKey) {
      const sameSectionIndex =
        fromLocation.index < dropTarget.index ? dropTarget.index - 1 : dropTarget.index;
      setCanvasSections((current) =>
        moveCanvasCard(current, {
          cardId: dropTarget.cardId,
          toSection: dropTarget.sectionKey,
          toIndex: sameSectionIndex,
        }),
      );
      setDropTarget(null);
      return;
    }

    setPendingMove({
      cardId: dropTarget.cardId,
      fromSection: fromLocation.sectionKey,
      toSection: dropTarget.sectionKey,
      toIndex: dropTarget.index,
      message: describeCanvasMove({
        fromSection: fromLocation.sectionKey,
        toSection: dropTarget.sectionKey,
      }),
    });
    setDropTarget(null);
  };

  const confirmPendingMove = async () => {
    if (!pendingMove) return;

    if (workspaceId && workspaceId !== 'demo') {
      const backendStage = mapSectionToBackendStage(pendingMove.toSection);
      await apiPost(`/api/canvas/workspaces/${workspaceId}/cards/${pendingMove.cardId}/move`, {
        stage: backendStage,
        reason: 'user drag'
      }, null);
      if (onRefresh) onRefresh();
    } else {
      setCanvasSections((current) =>
        moveCanvasCard(current, {
          cardId: pendingMove.cardId,
          toSection: pendingMove.toSection,
          toIndex: pendingMove.toIndex,
        }),
      );
    }
    setPendingMove(null);
  };

  const renderCard = (card, sectionKey, index) => {
    const { isSelectedSelf, isSelectedRelated, isPreviewSelf, isPreviewRelated } = checkCardActiveState(card.id);
    const showsDropBefore =
      dropTarget?.legal &&
      dropTarget.sectionKey === sectionKey &&
      dropTarget.index === index;
    const showsDropAfter =
      dropTarget?.legal &&
      dropTarget.sectionKey === sectionKey &&
      dropTarget.index === index + 1;

    return (
      <div
        key={card.id}
        className={`canvas-card-slot${showsDropBefore ? ' drop-before' : ''}${showsDropAfter ? ' drop-after' : ''}`}
        onDragOver={(event) => handleCardDragOver(event, sectionKey, index)}
        onDrop={(event) => {
          event.preventDefault();
          event.stopPropagation();
          applyDropTarget();
        }}
      >
        <CanvasCard
          data={card}
          onSelect={(cardId) => setSelectedCardId((current) => (current === cardId ? null : cardId))}
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
          draggable={!editingState && !pendingMove}
          onDragStart={handleCardDragStart}
          onDragEnd={handleCardDragEnd}
        />
      </div>
    );
  };

  const renderLane = ({ sectionKey, laneTitle, clusterTitle }) => {
    const cards = canvasSections[sectionKey];
    const fromLocation = draggingCardId ? getCardLocation(canvasSections, draggingCardId) : null;
    const canDropHere = fromLocation
      ? isMoveAllowed({ fromSection: fromLocation.sectionKey, toSection: sectionKey })
      : false;
    const isDropEndTarget = dropTarget?.legal && dropTarget.sectionKey === sectionKey && dropTarget.index === cards.length;

    return (
      <div className="canvas-lane" key={sectionKey} style={{ gridArea: sectionKey }}>
        <div className="lane-header">
          <h3>{laneTitle}</h3>
        </div>
        <div className="lane-content">
          <div className="module-cluster">
            <div className="cluster-title">{clusterTitle}</div>
            <div
              className={`cluster-cards${draggingCardId ? ` drag-scope ${canDropHere ? 'drop-zone-legal' : 'drop-zone-illegal'}` : ''}${isDropEndTarget ? ' drop-end' : ''}`}
              onDragOver={(event) => handleClusterDragOver(event, sectionKey)}
              onDrop={(event) => {
                event.preventDefault();
                event.stopPropagation();
                applyDropTarget();
              }}
            >
              {cards.map((card, index) => renderCard(card, sectionKey, index))}
            </div>
          </div>
        </div>
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
        backgroundSize: `${24 * transform.scale}px ${24 * transform.scale}px`
      }}
    >
      {/* 悬浮 Todos 触发按钮 - 独立于缩放画布 */}
      <button 
        className="todos-trigger" 
        style={{position: 'absolute', top: 24, right: isChatOpen ? 452 : 160, zIndex: 10}}
        onClick={() => setShowTodos(!showTodos)}
      >
        <ListTodo size={14} /> 活跃待办 <ChevronRight size={14} style={{transform: showTodos ? 'rotate(90deg)' : 'none', transition: '0.2s'}}/>
      </button>

      {/* 无限缩放平面 */}
      <div 
        className="canvas-lanes"
        style={{
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
          transformOrigin: '0 0'
        }}
      >
          
          {LANE_DEFINITIONS.map(renderLane)}

          {/* 渲染所有箭头 */}
          {arrows.map((arr, i) => (
            <CustomArrow
              key={i}
              start={arr.start}
              end={arr.end}
              transform={transform}
              visualState={getArrowPresentation(arr, focusedCardId).visualState}
              accentColor={relationColors[getArrowKey(arr)]}
              outIndex={arr.startOffsetIndex}
              outCount={arr.startOffsetTotal}
              inIndex={arr.endOffsetIndex}
              inCount={arr.endOffsetTotal}
            />
          ))}

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

      {/* 底部时间轴 */}
      <TimelineScrubber isChatOpen={isChatOpen} />

      {/* 活跃待办浮层 (二合一面板) */}
      {showTodos && (
        <div style={{
          position: 'absolute', top: 68, right: isChatOpen ? 452 : 160, width: 280,
          background: '#fff', borderRadius: 12, boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
          border: '1px solid var(--border)', zIndex: 100, padding: 16,
          maxHeight: 450, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16
        }}>
          {/* 待办板块 */}
          <div>
            <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 12}}>
              <span style={{fontSize: 13, fontWeight: 600, color: '#94a3b8'}}>待办</span>
            </div>
            <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
              {localTodos.map(todo => (
                <div 
                  key={todo.id} 
                  onClick={() => toggleTodo(todo.id)}
                  style={{
                    display: 'flex', 
                    gap: 10, 
                    fontSize: 13, 
                    alignItems: 'flex-start', 
                    cursor: 'pointer',
                    userSelect: 'none'
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', marginTop: 2, color: todo.checked ? '#94a3b8' : '#64748b' }}>
                    {todo.checked ? (
                      <CheckCircle2 size={16} color="#94a3b8" />
                    ) : (
                      <Circle size={16} color="#cbd5e1" />
                    )}
                  </span>
                  <span style={{
                    color: todo.checked ? '#94a3b8' : '#334155',
                    textDecoration: todo.checked ? 'line-through' : 'none',
                    lineHeight: '1.4',
                    flex: 1,
                    textAlign: 'left'
                  }}>
                    {todo.text}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 分隔线 */}
          <div style={{ borderTop: '1px solid #f1f5f9' }} />

          {/* 来源板块 */}
          <div>
            <div style={{marginBottom: 12}}>
              <span style={{fontSize: 13, fontWeight: 600, color: '#94a3b8'}}>来源</span>
            </div>
            <div style={{display: 'flex', flexDirection: 'column', gap: 10}}>
              {uploadedMaterials.length === 0 ? (
                <div style={{fontSize: 13, color: '#94a3b8', fontStyle: 'italic', textAlign: 'left'}}>
                  暂无来源
                </div>
              ) : (
                uploadedMaterials.map(m => {
                  return (
                    <div key={m.id} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      fontSize: 13, color: '#334155'
                    }}>
                      <Paperclip size={16} color="#64748b" />
                      <span style={{
                        fontSize: 13, fontWeight: 500, color: '#334155',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1,
                        textAlign: 'left'
                      }} title={m.name}>{m.name}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
