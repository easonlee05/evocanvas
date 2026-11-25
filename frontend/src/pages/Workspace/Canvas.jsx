import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import './Canvas.css';
import {
  Layers,
  MousePointer,
  MoveUpRight,
  Shapes,
  Sparkles,
  Square,
  Type,
} from 'lucide-react';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';
import { reconcileCanvasProjection } from './canvasProjection.js';
import { apiPost, apiPatchWithStatus, apiDelete } from '../../api';
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
  updateCanvasCard,
} from './canvasEditing.js';
import {
  CANVAS_VIEW_STATE_VERSION,
  getCanvasViewStateStorageKey,
  readStoredCanvasViewState,
} from './workspaceSession';
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
} from './CanvasEdges.jsx';
import {
  collectCardGeometry,
  getCanvasPortPoint,
  normalizeCardGeometry,
  resolveConnectionTargetAtPoint,
} from './canvasEngine/geometry.js';
import {
  createDragSession,
  getDraggedPosition,
} from './canvasEngine/drag.js';
import {
  screenPointToCanvas,
  translateViewport,
  zoomViewportAtPoint,
} from './canvasEngine/viewport.js';
import {
  LANE_DEFINITIONS,
  CONNECT_SNAP_RADIUS,
  EXPLICIT_PORT_SNAP_RADIUS,
  NOTE_THEMES,
  COLLAPSED_WIDGET_HEIGHT,
  SCREEN_WIDGET_PADDING,
  AGENT_ENTRY_WIDTH,
  WIDGET_ENTRY_GAP,
  WIDGET_LAYOUT_TRANSITION,
  createEmptyCanvasSections,
  getCollapsedWidgetWidthByTitle,
  getSystemWidgetCollapsedWidth,
  WIDGET_LIBRARY,
  normalizeEditableValue,
  CanvasCard,
} from './CanvasCardNode.jsx';

