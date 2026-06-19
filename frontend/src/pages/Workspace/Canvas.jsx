import React, { useEffect, useRef, useState } from 'react';
import './Canvas.css';
import {
  Archive,
  ChevronRight,
  Clock3,
  ListTodo,
  MousePointer,
  MoveUpRight,
  MoreHorizontal,
  Shapes,
  Sparkles,
  Square,
  StickyNote,
  Timer,
  Type,
} from 'lucide-react';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';
import { apiPost, apiDelete, apiUrl } from '../../api';
import {
  applyConnectionToSections,
  buildConnectionPortMap,
  collectCanvasArrows,
  findRelationId,
  getArrowKey,
  getArrowPresentation,
  getFocusedRelationColors,
  getRelatedCardIds,
  removeConnectionFromSections,
  syncSectionConnectionsFromRelations,
} from './canvasRelations.js';
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
  buildCompactSectionLayout,
  estimateCardHeight,
  getCanvasBounds,
  resolveCollisions,
} from './canvasLayout.js';
import {
  getCanvasViewStateStorageKey,
  readStoredCanvasViewState,
} from './workspaceSession';
import { CARD_PORTS } from './edgeRouter.js';
import {
  ActiveBacklogPanel,
  ClockWidget,
  CardCreatorBubble,
  FocusTimerWidget,
  ParkingLotWidget,
  StickyNoteWidget,
  TimelineScrubber,
} from './CanvasOverlays.jsx';
import CanvasTextLayer from './CanvasTextLayer.jsx';
import {
  CustomArrow,
  TempConnectionLine,
  getCardPorts,
  getCardRectInCanvas,
  getPortPointByName,
} from './CanvasEdges.jsx';

const LANE_DEFINITIONS = [
  { sectionKey: 'clarify', laneTitle: '待澄清项', clusterTitle: '问题与不确定性' },
  { sectionKey: 'rules', laneTitle: '规则约束', clusterTitle: '核心业务规则' },
  { sectionKey: 'options', laneTitle: '方案与决策', clusterTitle: '备选方案与拍板' },
  { sectionKey: 'evidence', laneTitle: '探索发现', clusterTitle: '原始证据池' },
  { sectionKey: 'problems', laneTitle: '焦点问题', clusterTitle: '问题定义' },
  { sectionKey: 'planning', laneTitle: '落地交接', clusterTitle: '结构化交接物' },
];

const CONNECT_SNAP_RADIUS = 64;
const EXPLICIT_PORT_SNAP_RADIUS = 20;
const NOTE_THEMES = ['sun', 'mint', 'sky', 'rose'];
const COLLAPSED_WIDGET_HEIGHT = 36;
const SCREEN_WIDGET_PADDING = 16;
const WIDGET_LAYOUT_TRANSITION = 'left 0.26s cubic-bezier(0.2, 0, 0, 1), top 0.26s cubic-bezier(0.2, 0, 0, 1), width 0.26s cubic-bezier(0.2, 0, 0, 1), height 0.26s cubic-bezier(0.2, 0, 0, 1)';

const getCollapsedWidgetWidthByTitle = (title = '') => {
  const textWidth = Array.from(title).reduce((width, char) => {
    if (/[\u4e00-\u9fff]/.test(char)) return width + 12.5;
    if (/\s/.test(char)) return width + 4;
    return width + 7;
  }, 0);

  // 左右 padding + 图标 + 两处间距 + 展开箭头，保留与 Canvas AI 相近的紧凑胶囊。
  return Math.ceil(Math.max(96, textWidth + 78));
};

const getSystemWidgetCollapsedWidth = (type) =>
  getCollapsedWidgetWidthByTitle(type === 'backlog' ? '活跃缺口' : '项目时间轴');

const WIDGET_LIBRARY = [
  {
    type: 'timeline',
    icon: Sparkles,
    name: '项目时间轴',
    description: '看当前主题大致推进到哪里。',
    scope: 'system',
  },
  {
    type: 'backlog',
    icon: ListTodo,
    name: '活跃缺口',
    description: '聚焦当前最阻塞推进的缺口。',
    scope: 'system',
  },
  {
    type: 'stickyNote',
    icon: StickyNote,
    name: '便签',
    description: '记一句临时判断、提醒或灵感。',
    scope: 'personal',
  },
  {
    type: 'parkingLot',
    icon: Archive,
    name: '停车区',
    description: '暂存不在当前主线展开的事项。',
    scope: 'personal',
  },
  {
    type: 'clock',
    icon: Clock3,
    name: '时钟',
    description: '提供轻量时间感知和第二时区。',
    scope: 'personal',
  },
  {
    type: 'focusTimer',
    icon: Timer,
    name: '专注计时器',
    description: '给收敛、整理和交接一个短时节奏。',
    scope: 'personal',
  },
];

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
  isConnectorSource,
  isConnectorTarget,
}) {
  const primaryTag = data.tags?.[0];
  const secondaryTags = data.tags?.slice(1) || [];
  const hasTags = primaryTag || data.statusPill;

  const isEditingTitle = editingState?.cardId === data.id && editingState?.field === 'title';
  const isEditingDesc = editingState?.cardId === data.id && editingState?.field === 'desc';

  const cardClassName = `canvas-card${isSelectedSelf ? ' selected-self' : ''}${isSelectedRelated && !isSelectedSelf ? ' selected-related' : ''}${isPreviewSelf ? ' preview-self' : ''}${isPreviewRelated && !isPreviewSelf && !isSelectedRelated ? ' preview-related' : ''}${isDimmed ? ' is-dimmed' : ''}${isConnectorSource ? ' connector-source' : ''}${isConnectorTarget ? ' connector-target' : ''}`;

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
            className="connector-hitarea port-top"
            style={{ top: 0, left: '50%' }}
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('top', e); }} 
            title="向上连线"
            data-port="top"
          />
          <div 
            className="connector-hitarea port-bottom"
            style={{ top: '100%', left: '50%' }}
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('bottom', e); }} 
            title="向下连线"
            data-port="bottom"
          />
          <div 
            className="connector-hitarea port-left"
            style={{ top: '50%', left: 0 }}
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('left', e); }} 
            title="向左连线"
            data-port="left"
          />
          <div 
            className="connector-hitarea port-right"
            style={{ top: '50%', left: '100%' }}
            onPointerDown={(e) => { e.stopPropagation(); onConnectStart('right', e); }} 
            title="向右连线"
            data-port="right"
          />
        </>
      )}
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
  const [viewMode, setViewMode] = useState('convergence'); // convergence | problem | option | decision | handoff
  const [activeTool, setActiveTool] = useState('select'); // select | card | connector | text
  const [activeConnector, setActiveConnector] = useState(null); // { startCardId, startPort, endX, endY }
  const [canvasTexts, setCanvasTexts] = useState([]);
  const [creatorState, setCreatorState] = useState(null); // { x, y, canvasX, canvasY, stage }
  const [isBacklogOpen, setIsBacklogOpen] = useState(true);
  const [cardOffsets, setCardOffsets] = useState({});
  const [isTimelineOpen, setIsTimelineOpen] = useState(true);
  const [isPinned, setIsPinned] = useState(true);
  const [isTimelineCollapsed, setIsTimelineCollapsed] = useState(true);
  const [timelinePos, setTimelinePos] = useState({ x: 80, y: 800 });
  const [timelinePinnedPos, setTimelinePinnedPos] = useState({ x: 24, y: 720 });
  const [isBacklogPinned, setIsBacklogPinned] = useState(true);
  const [isBacklogCollapsed, setIsBacklogCollapsed] = useState(false);
  const [backlogPos, setBacklogPos] = useState({ x: 1200, y: 300 });
  const [backlogPinnedPos, setBacklogPinnedPos] = useState({ x: 940, y: 24 });
  const [personalWidgets, setPersonalWidgets] = useState([]);
  const [activeCardMenuId, setActiveCardMenuId] = useState(null);
  const [isWidgetPanelOpen, setIsWidgetPanelOpen] = useState(false);

  const [canvasSections, setCanvasSections] = useState(() => createInitialCanvasSections(DEMO_CANVAS_SECTIONS));
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [hoveredCardId, setHoveredCardId] = useState(null);
  const [connectorTarget, setConnectorTarget] = useState(null);
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
  const pendingTextFocusIdRef = useRef(null);

  const canvasViewStorageKey = getCanvasViewStateStorageKey(workspaceId);
  const connectionPortMapRef = useRef({});

  const focusCanvasTextEditor = (textId) => {
    requestAnimationFrame(() => {
      const editor = document.getElementById(`canvas-text-editor-${textId}`);
      if (!editor) return;
      editor.focus();
      const length = editor.value?.length ?? 0;
      if (typeof editor.setSelectionRange === 'function') {
        editor.setSelectionRange(length, length);
      }
    });
  };

  const updateCanvasText = (textId, updates) => {
    setCanvasTexts((current) => current.map((item) => (
      item.id === textId ? { ...item, ...updates } : item
    )));
  };

  const finishCanvasTextEdit = (textId, rawValue) => {
    const nextValue = rawValue.trim();
    if (!nextValue) {
      setCanvasTexts((current) => current.filter((item) => item.id !== textId));
      return;
    }

    updateCanvasText(textId, { text: nextValue, isEditing: false });
  };

  const updatePersonalWidget = (widgetId, updates) => {
    setPersonalWidgets((current) => current.map((widget) => (
      widget.id === widgetId
        ? {
            ...widget,
            ...(typeof updates === 'function' ? updates(widget) : updates),
          }
        : widget
    )));
  };

  const removePersonalWidget = (widgetId) => {
    setPersonalWidgets((current) => current.filter((widget) => widget.id !== widgetId));
  };

  const getViewportWidgetPosition = (slot = 0) => {
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) {
      return { x: 980 + slot * 32, y: 140 + slot * 26 };
    }

    const viewportX = containerRect.width * 0.68;
    const viewportY = 112 + slot * 28;
    return {
      x: (viewportX - transform.x) / transform.scale,
      y: (viewportY - transform.y) / transform.scale,
    };
  };

  const buildPersonalWidget = (type) => {
    const createdAt = Date.now();
    const currentCount = personalWidgets.filter((widget) => widget.type === type).length;
    const position = getViewportWidgetPosition(currentCount);
    const baseWidget = {
      id: `${type}-${createdAt}`,
      type,
      x: position.x,
      y: position.y,
      isPinned: false,
      isCollapsed: false,
      createdAt,
    };

    if (type === 'stickyNote') {
      return {
        ...baseWidget,
        title: '',
        content: '',
        theme: NOTE_THEMES[currentCount % NOTE_THEMES.length],
      };
    }

    if (type === 'parkingLot') {
      return {
        ...baseWidget,
        items: [],
      };
    }

    if (type === 'clock') {
      return {
        ...baseWidget,
        is24Hour: true,
        secondaryTimezone: 'UTC',
      };
    }

    return {
      ...baseWidget,
      durationMinutes: 20,
      remainingSeconds: 20 * 60,
      isRunning: false,
      isCompleted: false,
      mode: '收敛',
    };
  };

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
    connectionPortMapRef.current = buildConnectionPortMap(relations);
  }, [relations]);

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
        const backendSections = syncSectionConnectionsFromRelations(
          mapBackendCardsToSections(filteredBackendCards, relations),
          relations,
        );

        const allCurrentCards = Object.values(current).flat();
        if (allCurrentCards.length === 0) {
          return backendSections;
        }

        const localCardIds = new Set(allCurrentCards.map(c => c.id));
        const newBackendCards = filteredBackendCards.filter(c => !localCardIds.has(c.id));

        if (newBackendCards.length === 0) {
          return syncSectionConnectionsFromRelations(current, relations);
        }

        const nextSections = { ...current };
        const newSections = mapBackendCardsToSections(newBackendCards, relations);

        Object.entries(newSections).forEach(([key, newCards]) => {
          nextSections[key] = [...(nextSections[key] || []), ...newCards];
        });

        return syncSectionConnectionsFromRelations(nextSections, relations);
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
    setIsTimelineOpen(true);
    setCardOffsets({});
    setIsPinned(true);
    setIsTimelineCollapsed(true);
    setTimelinePos({ x: 80, y: 800 });
    setTimelinePinnedPos({ x: 24, y: 720 });
    setIsBacklogPinned(true);
    setIsBacklogCollapsed(false);
    setBacklogPos({ x: 1200, y: 300 });
    setBacklogPinnedPos({ x: 940, y: 24 });
    setTransform({ x: 0, y: 0, scale: 1 });
    setCanvasTexts([]);
    setPersonalWidgets([]);
    setConnectorTarget(null);
    setIsWidgetPanelOpen(false);
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

    if (typeof storedState.isTimelineOpen === 'boolean') {
      setIsTimelineOpen(storedState.isTimelineOpen);
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

    if (typeof storedState.isTimelineCollapsed === 'boolean') {
      setIsTimelineCollapsed(storedState.isTimelineCollapsed);
    }

    if (
      storedState.timelinePos &&
      typeof storedState.timelinePos.x === 'number' &&
      typeof storedState.timelinePos.y === 'number'
    ) {
      setTimelinePos(storedState.timelinePos);
    }

    if (
      storedState.timelinePinnedPos &&
      typeof storedState.timelinePinnedPos.x === 'number' &&
      typeof storedState.timelinePinnedPos.y === 'number'
    ) {
      setTimelinePinnedPos(storedState.timelinePinnedPos);
    }

    if (typeof storedState.isBacklogPinned === 'boolean') {
      setIsBacklogPinned(storedState.isBacklogPinned);
    }

    if (typeof storedState.isBacklogCollapsed === 'boolean') {
      setIsBacklogCollapsed(storedState.isBacklogCollapsed);
    }

    if (
      storedState.backlogPos &&
      typeof storedState.backlogPos.x === 'number' &&
      typeof storedState.backlogPos.y === 'number'
    ) {
      setBacklogPos(storedState.backlogPos);
    }

    if (
      storedState.backlogPinnedPos &&
      typeof storedState.backlogPinnedPos.x === 'number' &&
      typeof storedState.backlogPinnedPos.y === 'number'
    ) {
      setBacklogPinnedPos(storedState.backlogPinnedPos);
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

    if (Array.isArray(storedState.personalWidgets)) {
      setPersonalWidgets(storedState.personalWidgets);
    } else {
      setPersonalWidgets([]);
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
      isTimelineOpen,
      cardOffsets,
      isPinned,
      isTimelineCollapsed,
      timelinePos,
      timelinePinnedPos,
      isBacklogPinned,
      isBacklogCollapsed,
      backlogPos,
      backlogPinnedPos,
      transform,
      canvasSections,
      canvasTexts,
      personalWidgets,
    };
    localStorage.setItem(canvasViewStorageKey, JSON.stringify(nextState));
  }, [canvasViewStorageKey, hasHydratedCanvasView, isBacklogOpen, isTimelineOpen, cardOffsets, isPinned, isTimelineCollapsed, timelinePos, timelinePinnedPos, isBacklogPinned, isBacklogCollapsed, backlogPos, backlogPinnedPos, transform, canvasSections, canvasTexts, personalWidgets]);

  useEffect(() => {
    if (!pendingTextFocusIdRef.current) return;

    const pendingId = pendingTextFocusIdRef.current;
    const targetExists = canvasTexts.some((item) => item.id === pendingId && item.isEditing);
    if (!targetExists) return;

    focusCanvasTextEditor(pendingId);
    pendingTextFocusIdRef.current = null;
  }, [canvasTexts]);

  useEffect(() => {
    const hasRunningTimer = personalWidgets.some((widget) => widget.type === 'focusTimer' && widget.isRunning);
    if (!hasRunningTimer) return;

    const intervalId = window.setInterval(() => {
      setPersonalWidgets((current) => current.map((widget) => {
        if (widget.type !== 'focusTimer' || !widget.isRunning) return widget;
        if (widget.remainingSeconds <= 1) {
          return {
            ...widget,
            remainingSeconds: 0,
            isRunning: false,
            isCompleted: true,
          };
        }
        return {
          ...widget,
          remainingSeconds: widget.remainingSeconds - 1,
        };
      }));
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [personalWidgets]);

  const handleAutoLayout = () => {
    setCardOffsets({});
    setTimelinePos({ x: 80, y: 800 });
    setTimelinePinnedPos({ x: 24, y: 720 });
    setBacklogPos({ x: 1200, y: 300 });
    setBacklogPinnedPos({ x: 940, y: 24 });
    setTransform({ x: 0, y: 0, scale: 1 });
  };

  const addWidgetToCanvas = (type) => {
    if (type === 'timeline') {
      setIsTimelineOpen(true);
      setIsPinned(true);
      setIsTimelineCollapsed(false);
      return;
    }

    if (type === 'backlog') {
      setIsBacklogOpen(true);
      setIsBacklogPinned(true);
      setIsBacklogCollapsed(false);
      return;
    }

    const existingWidget = personalWidgets.find((widget) => widget.type === type);
    if (existingWidget) {
      updatePersonalWidget(existingWidget.id, {
        isCollapsed: false,
        ...(existingWidget.isPinned ? {} : getViewportWidgetPosition(0)),
      });
      return;
    }

    setPersonalWidgets((current) => [...current, buildPersonalWidget(type)]);
  };

  const isWidgetEnabled = (type) => {
    if (type === 'timeline') return isTimelineOpen;
    if (type === 'backlog') return isBacklogOpen;
    return personalWidgets.some((widget) => widget.type === type);
  };

  const toggleWidgetEnabled = (type) => {
    if (type === 'timeline') {
      if (isTimelineOpen) {
        setIsTimelineOpen(false);
      } else {
        setIsTimelineOpen(true);
        setIsPinned(true);
        setIsTimelineCollapsed(false);
      }
      setIsWidgetPanelOpen(false);
      return;
    }

    if (type === 'backlog') {
      if (isBacklogOpen) {
        setIsBacklogOpen(false);
      } else {
        setIsBacklogOpen(true);
        setIsBacklogPinned(true);
        setIsBacklogCollapsed(false);
      }
      setIsWidgetPanelOpen(false);
      return;
    }

    const existingWidget = personalWidgets.find((widget) => widget.type === type);
    if (existingWidget) {
      removePersonalWidget(existingWidget.id);
      setIsWidgetPanelOpen(false);
      return;
    }

    addWidgetToCanvas(type);
    setIsWidgetPanelOpen(false);
  };

  const containerRef = useRef(null);
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (event) => {
      if (event.target.closest?.('[data-canvas-wheel-region="true"]')) {
        return;
      }

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
    if (event.target.closest?.('.figma-toolbar')) {
      return;
    }

    setIsWidgetPanelOpen(false);
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
      event.preventDefault();
      const rect = containerRef.current.getBoundingClientRect();
      const clientX = event.clientX;
      const clientY = event.clientY;
      const canvasX = (clientX - rect.left - transform.x) / transform.scale;
      const canvasY = (clientY - rect.top - transform.y) / transform.scale;
      const textId = 'text-' + Date.now();

      const newText = {
        id: textId,
        x: canvasX,
        y: canvasY,
        text: '',
        isEditing: true
      };

      pendingTextFocusIdRef.current = textId;
      setCanvasTexts(prev => [...prev, newText]);
      setActiveTool('select');
      return;
    }

    if (activeTool !== 'select') return;
    
    let target = event.target;
    while (target && target !== containerRef.current) {
      if (
        target.className?.includes?.('canvas-card') ||
        target.className?.includes?.('timeline-scrubber') ||
        target.className?.includes?.('workspace-widget') ||
        target.closest?.('.workspace-widget') ||
        target.tagName === 'BUTTON' ||
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.className?.includes?.('canvas-text-label')
      ) {
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
    let coordinateSpace = 'canvas';
    if (type === 'card') {
      source = cardOffsets[id] || { x: 0, y: 0 };
    } else if (type === 'timeline') {
      if (isPinned) {
        coordinateSpace = 'screen';
        source = timelinePinnedPos;
      } else {
        source = timelinePos;
      }
    } else if (type === 'backlog') {
      if (isBacklogPinned) {
        coordinateSpace = 'screen';
        source = backlogPinnedPos;
      } else {
        source = backlogPos;
      }
    } else if (type === 'widget') {
      const targetWidget = personalWidgets.find((widget) => widget.id === id);
      if (targetWidget?.isPinned) {
        const containerRect = containerRef.current?.getBoundingClientRect();
        const widgetRect = event.currentTarget
          ?.closest?.('.workspace-widget')
          ?.getBoundingClientRect?.();

        coordinateSpace = 'screen';
        source = widgetRect && containerRect
          ? {
              x: widgetRect.left - containerRect.left,
              y: widgetRect.top - containerRect.top,
            }
          : {
              x: targetWidget.pinnedScreenX ?? 0,
              y: targetWidget.pinnedScreenY ?? 0,
            };
      } else {
        source = targetWidget ? { x: targetWidget.x, y: targetWidget.y } : { x: 0, y: 0 };
      }
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
      coordinateSpace,
    };
  };

  const hoveredCardIdRef = useRef(null);
  useEffect(() => {
    hoveredCardIdRef.current = hoveredCardId;
  }, [hoveredCardId]);

  const resolveConnectionTarget = (clientX, clientY, startCardId) => {
    const lanesEl = document.querySelector('.canvas-lanes');
    if (!lanesEl) return null;

    const scale = transform.scale;
    const containerRect = lanesEl.getBoundingClientRect();
    const pointerX = (clientX - containerRect.left) / scale;
    const pointerY = (clientY - containerRect.top) / scale;

    let closestCardId = null;
    let closestPort = null;
    let closestDistance = Number.POSITIVE_INFINITY;
    let strongestExplicitMatch = null;

    document.querySelectorAll('.canvas-card').forEach((cardElement) => {
      const cardId = cardElement.id;
      if (!cardId || cardId === startCardId) return;

      const cardRect = cardElement.getBoundingClientRect();
      const cardLeft = (cardRect.left - containerRect.left) / scale;
      const cardRight = (cardRect.right - containerRect.left) / scale;
      const cardTop = (cardRect.top - containerRect.top) / scale;
      const cardBottom = (cardRect.bottom - containerRect.top) / scale;
      const ports = getCardPorts(getCardRectInCanvas(cardRect, containerRect, scale, cardId));

      const edgeCandidates = [
        { port: 'left', distance: Math.abs(pointerX - cardLeft), aligned: pointerY >= cardTop - CONNECT_SNAP_RADIUS && pointerY <= cardBottom + CONNECT_SNAP_RADIUS },
        { port: 'right', distance: Math.abs(pointerX - cardRight), aligned: pointerY >= cardTop - CONNECT_SNAP_RADIUS && pointerY <= cardBottom + CONNECT_SNAP_RADIUS },
        { port: 'top', distance: Math.abs(pointerY - cardTop), aligned: pointerX >= cardLeft - CONNECT_SNAP_RADIUS && pointerX <= cardRight + CONNECT_SNAP_RADIUS },
        { port: 'bottom', distance: Math.abs(pointerY - cardBottom), aligned: pointerX >= cardLeft - CONNECT_SNAP_RADIUS && pointerX <= cardRight + CONNECT_SNAP_RADIUS },
      ];

      edgeCandidates.forEach((candidate) => {
        if (!candidate.aligned || candidate.distance > EXPLICIT_PORT_SNAP_RADIUS) return;
        if (!strongestExplicitMatch || candidate.distance < strongestExplicitMatch.distance) {
          strongestExplicitMatch = { cardId, port: candidate.port, distance: candidate.distance };
        }
      });

      CARD_PORTS.forEach((port) => {
        const point = ports[port];
        const distance = Math.hypot(pointerX - point.x, pointerY - point.y);
        if (distance < closestDistance) {
          closestDistance = distance;
          closestCardId = cardId;
          closestPort = port;
        }
      });
    });

    if (strongestExplicitMatch) {
      return strongestExplicitMatch;
    }

    if (!closestCardId || !closestPort || closestDistance > CONNECT_SNAP_RADIUS) {
      return null;
    }

    return {
      cardId: closestCardId,
      port: closestPort,
      distance: closestDistance,
    };
  };

  useEffect(() => {
    const handleWindowPointerMove = (event) => {
      const session = dragSession.current;
      if (!session) return;

      const usesScreenSpace = session.coordinateSpace === 'screen';
      const deltaX = usesScreenSpace
        ? event.clientX - session.pointerX
        : (event.clientX - session.pointerX) / transform.scale;
      const deltaY = usesScreenSpace
        ? event.clientY - session.pointerY
        : (event.clientY - session.pointerY) / transform.scale;

      if (session.type === 'card') {
        setCardOffsets((current) => ({
          ...current,
          [session.id]: {
            x: session.startX + deltaX,
            y: session.startY + deltaY,
          },
        }));
      } else if (session.type === 'timeline') {
        if (session.coordinateSpace === 'screen') {
          setTimelinePinnedPos({
            x: session.startX + deltaX,
            y: session.startY + deltaY,
          });
        } else {
          setTimelinePos({
            x: session.startX + deltaX,
            y: session.startY + deltaY,
          });
        }
      } else if (session.type === 'backlog') {
        if (session.coordinateSpace === 'screen') {
          setBacklogPinnedPos({
            x: session.startX + deltaX,
            y: session.startY + deltaY,
          });
        } else {
          setBacklogPos({
            x: session.startX + deltaX,
            y: session.startY + deltaY,
          });
        }
      } else if (session.type === 'widget') {
        setPersonalWidgets((current) => current.map((widget) => (
          widget.id === session.id
            ? {
                ...widget,
                ...(session.coordinateSpace === 'screen'
                  ? {
                      pinnedScreenX: session.startX + deltaX,
                      pinnedScreenY: session.startY + deltaY,
                    }
                  : {
                      x: session.startX + deltaX,
                      y: session.startY + deltaY,
                    }),
              }
            : widget
        )));
      } else if (session.type === 'text') {
        setCanvasTexts((current) => current.map(t => t.id === session.id ? {
          ...t,
          x: session.startX + deltaX,
          y: session.startY + deltaY,
        } : t));
      } else if (session.type === 'connector') {
        const lanesEl = document.querySelector('.canvas-lanes');
        if (lanesEl) {
          const resolvedTarget = resolveConnectionTarget(event.clientX, event.clientY, session.startCardId);
          if (resolvedTarget?.cardId) {
            setConnectorTarget(resolvedTarget);
            const targetEl = document.getElementById(resolvedTarget.cardId);
            if (targetEl) {
              const snappedPoint = getPortPointByName(targetEl, lanesEl, transform.scale, resolvedTarget.port);
              setActiveConnector(prev => prev ? {
                ...prev,
                endX: snappedPoint.x,
                endY: snappedPoint.y,
                endPort: resolvedTarget.port,
              } : null);
              return;
            }
          }

          setConnectorTarget(null);
          const lanesRect = lanesEl.getBoundingClientRect();
          const endX = (event.clientX - lanesRect.left) / transform.scale;
          const endY = (event.clientY - lanesRect.top) / transform.scale;
          setActiveConnector(prev => prev ? { ...prev, endX, endY, endPort: null } : null);
        }
      }
    };

    const handleWindowPointerUp = (event) => {
      const session = dragSession.current;
      if (session && session.type === 'connector') {
        const target = resolveConnectionTarget(
          event.clientX,
          event.clientY,
          session.startCardId,
        );
        if (target && target.cardId !== session.startCardId) {
          handleAddConnection({
            startId: session.startCardId,
            endId: target.cardId,
            startPort: session.startPort,
            endPort: target.port,
          });
        }
        setConnectorTarget(null);
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
  }, [transform.scale, cardOffsets, timelinePos, timelinePinnedPos, backlogPos, backlogPinnedPos, personalWidgets, canvasTexts, isPinned, isBacklogPinned]);

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

  const handleAddConnection = async ({ startId, endId, startPort, endPort }) => {
    const existingRelationId = findRelationId(relations, startId, endId);
    const edgeKey = getArrowKey({ start: startId, end: endId });

    connectionPortMapRef.current = {
      ...connectionPortMapRef.current,
      [edgeKey]: { startPort, endPort },
    };

    setCanvasSections((prev) => applyConnectionToSections(prev, startId, endId));

    if (workspaceId && workspaceId !== 'demo') {
      if (existingRelationId) {
        const deleted = await apiDelete(`/api/canvas/workspaces/${workspaceId}/relations/${existingRelationId}`, null);
        if (!deleted?.deleted) {
          delete connectionPortMapRef.current[edgeKey];
          setMoveError('更新连线失败，请稍后重试');
          return;
        }
      }

      const created = await apiPost(`/api/canvas/workspaces/${workspaceId}/relations`, {
        kind: 'supports',
        from_card_id: startId,
        to_card_id: endId,
        note: '',
        metadata: {
          start_port: startPort,
          end_port: endPort,
        },
      }, null);

      if (!created?.relation) {
        delete connectionPortMapRef.current[edgeKey];
        setCanvasSections((prev) => removeConnectionFromSections(prev, startId, endId));
        setMoveError('新增连线失败，请稍后重试');
        return;
      }

      if (onRefresh) onRefresh();
    }
  };

  const handleDeleteConnection = async (startId, endId) => {
    const edgeKey = getArrowKey({ start: startId, end: endId });

    if (workspaceId && workspaceId !== 'demo') {
      const relationId = findRelationId(relations, startId, endId);
      if (!relationId) {
        setMoveError('未找到这条连线对应的关系记录，请刷新后再试');
        return;
      }

      delete connectionPortMapRef.current[edgeKey];
      setCanvasSections((prev) => removeConnectionFromSections(prev, startId, endId));
      const deleted = await apiDelete(`/api/canvas/workspaces/${workspaceId}/relations/${relationId}`, null);
      if (!deleted?.deleted) {
        const persistedPortMap = buildConnectionPortMap(relations);
        connectionPortMapRef.current = {
          ...connectionPortMapRef.current,
          ...(persistedPortMap[edgeKey] ? { [edgeKey]: persistedPortMap[edgeKey] } : {}),
        };
        setCanvasSections((prev) => applyConnectionToSections(prev, startId, endId));
        setMoveError('删除连线失败，请稍后重试');
        return;
      }

      if (onRefresh) onRefresh();
      return;
    }

    delete connectionPortMapRef.current[edgeKey];
    setCanvasSections((prev) => removeConnectionFromSections(prev, startId, endId));
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
      endPort: null,
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
    const allArrows = collectCanvasArrows(canvasSections, connectionPortMapRef.current);
    const selectedRelatedCardIds = getRelatedCardIds(selectedCardId, allArrows);
    const previewRelatedCardIds = selectedCardId ? new Set() : getRelatedCardIds(hoveredCardId, allArrows);

    const isSelectedSelf = selectedCardId === cardId;
    const isSelectedRelated = Boolean(selectedCardId) && selectedRelatedCardIds.has(cardId);
    const isPreviewSelf = !selectedCardId && hoveredCardId === cardId;
    const isPreviewRelated = !selectedCardId && previewRelatedCardIds.has(cardId);

    return { isSelectedSelf, isSelectedRelated, isPreviewSelf, isPreviewRelated };
  };

  const getCardRelationAccent = (cardId) => {
    const activeId = selectedCardId || (!selectedCardId ? hoveredCardId : null);
    if (!activeId || activeId === cardId) return null;

    const allArrows = collectCanvasArrows(canvasSections, connectionPortMapRef.current);
    const activeRelationColors = getFocusedRelationColors(allArrows, activeId);
    return activeRelationColors[cardId] || null;
  };

  const focusedCardId = selectedCardId || (!selectedCardId ? hoveredCardId : null);
  const shouldRevealArrows = activeTool === 'connector' || Boolean(focusedCardId);
  const allArrows = collectCanvasArrows(canvasSections, connectionPortMapRef.current);
  const selectedRelatedCardIds = getRelatedCardIds(selectedCardId, allArrows);
  const previewRelatedCardIds = selectedCardId ? new Set() : getRelatedCardIds(hoveredCardId, allArrows);
  const relationColors = getFocusedRelationColors(allArrows, focusedCardId);

  const getPersonalWidgetCollapsedTitle = (widget) => {
    if (widget.type === 'stickyNote') return widget.title?.trim() || '便签';
    if (widget.type === 'parkingLot') return '停车区';
    if (widget.type === 'clock') return '时钟';
    if (widget.type === 'focusTimer') return '专注计时器';
    return '挂件';
  };

  const getPersonalWidgetCollapsedWidth = (widget) =>
    getCollapsedWidgetWidthByTitle(getPersonalWidgetCollapsedTitle(widget));

  const getPersonalWidgetWidth = (widget) => {
    if (widget.isCollapsed) return getPersonalWidgetCollapsedWidth(widget);
    if (widget.type === 'parkingLot') return 320;
    if (widget.type === 'clock') return 232;
    if (widget.type === 'focusTimer') return 312;
    return 240;
  };

  const getPersonalWidgetExpandedHeight = (widget) => {
    if (widget.type === 'parkingLot') return 286;
    if (widget.type === 'clock') return 188;
    if (widget.type === 'focusTimer') return 404;
    return 246;
  };

  const getScreenBounds = () => {
    const containerRect = containerRef.current?.getBoundingClientRect();
    return {
      width: containerRect?.width ?? window.innerWidth,
      height: containerRect?.height ?? window.innerHeight,
    };
  };

  const clampScreenValue = (value, min, max) => Math.max(min, Math.min(value, max));

  const resolveScreenWidgetLayout = ({
    anchorX,
    anchorY,
    collapsedWidth = getCollapsedWidgetWidthByTitle('挂件'),
    collapsedHeight = COLLAPSED_WIDGET_HEIGHT,
    expandedWidth,
    expandedHeight,
  }) => {
    const bounds = getScreenBounds();
    const collapsedLeft = clampScreenValue(
      anchorX,
      SCREEN_WIDGET_PADDING,
      Math.max(SCREEN_WIDGET_PADDING, bounds.width - collapsedWidth - SCREEN_WIDGET_PADDING),
    );
    const collapsedTop = clampScreenValue(
      anchorY,
      SCREEN_WIDGET_PADDING,
      Math.max(SCREEN_WIDGET_PADDING, bounds.height - collapsedHeight - SCREEN_WIDGET_PADDING),
    );

    const opensRight = collapsedLeft + collapsedWidth / 2 < bounds.width / 2;
    const opensDown = collapsedTop + collapsedHeight / 2 < bounds.height / 2;

    const expandedLeft = clampScreenValue(
      opensRight ? collapsedLeft : collapsedLeft + collapsedWidth - expandedWidth,
      SCREEN_WIDGET_PADDING,
      Math.max(SCREEN_WIDGET_PADDING, bounds.width - expandedWidth - SCREEN_WIDGET_PADDING),
    );
    const expandedTop = clampScreenValue(
      opensDown ? collapsedTop : collapsedTop + collapsedHeight - expandedHeight,
      SCREEN_WIDGET_PADDING,
      Math.max(SCREEN_WIDGET_PADDING, bounds.height - expandedHeight - SCREEN_WIDGET_PADDING),
    );

    return {
      collapsed: {
        left: collapsedLeft,
        top: collapsedTop,
        width: collapsedWidth,
        height: collapsedHeight,
      },
      expanded: {
        left: expandedLeft,
        top: expandedTop,
        width: expandedWidth,
        height: expandedHeight,
      },
    };
  };

  const getPinnedWidgetStyle = (widget) => {
    const containerBounds = getScreenBounds();
    if (
      typeof widget.pinnedScreenX === 'number' &&
      typeof widget.pinnedScreenY === 'number'
    ) {
      const collapsedWidth = getPersonalWidgetCollapsedWidth(widget);
      const layout = resolveScreenWidgetLayout({
        anchorX: widget.pinnedScreenX,
        anchorY: widget.pinnedScreenY,
        collapsedWidth,
        expandedWidth: getPersonalWidgetWidth({ ...widget, isCollapsed: false }),
        expandedHeight: getPersonalWidgetExpandedHeight(widget),
      });
      return {
        position: 'absolute',
        ...(widget.isCollapsed ? layout.collapsed : layout.expanded),
        zIndex: 92,
        transition: WIDGET_LAYOUT_TRANSITION,
      };
    }

    const rightBase = isChatOpen ? 452 : 156;
    const pinnedNoteIndex = personalWidgets.filter(
      (entry) => entry.type === 'stickyNote' && entry.isPinned,
    ).findIndex((entry) => entry.id === widget.id);

    if (widget.type === 'parkingLot') {
      const collapsedWidth = getPersonalWidgetCollapsedWidth(widget);
      const layout = resolveScreenWidgetLayout({
        anchorX: 24,
        anchorY: 88,
        collapsedWidth,
        expandedWidth: 320,
        expandedHeight: getPersonalWidgetExpandedHeight(widget),
      });
      return {
        position: 'absolute',
        ...(widget.isCollapsed ? layout.collapsed : layout.expanded),
        zIndex: 92,
        transition: WIDGET_LAYOUT_TRANSITION,
      };
    }

    if (widget.type === 'clock') {
      const collapsedWidth = getPersonalWidgetCollapsedWidth(widget);
      const layout = resolveScreenWidgetLayout({
        anchorX: containerBounds.width - rightBase - collapsedWidth,
        anchorY: containerBounds.height - 92 - COLLAPSED_WIDGET_HEIGHT,
        collapsedWidth,
        expandedWidth: 232,
        expandedHeight: getPersonalWidgetExpandedHeight(widget),
      });
      return {
        position: 'absolute',
        ...(widget.isCollapsed ? layout.collapsed : layout.expanded),
        zIndex: 92,
        transition: WIDGET_LAYOUT_TRANSITION,
      };
    }

    if (widget.type === 'focusTimer') {
      const collapsedWidth = getPersonalWidgetCollapsedWidth(widget);
      const layout = resolveScreenWidgetLayout({
        anchorX: containerBounds.width - rightBase - 326 - collapsedWidth,
        anchorY: containerBounds.height - 92 - COLLAPSED_WIDGET_HEIGHT,
        collapsedWidth,
        expandedWidth: 312,
        expandedHeight: getPersonalWidgetExpandedHeight(widget),
      });
      return {
        position: 'absolute',
        ...(widget.isCollapsed ? layout.collapsed : layout.expanded),
        zIndex: 92,
        transition: WIDGET_LAYOUT_TRANSITION,
      };
    }

    const collapsedWidth = getPersonalWidgetCollapsedWidth(widget);
    const stickyAnchorX = containerBounds.width - rightBase - collapsedWidth;
    const stickyAnchorY = 568 + Math.max(pinnedNoteIndex, 0) * 148;
    const layout = resolveScreenWidgetLayout({
      anchorX: stickyAnchorX,
      anchorY: stickyAnchorY,
      collapsedWidth,
      expandedWidth: 240,
      expandedHeight: getPersonalWidgetExpandedHeight(widget),
    });
    return {
      position: 'absolute',
      ...(widget.isCollapsed ? layout.collapsed : layout.expanded),
      zIndex: 92,
      transition: WIDGET_LAYOUT_TRANSITION,
    };
  };

  const renderPersonalWidget = (widget) => {
    const sharedProps = {
      widget,
      onUpdate: (updates) => updatePersonalWidget(widget.id, updates),
      onPinToggle: () => updatePersonalWidget(widget.id, { isPinned: !widget.isPinned }),
      onDragStart: (event) => beginFreeDrag('widget', widget.id, event),
    };

    if (widget.type === 'stickyNote') {
      return <StickyNoteWidget {...sharedProps} />;
    }

    if (widget.type === 'parkingLot') {
      return <ParkingLotWidget {...sharedProps} />;
    }

    if (widget.type === 'clock') {
      return <ClockWidget {...sharedProps} />;
    }

    return <FocusTimerWidget {...sharedProps} />;
  };

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
          onConnectStart={(port, event) => handleConnectStart(card.id, port, event)}
          isConnectorSource={activeConnector?.startCardId === card.id}
          isConnectorTarget={connectorTarget?.cardId === card.id}
        />
      </div>
    );
  };

  const focusCardOnCanvas = (cardId) => {
    setSelectedCardId(cardId);

    window.requestAnimationFrame(() => {
      const container = containerRef.current;
      const cardEl = document.getElementById(cardId);
      if (!container || !cardEl) return;

      const containerRect = container.getBoundingClientRect();
      const cardRect = cardEl.getBoundingClientRect();
      const containerCenterX = containerRect.width * 0.52;
      const containerCenterY = containerRect.height * 0.36;
      const cardCenterX = cardRect.left - containerRect.left + cardRect.width / 2;
      const cardCenterY = cardRect.top - containerRect.top + cardRect.height / 2;

      setTransform((current) => ({
        ...current,
        x: current.x + (containerCenterX - cardCenterX),
        y: current.y + (containerCenterY - cardCenterY),
      }));
    });
  };

  const timelinePinnedLayout = resolveScreenWidgetLayout({
    anchorX: timelinePinnedPos.x,
    anchorY: timelinePinnedPos.y,
    collapsedWidth: getSystemWidgetCollapsedWidth('timeline'),
    expandedWidth: 720,
    expandedHeight: 160,
  });

  const backlogPinnedLayout = resolveScreenWidgetLayout({
    anchorX: backlogPinnedPos.x,
    anchorY: backlogPinnedPos.y,
    collapsedWidth: getSystemWidgetCollapsedWidth('backlog'),
    expandedWidth: 320,
    expandedHeight: 520,
  });

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
      <div
        className="figma-toolbar"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
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

        <div className="figma-toolbar-divider" />

        <div className="widget-toolbar-entry">
          <button
            className={`figma-toolbar-btn figma-toolbar-widget-btn${isWidgetPanelOpen ? ' active' : ''}`}
            title="添加挂件"
            onClick={() => setIsWidgetPanelOpen((current) => !current)}
          >
            <Shapes size={16} />
          </button>

          {isWidgetPanelOpen && (
            <div className="widget-toolbar-panel" onClick={(event) => event.stopPropagation()}>
              <div className="widget-toolbar-panel-header">
                <span className="widget-toolbar-panel-title">添加挂件</span>
                <span className="widget-toolbar-panel-desc">先加进工作台，运行态操作都在组件本身完成。</span>
              </div>

              <div className="widget-toolbar-list">
                {WIDGET_LIBRARY.map((widgetItem) => {
                  const Icon = widgetItem.icon;
                  const isEnabled = isWidgetEnabled(widgetItem.type);
                  return (
                    <div key={widgetItem.type} className="widget-toolbar-item">
                      <div className="widget-toolbar-item-icon">
                        <Icon size={15} />
                      </div>
                      <div className="widget-toolbar-item-copy">
                        <span className="widget-toolbar-item-name">{widgetItem.name}</span>
                        <span className="widget-toolbar-item-desc">{widgetItem.description}</span>
                      </div>
                      <button
                        type="button"
                        className="widget-toolbar-add-btn"
                        onClick={() => toggleWidgetEnabled(widgetItem.type)}
                      >
                        {isEnabled ? '停用' : '启用'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
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
                const activeId = selectedCardId || (!selectedCardId ? hoveredCardId : null);
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
                visualState={
                  !shouldRevealArrows
                    ? 'hidden'
                    : arrowIsDimmed
                      ? 'hidden'
                      : activeTool === 'connector' && !focusedCardId
                        ? 'muted'
                        : getArrowPresentation(arr, focusedCardId).visualState
                }
                accentColor={relationColors[getArrowKey(arr)]}
                outIndex={arr.startOffsetIndex}
                outCount={arr.startOffsetTotal}
                inIndex={arr.endOffsetIndex}
                inCount={arr.endOffsetTotal}
                startPort={arr.startPort}
                endPort={arr.endPort}
                onDelete={handleDeleteConnection}
                canDelete={activeTool === 'connector'}
              />
            );
          })}

          {activeConnector && (
            <TempConnectionLine
              startCardId={activeConnector.startCardId}
              startPort={activeConnector.startPort}
              targetCardId={connectorTarget?.cardId || null}
              endX={activeConnector.endX}
              endY={activeConnector.endY}
              endPort={activeConnector.endPort}
              transform={transform}
            />
          )}

          <CanvasTextLayer
            canvasTexts={canvasTexts}
            onBeginDrag={(textId, event) => beginFreeDrag('text', textId, event)}
            onTextChange={(textId, nextText) => updateCanvasText(textId, { text: nextText })}
            onTextFinishEdit={finishCanvasTextEdit}
            onTextStartEdit={(textId) => {
              pendingTextFocusIdRef.current = textId;
              updateCanvasText(textId, { isEditing: true });
            }}
          />

          {personalWidgets.filter((widget) => !widget.isPinned).map((widget) => (
            <div
              key={widget.id}
              style={{
                position: 'absolute',
                left: widget.x,
                top: widget.y,
                width: getPersonalWidgetWidth(widget),
                zIndex: 18,
                transition: WIDGET_LAYOUT_TRANSITION,
              }}
            >
              {renderPersonalWidget(widget)}
            </div>
          ))}

          {/* 画布内漂移时间轴 */}
          {isTimelineOpen && !isPinned && (
            <div 
              style={{
                position: 'absolute',
                left: timelinePos.x,
                top: timelinePos.y,
                width: isTimelineCollapsed ? getSystemWidgetCollapsedWidth('timeline') : '720px',
                zIndex: 10,
                transition: 'width 0.26s cubic-bezier(0.2, 0, 0, 1)',
              }}
            >
              <TimelineScrubber 
                isPinned={false}
                isCollapsed={isTimelineCollapsed}
                onPinToggle={() => setIsPinned(true)}
                onDragStart={(event) => beginFreeDrag('timeline', 'timeline', event)}
                onCollapsedChange={setIsTimelineCollapsed}
                canvasSections={canvasSections}
                onFocusCard={focusCardOnCanvas}
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
                width: isBacklogCollapsed ? getSystemWidgetCollapsedWidth('backlog') : '320px',
                zIndex: 10,
              }}
            >
              <ActiveBacklogPanel 
                isChatOpen={isChatOpen}
                isPinned={false}
                onPinToggle={() => setIsBacklogPinned(true)}
                isCollapsed={isBacklogCollapsed}
                onCollapsedChange={setIsBacklogCollapsed}
                onDragStart={(event) => beginFreeDrag('backlog', 'backlog', event)}
                canvasSections={canvasSections}
                selectedCardId={selectedCardId}
                setSelectedCardId={setSelectedCardId}
                onFocusCard={focusCardOnCanvas}
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

      {personalWidgets.filter((widget) => widget.isPinned).map((widget) => (
        <div key={widget.id} style={getPinnedWidgetStyle(widget)}>
          {renderPersonalWidget(widget)}
        </div>
      ))}

      {/* 底部时间轴 (钉住状态下固定在屏幕左下角偏极边缘) */}
      {isTimelineOpen && isPinned && (
        <TimelineScrubber
          isPinned={true}
          isCollapsed={isTimelineCollapsed}
          onCollapsedChange={setIsTimelineCollapsed}
          onPinToggle={() => setIsPinned(false)}
          onDragStart={(event) => beginFreeDrag('timeline', 'timeline', event)}
          canvasSections={canvasSections}
          onFocusCard={focusCardOnCanvas}
          style={{
            ...(isTimelineCollapsed ? timelinePinnedLayout.collapsed : timelinePinnedLayout.expanded),
            bottom: 'auto',
          }}
        />
      )}

      {/* 活跃缺口 (Active Backlog) 悬浮卡片看板 (钉住状态下固定在右上角) */}
      {isBacklogOpen && isBacklogPinned && (
        <ActiveBacklogPanel 
          isChatOpen={isChatOpen}
          isPinned={true}
          isCollapsed={isBacklogCollapsed}
          onCollapsedChange={setIsBacklogCollapsed}
          onPinToggle={() => setIsBacklogPinned(false)}
          onDragStart={(event) => beginFreeDrag('backlog', 'backlog', event)}
          canvasSections={canvasSections}
          selectedCardId={selectedCardId}
          setSelectedCardId={setSelectedCardId}
          onFocusCard={focusCardOnCanvas}
          uploadedMaterials={uploadedMaterials}
          style={{
            ...(isBacklogCollapsed ? backlogPinnedLayout.collapsed : backlogPinnedLayout.expanded),
            right: 'auto',
          }}
        />
      )}
    </div>
  );
}