export default function Canvas({ 
  isChatOpen = true,
  workspaceId,
  isHydrating = false,
  cards = [],
  relations = [],
  selectedCardId,
  setSelectedCardId,
  onRefresh,
  uploadedMaterials = [],
}) {
  const [viewMode] = useState('convergence'); // convergence | problem | option | decision | handoff
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
  // 钉住挂件的默认位置由当前画布尺寸和入口位置实时计算；只有用户拖动后才保存坐标。
  const [timelinePinnedPos, setTimelinePinnedPos] = useState(null);
  const [isBacklogPinned, setIsBacklogPinned] = useState(true);
  const [isBacklogCollapsed, setIsBacklogCollapsed] = useState(true);
  const [backlogPos, setBacklogPos] = useState({ x: 1200, y: 300 });
  const [backlogPinnedPos, setBacklogPinnedPos] = useState(null);
  const [personalWidgets, setPersonalWidgets] = useState([]);
  const [activeCardMenuId, setActiveCardMenuId] = useState(null);
  const [isWidgetPanelOpen, setIsWidgetPanelOpen] = useState(false);

  const [canvasSections, setCanvasSections] = useState(() => (
    workspaceId === 'demo' ? createInitialCanvasSections(DEMO_CANVAS_SECTIONS) : createEmptyCanvasSections()
  ));
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [cardGeometry, setCardGeometry] = useState({});
  const [hoveredCardId, setHoveredCardId] = useState(null);
  const [connectorTarget, setConnectorTarget] = useState(null);
  const [editingState, setEditingState] = useState(null);
  const [draggingCardId, setDraggingCardId] = useState(null);
  const [moveError, setMoveError] = useState(null);
  const [hasHydratedCanvasView, setHasHydratedCanvasView] = useState(false);
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const panFrame = useRef(null);
  const dragSession = useRef(null);
  const containerRef = useRef(null);
  const canvasLanesRef = useRef(null);
  const cardGeometryRef = useRef({});
  const cardGeometryVersionRef = useRef({});
  const hasRestoredViewStateRef = useRef(false);
  const autoFitCanvasRef = useRef(true);
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
    return screenPointToCanvas({ x: viewportX, y: viewportY }, transform);
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
      // Python Canvas API uses `card_id`; legacy/demo payloads use `id`.
      // Normalize both at the projection boundary so selection, relations,
      // local view state and refreshes keep the same card identity.
      const cardId = card.id || card.card_id;
      let sectionKey = 'evidence';
      if (card.kind === 'problem') sectionKey = 'problems';
      else if (card.kind === 'clarification') sectionKey = 'clarify';
      else if (card.kind === 'constraint') sectionKey = 'rules';
      else if (card.kind === 'handoff') sectionKey = 'planning';
      else if (card.kind === 'decision' || card.kind === 'option') {
        // L3 规格：handoff 不是对象类型，planning section 的卡片在后端统一存为 decision。
        // 通过 metadata.section_hint 区分其归属 section，未标记时默认归 options。
        sectionKey = card.metadata?.section_hint === 'planning' ? 'planning' : 'options';
      }

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
        id: cardId,
        isProjection: true,
        kind: card.kind,
        title: card.title,
        desc: card.summary || card.desc,
        tags: mappedTags,
        status: card.status,
        confidence: card.confidence,
        structureKind: card.metadata?.structured_kind
          || (sectionKey === 'rules' || sectionKey === 'planning' ? 'checkpoints' : 'list'),
        structuredItems: card.metadata?.structured_items || [],
        next: nextMap[cardId] || [],
        source: card.metadata?.source_persona ? {
          label: '来源',
          name: card.metadata.source_persona.name,
          avatar: card.metadata.source_persona.avatar || card.metadata.source_persona.name?.[0],
          avatarTone: card.metadata.source_persona.avatar_tone || 'slate',
          avatarSrc: card.metadata.source_persona.avatar_src || null,
        } : null,
        owner: card.metadata?.owner_persona ? {
          label: card.metadata.owner_persona.label || '负责人',
          name: card.metadata.owner_persona.name,
          avatar: card.metadata.owner_persona.avatar || card.metadata.owner_persona.name?.[0],
          avatarTone: card.metadata.owner_persona.avatar_tone || 'slate',
          avatarSrc: card.metadata.owner_persona.avatar_src || null,
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
        
        const filteredBackendCards = cards.filter(c => !deletedCardIds.has(c.id || c.card_id));
        const backendSections = syncSectionConnectionsFromRelations(
          mapBackendCardsToSections(filteredBackendCards, relations),
          relations,
        );

        return syncSectionConnectionsFromRelations(reconcileCanvasProjection(current, backendSections), relations);
      });
    } else {
      // 非 demo 工作区的空响应必须保持为空，不能回退到演示场景。
      // 这样新工作区会显示明确的空状态，直到真实卡片由后端返回。
      if (workspaceId !== 'demo') setCanvasSections(createEmptyCanvasSections());
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
    setTimelinePinnedPos(null);
    setIsBacklogPinned(true);
    setIsBacklogCollapsed(true);
    setBacklogPos({ x: 1200, y: 300 });
    setBacklogPinnedPos(null);
    setTransform({ x: 0, y: 0, scale: 1 });
    autoFitCanvasRef.current = true;
    setCanvasSections(workspaceId === 'demo' ? createInitialCanvasSections(DEMO_CANVAS_SECTIONS) : createEmptyCanvasSections());
    setCanvasTexts([]);
    setPersonalWidgets([]);
    setConnectorTarget(null);
    setIsWidgetPanelOpen(false);
  }, [workspaceId]);

  useEffect(() => {
    if (hasRestoredViewStateRef.current) return;

    const storedState = readStoredCanvasViewState(canvasViewStorageKey);
    if (!storedState || storedState.viewVersion !== CANVAS_VIEW_STATE_VERSION) {
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

    if (workspaceId === 'demo' &&
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
      viewVersion: CANVAS_VIEW_STATE_VERSION,
      canvasSections,
      canvasTexts,
      personalWidgets,
    };
    localStorage.setItem(canvasViewStorageKey, JSON.stringify(nextState));
  }, [canvasViewStorageKey, hasHydratedCanvasView, isBacklogOpen, isTimelineOpen, cardOffsets, isPinned, isTimelineCollapsed, timelinePos, timelinePinnedPos, isBacklogPinned, isBacklogCollapsed, backlogPos, backlogPinnedPos, transform, canvasSections, canvasTexts, personalWidgets]);

  // 桌面端首次打开时把固定画布缩放到“助手面板左侧的可用区域”；用户开始平移或缩放后不再抢夺视角。
  useEffect(() => {
    const container = containerRef.current;
    const lanes = canvasLanesRef.current;
    if (!container || !lanes || !hasHydratedCanvasView || !autoFitCanvasRef.current) return undefined;

    const fitCanvas = () => {
      const isCompact = window.matchMedia('(max-width: 900px)').matches;
      if (isCompact) {
        setTransform((current) => current.scale === 1 && current.x === 0 && current.y === 0
          ? current
          : { x: 0, y: 0, scale: 1 });
        return;
      }

      const naturalWidth = lanes.offsetWidth;
      if (!naturalWidth) return;
      const bounds = container.getBoundingClientRect();
      const reservedForChat = isChatOpen ? 452 : 32;
      const availableWidth = Math.max(520, bounds.width - reservedForChat);
      const scale = Math.min(1, availableWidth / naturalWidth);
      const x = Math.max(24, (availableWidth - naturalWidth * scale) / 2);
      setTransform((current) => (
        Math.abs(current.scale - scale) < 0.01 && Math.abs(current.x - x) < 1
          ? current
          : { x, y: 24, scale }
      ));
    };

    fitCanvas();
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(fitCanvas) : null;
    observer?.observe(container);
    observer?.observe(lanes);
    return () => observer?.disconnect();
  }, [hasHydratedCanvasView, canvasSections, isChatOpen]);

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
    setTimelinePinnedPos(null);
    setBacklogPos({ x: 1200, y: 300 });
    setBacklogPinnedPos(null);
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

    const existingWidget = type === 'stickyNote' ? null : personalWidgets.find((widget) => widget.type === type);
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

    if (type === 'stickyNote') {
      addWidgetToCanvas(type);
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

  useLayoutEffect(() => {
    const lanesElement = canvasLanesRef.current;
    if (!lanesElement) return undefined;

    let frameId = null;
    const refreshGeometry = () => {
      const containerRect = lanesElement.getBoundingClientRect();
      const rawGeometry = collectCardGeometry(
        lanesElement.querySelectorAll('.canvas-card[id]'),
        containerRect,
        transform.scale,
      );

      const nextGeometry = {};
      const nextVersions = {};
      Object.entries(rawGeometry).forEach(([cardId, rawGeom]) => {
        const prevVersion = cardGeometryVersionRef.current[cardId] || 0;
        const prev = cardGeometryRef.current[cardId];
        const moved = !prev
          || prev.left !== rawGeom.left
          || prev.top !== rawGeom.top
          || prev.width !== rawGeom.width
          || prev.height !== rawGeom.height;
        if (!moved) {
          nextVersions[cardId] = prevVersion;
          nextGeometry[cardId] = prev;
          return;
        }
        const version = prevVersion + 1;
        nextVersions[cardId] = version;
        nextGeometry[cardId] = normalizeCardGeometry(rawGeom, version);
      });

      cardGeometryVersionRef.current = nextVersions;
      cardGeometryRef.current = nextGeometry;
      setCardGeometry(nextGeometry);
    };

    const scheduleRefresh = () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(refreshGeometry);
    };

    scheduleRefresh();

    const resizeObserver = typeof ResizeObserver === 'function'
      ? new ResizeObserver(scheduleRefresh)
      : null;
    resizeObserver?.observe(lanesElement);
    lanesElement.querySelectorAll('.canvas-card[id]').forEach((element) => {
      resizeObserver?.observe(element);
    });

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
    };
  }, [canvasSections, cardOffsets, transform.x, transform.y, transform.scale]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let wheelFrame = null;
    let pendingDelta = 0;

    const flushWheel = () => {
      wheelFrame = null;
      const delta = pendingDelta;
      pendingDelta = 0;
      if (delta === 0) return;
      const rect = container.getBoundingClientRect();
      setTransform((current) => zoomViewportAtPoint(
        current,
        {
          x: lastWheelClientX - rect.left,
          y: lastWheelClientY - rect.top,
        },
        delta,
      ));
    };

    let lastWheelClientX = 0;
    let lastWheelClientY = 0;

    const handleWheel = (event) => {
      if (event.target.closest?.('[data-canvas-wheel-region="true"]')) {
        return;
      }

      event.preventDefault();
      lastWheelClientX = event.clientX;
      lastWheelClientY = event.clientY;
      pendingDelta += event.deltaY;

      if (wheelFrame === null) {
        wheelFrame = requestAnimationFrame(flushWheel);
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
      if (wheelFrame !== null) cancelAnimationFrame(wheelFrame);
    };
  }, []);

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
      const { x: canvasX, y: canvasY } = screenPointToCanvas(
        { x: clientX - rect.left, y: clientY - rect.top },
        transform,
      );
      
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
      const { x: canvasX, y: canvasY } = screenPointToCanvas(
        { x: clientX - rect.left, y: clientY - rect.top },
        transform,
      );
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

    autoFitCanvasRef.current = false;
    
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
    // setPointerCapture 在指针已失效（合成事件、边缘场景）时会抛
    // NotFoundError，用 try-catch 保护避免整页崩溃
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch (_e) { /* 指针已失效，平移仍可正常工作 */ }
  };

  const panLatest = useRef({ x: 0, y: 0 });

  const handlePointerMove = (event) => {
    if (!isDragging.current) return;
    panLatest.current = {
      x: event.clientX - dragStart.current.x,
      y: event.clientY - dragStart.current.y,
    };
    if (panFrame.current !== null) return;
    panFrame.current = requestAnimationFrame(() => {
      panFrame.current = null;
      const { x: newX, y: newY } = panLatest.current;
      setTransform((current) => translateViewport(current, {
        x: newX - current.x,
        y: newY - current.y,
      }));
    });
  };

  const handlePointerUp = (event) => {
    if (isDragging.current) {
      isDragging.current = false;
      if (panFrame.current !== null) {
        cancelAnimationFrame(panFrame.current);
        panFrame.current = null;
      }
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch (_e) { /* 指针已释放，无需操作 */ }
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
        source = timelinePinnedPos || getDefaultPinnedWidgetPosition('timeline', getSystemWidgetCollapsedWidth('timeline'));
      } else {
        source = timelinePos;
      }
    } else if (type === 'backlog') {
      if (isBacklogPinned) {
        coordinateSpace = 'screen';
        source = backlogPinnedPos || getDefaultPinnedWidgetPosition('backlog', getSystemWidgetCollapsedWidth('backlog'));
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

    dragSession.current = createDragSession({
      type,
      id,
      pointer: { x: event.clientX, y: event.clientY },
      start: source,
      coordinateSpace,
    });
  };

  const hoveredCardIdRef = useRef(null);
  useEffect(() => {
    hoveredCardIdRef.current = hoveredCardId;
  }, [hoveredCardId]);

  const resolveConnectionTarget = (clientX, clientY, startCardId) => {
    const lanesElement = canvasLanesRef.current;
    if (!lanesElement) return null;

    const lanesRect = lanesElement.getBoundingClientRect();
    const point = screenPointToCanvas(
      {
        x: clientX - lanesRect.left,
        y: clientY - lanesRect.top,
      },
      { x: 0, y: 0, scale: transform.scale },
    );

    return resolveConnectionTargetAtPoint(
      point,
      cardGeometryRef.current,
      startCardId,
      {
        connectSnapRadius: CONNECT_SNAP_RADIUS,
        explicitPortSnapRadius: EXPLICIT_PORT_SNAP_RADIUS,
      },
    );
  };

  useEffect(() => {
    const handleWindowPointerMove = (event) => {
      const session = dragSession.current;
      if (!session) return;

      const nextPosition = getDraggedPosition(
        session,
        { x: event.clientX, y: event.clientY },
        transform.scale,
      );
      const deltaX = nextPosition.x - session.startX;
      const deltaY = nextPosition.y - session.startY;

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
        const lanesEl = canvasLanesRef.current;
        if (lanesEl) {
          const resolvedTarget = resolveConnectionTarget(event.clientX, event.clientY, session.startCardId);
          if (resolvedTarget?.cardId) {
            setConnectorTarget(resolvedTarget);
            const targetRect = cardGeometryRef.current[resolvedTarget.cardId];
            if (targetRect) {
              const snappedPoint = getCanvasPortPoint(targetRect, resolvedTarget.port);
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
          const { x: endX, y: endY } = screenPointToCanvas(
            {
              x: event.clientX - lanesRect.left,
              y: event.clientY - lanesRect.top,
            },
            { x: 0, y: 0, scale: transform.scale },
          );
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

    const normalizedValue = normalizeEditableValue(newValue);
    const normalizedCurrent = normalizeEditableValue(targetCard[field]);

    if (Array.isArray(normalizedValue) && Array.isArray(normalizedCurrent)) {
      if (JSON.stringify(normalizedValue) === JSON.stringify(normalizedCurrent)) return;
    } else if (normalizedValue === normalizedCurrent) {
      return;
    }

    setCanvasSections((current) =>
      updateCanvasCard(current, cardId, { [field]: newValue }),
    );

    if (workspaceId && workspaceId !== 'demo') {
      // L3 规格：patch_card 只接受展示字段 title/summary/tags，kind/status 不可写。
      // 稳定态卡片修订会触发 409 chat_confirmation_required，此处显性引导走 Chat 确认流，
      // 不静默回滚，也不绕过用户确认。
      const result = await apiPatchWithStatus(
        `/api/canvas/workspaces/${workspaceId}/cards/${cardId}`,
        {
          title: field === 'title' ? newValue : targetCard.title,
          summary: field === 'desc' ? newValue : targetCard.desc,
        },
      );
      if (result.ok) {
        if (onRefresh) onRefresh();
      } else if (result.status === 409 && result.data?.reason === 'chat_confirmation_required') {
        // 回滚本地乐观更新，避免本地与后端稳定态不一致
        setCanvasSections((current) => updateCanvasCard(current, cardId, { [field]: targetCard[field] }));
        setMoveError('这张卡片已进入稳定态，直接修订需走对话确认。请在右侧对话中说明修订意图，由 AI 提案后确认。');
      } else {
        setCanvasSections((current) => updateCanvasCard(current, cardId, { [field]: targetCard[field] }));
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
    autoFitCanvasRef.current = false;
    const lanesEl = canvasLanesRef.current;
    if (!lanesEl) return;

    const lanesRect = lanesEl.getBoundingClientRect();
    const { x: currentX, y: currentY } = screenPointToCanvas(
      {
        x: event.clientX - lanesRect.left,
        y: event.clientY - lanesRect.top,
      },
      { x: 0, y: 0, scale: transform.scale },
    );

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
    else if (kind === 'planning') backendKind = 'decision';
    // L3 规格：handoff 不是对象类型，planning section 复用 decision 类型承载待决策项。

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
        // L3 规格：stage 字段已下线，不再传给后端；kind 必须是五类合法枚举之一。
        // planning section 用 section_hint 标记归属，后端统一存为 decision 类型。
        const payload = {
          kind: backendKind,
          title,
          summary: desc,
        };
        if (kind === 'planning') {
          payload.metadata = { section_hint: 'planning' };
        }
        const res = await apiPost(`/api/canvas/workspaces/${workspaceId}/cards`, payload);
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
  const allArrows = collectCanvasArrows(canvasSections, connectionPortMapRef.current);
  // 稳定关系是画布结构的一部分，默认就应可见；选中/悬停只负责高亮，
  // 连接线工具负责进入编辑态，不再把已有关系整体隐藏。
  const shouldRevealArrows = allArrows.length > 0;
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

  const getDefaultPinnedWidgetPosition = (type, collapsedWidth) => {
    const bounds = getScreenBounds();

    if (type === 'timeline') {
      return {
        x: SCREEN_WIDGET_PADDING,
        y: bounds.height - SCREEN_WIDGET_PADDING - COLLAPSED_WIDGET_HEIGHT,
      };
    }

    // Agent 入口收起时是右上角的 Canvas AI 胶囊；助手展开时则以助手面板左边作为邻接边。
    const isCompact = window.matchMedia('(max-width: 900px)').matches;
    const adjacentEntryLeft = isChatOpen
      ? (isCompact ? SCREEN_WIDGET_PADDING - 4 : bounds.width - 16 - 420)
      : bounds.width - 24 - AGENT_ENTRY_WIDTH;

    return {
      x: adjacentEntryLeft - WIDGET_ENTRY_GAP - collapsedWidth,
      y: 24,
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
      onDelete: () => removePersonalWidget(widget.id),
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

  const renderCard = (card, sectionKey) => {
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
          sectionKey={sectionKey}
          isUiKitFocusCard={workspaceId === 'demo' && sectionKey === 'problems' && canvasSections[sectionKey]?.[0]?.id === card.id}
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

  const timelinePinnedAnchor = timelinePinnedPos || getDefaultPinnedWidgetPosition('timeline', getSystemWidgetCollapsedWidth('timeline'));
  const timelinePinnedLayout = resolveScreenWidgetLayout({
    anchorX: timelinePinnedAnchor.x,
    anchorY: timelinePinnedAnchor.y,
    collapsedWidth: getSystemWidgetCollapsedWidth('timeline'),
    expandedWidth: 720,
    expandedHeight: 160,
  });

  const backlogPinnedAnchor = backlogPinnedPos || getDefaultPinnedWidgetPosition('backlog', getSystemWidgetCollapsedWidth('backlog'));
  const backlogPinnedLayout = resolveScreenWidgetLayout({
    anchorX: backlogPinnedAnchor.x,
    anchorY: backlogPinnedAnchor.y,
    collapsedWidth: getSystemWidgetCollapsedWidth('backlog'),
    expandedWidth: 320,
    expandedHeight: 520,
  });
  const hasCanvasCards = Object.values(canvasSections).some((section) => section.length > 0);

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
                        {widgetItem.type === 'stickyNote' ? '添加' : isEnabled ? '停用' : '启用'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>



      {isHydrating && workspaceId !== 'demo' && (
        <div className="canvas-loading-state" role="status">
          <div className="canvas-empty-state-mark"><Layers size={18} /></div>
          <div>
            <strong>正在恢复工作区</strong>
            <span>正在读取已保存的问题、对话和交接状态…</span>
          </div>
        </div>
      )}

      {!isHydrating && !hasCanvasCards && workspaceId !== 'demo' && (
        <div className="canvas-empty-state" role="status">
          <div className="canvas-empty-state-mark"><Layers size={18} /></div>
          <div>
            <strong>工作面还是空的</strong>
            <span>在右侧助手输入材料后，真实收敛结果会出现在这里。</span>
          </div>
        </div>
      )}

      {/* 无限缩放平面 */}
      {(hasCanvasCards || workspaceId === 'demo') && (
        <div
          className="canvas-lanes"
          ref={canvasLanesRef}
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
                    {(canvasSections[sectionKey] || []).map((card) => renderCard(card, sectionKey))}
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
                geometry={cardGeometry}
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
              geometry={cardGeometry}
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
