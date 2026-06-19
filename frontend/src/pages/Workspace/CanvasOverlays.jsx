import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Archive,
  ChevronDown,
  ChevronUp,
  ChevronsRight,
  Clock3,
  HelpCircle,
  ListTodo,
  Paperclip,
  Pause,
  Pin,
  Play,
  RotateCcw,
  Scale,
  Sparkles,
  StickyNote,
  Timer,
} from 'lucide-react';

const SECTION_LABEL_MAP = {
  evidence: '输入编译',
  problems: '问题定义',
  clarify: '待澄清',
  rules: '约束与决策',
  options: '方案与决策',
  planning: '交接准备',
};

const PRIORITY_ORDER = { 高: 0, 中: 1, 低: 2 };
const COLLAPSED_WIDGET_HEIGHT = 36;
const COLLAPSED_WIDGET_SHADOW = '0 4px 12px rgba(0, 0, 0, 0.06)';
const WIDGET_EASE = 'cubic-bezier(0.2, 0, 0, 1)';
const WIDGET_ROOT_TRANSITION = `left 0.26s ${WIDGET_EASE}, top 0.26s ${WIDGET_EASE}, width 0.26s ${WIDGET_EASE}, height 0.26s ${WIDGET_EASE}`;
const WIDGET_COLLAPSED_TRANSITION = `opacity 0.14s ease-out, transform 0.22s ${WIDGET_EASE}`;
const WIDGET_EXPANDED_TRANSITION = `opacity 0.2s ease-out, transform 0.26s ${WIDGET_EASE}`;

const getCollapsedWidgetWidthByTitle = (title = '') => {
  const textWidth = Array.from(title).reduce((width, char) => {
    if (/[\u4e00-\u9fff]/.test(char)) return width + 12.5;
    if (/\s/.test(char)) return width + 4;
    return width + 7;
  }, 0);

  return Math.ceil(Math.max(96, textWidth + 78));
};

function flattenCanvasCards(canvasSections = {}) {
  return Object.entries(canvasSections).flatMap(([sectionKey, cards]) =>
    (cards || []).map((card) => ({ ...card, sectionKey })),
  );
}

function collectCardText(card) {
  const structuredText = Array.isArray(card.structuredItems)
    ? card.structuredItems
        .map((item) => (typeof item === 'string' ? item : item?.text || ''))
        .join(' ')
    : '';

  return [card.title, card.desc, card.status, card.statusPill?.label, structuredText]
    .filter(Boolean)
    .join(' ');
}

function isCardResolved(card) {
  const label = `${card.status || ''} ${card.statusPill?.label || ''}`.trim();
  return /(已确认|已审批|已完成|完成|关闭|closed|done|resolved)/i.test(label);
}

function inferGapType(card) {
  if (card.sectionKey === 'clarify') return '待澄清';

  const text = collectCardText(card);
  if (/(拍板|待决策|待审批|审批中|决策)/.test(text)) return '待决策';
  return '待定义';
}

function inferGapPriority(card) {
  const text = collectCardText(card);
  if (/(阻塞|必须|拍板|高风险|T\+0|兜底|升级)/.test(text)) return '高';
  if (/(待确认|待审批|待澄清|风险|需要)/.test(text)) return '中';
  return '低';
}

function buildActiveGapItems(canvasSections = {}) {
  const projected = flattenCanvasCards(canvasSections)
    .filter((card) => {
      if (isCardResolved(card)) return false;
      if (card.sectionKey === 'clarify') return true;
      if (card.sectionKey === 'rules' || card.sectionKey === 'options') {
        const text = collectCardText(card);
        return /(待审批|待确认|待定义|待决策|审批中|规则|口径|约束)/.test(text);
      }
      return false;
    })
    .map((card) => {
      const priority = inferGapPriority(card);
      const type = inferGapType(card);
      const text = collectCardText(card);
      return {
        ...card,
        gapType: type,
        priority,
        sourceLabel: SECTION_LABEL_MAP[card.sectionKey] || card.sectionKey,
        isBlocked: /(阻塞|必须|兜底|升级)/.test(text),
      };
    });

  const deduped = new Map();
  projected.forEach((item) => {
    if (!deduped.has(item.id)) {
      deduped.set(item.id, item);
    }
  });

  return Array.from(deduped.values()).sort((a, b) => {
    const priorityDelta = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
    if (priorityDelta !== 0) return priorityDelta;
    if (a.gapType !== b.gapType) return a.gapType.localeCompare(b.gapType, 'zh-CN');
    return a.title.localeCompare(b.title, 'zh-CN');
  });
}

function buildTimelineProjection(canvasSections = {}) {
  const activeGaps = buildActiveGapItems(canvasSections);
  const flatCards = flattenCanvasCards(canvasSections);
  const evidenceCount = flatCards.filter((card) => card.sectionKey === 'evidence').length;
  const clarifyCount = activeGaps.filter((item) => item.gapType === '待澄清').length;
  const decisionCount = activeGaps.filter((item) => item.gapType === '待决策').length;
  const defineCount = activeGaps.filter((item) => item.gapType === '待定义').length;
  const planningCount = flatCards.filter((card) => card.sectionKey === 'planning').length;
  const confirmedRules = flatCards.filter(
    (card) => card.sectionKey === 'rules' && /(已确认|已审批|已完成)/.test(card.statusPill?.label || ''),
  ).length;

  let currentStageIndex = 0;
  if (clarifyCount > 0) currentStageIndex = 1;
  if (decisionCount > 0 || defineCount > 0 || confirmedRules > 0) currentStageIndex = 2;
  if (planningCount > 0 && activeGaps.length <= 1) currentStageIndex = 3;

  const stages = [
    {
      key: 'intake',
      label: '输入编译',
      caption: evidenceCount ? `${evidenceCount} 张输入证据已汇入` : '先把多源输入收进同一工作面',
    },
    {
      key: 'clarify',
      label: '待澄清',
      caption: clarifyCount ? `还有 ${clarifyCount} 个问题待问清` : '关键问题已基本问清',
    },
    {
      key: 'define',
      label: '约束与决策',
      caption:
        decisionCount + defineCount > 0
          ? `${decisionCount + defineCount} 个口径 / 决策待收束`
          : `${confirmedRules} 条规则与决策已沉淀`,
    },
    {
      key: 'handoff',
      label: '交接准备',
      caption: planningCount ? `${planningCount} 张执行 / 交接卡已形成` : '还没进入明确交接节奏',
    },
  ];

  return {
    stages,
    activeGaps,
    currentStageIndex,
    progressLeft: [12, 38, 64, 88][currentStageIndex],
    currentStage: stages[currentStageIndex],
    nextStage: stages[Math.min(currentStageIndex + 1, stages.length - 1)],
    blockerTitles: activeGaps.slice(0, 2),
    confirmedRules,
  };
}

function WidgetActionButton({ title, onClick, children, active = false }) {
  return (
    <button
      type="button"
      className={`utility-widget-icon-btn${active ? ' active' : ''}`}
      onClick={onClick}
      title={title}
    >
      {children}
    </button>
  );
}

function CollapsedWidgetPill({
  icon,
  title,
  onExpand,
  onDragStart,
}) {
  return (
    <div
      className="workspace-widget-collapsed-pill"
      style={{ cursor: onDragStart ? 'move' : 'default' }}
      onPointerDown={onDragStart}
      onClick={() => onExpand()}
    >
      <div className="workspace-widget-collapsed-main">
        <span className="workspace-widget-title-icon">{icon}</span>
        <span className="workspace-widget-collapsed-title">{title}</span>
      </div>
      <div className="workspace-widget-actions">
        <WidgetActionButton
          title="展开挂件"
          onClick={(event) => {
            event.stopPropagation();
            onExpand();
          }}
        >
          <ChevronUp size={14} />
        </WidgetActionButton>
      </div>
    </div>
  );
}

function AnimatedWidgetShell({
  isCollapsed,
  collapsedWidth,
  expandedWidth = '100%',
  expandedLayerWidth = expandedWidth,
  expandedHeight,
  collapsedOrigin = 'top left',
  expandedOrigin = collapsedOrigin,
  collapsedContent,
  expandedContent,
  className = '',
  style,
  onPointerDown,
  collapsedStyle,
  expandedStyle,
}) {
  return (
    <div
      className={`workspace-widget-motion-shell ${isCollapsed ? 'collapsed' : 'expanded'}${className ? ` ${className}` : ''}`}
      style={{
        position: 'relative',
        width: isCollapsed ? `${collapsedWidth}px` : expandedWidth,
        height: isCollapsed ? `${COLLAPSED_WIDGET_HEIGHT}px` : expandedHeight,
        overflow: 'visible',
        transition: WIDGET_ROOT_TRANSITION,
        ...style,
      }}
      onPointerDown={onPointerDown}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: `${collapsedWidth}px`,
          height: `${COLLAPSED_WIDGET_HEIGHT}px`,
          background: 'var(--bg-surface)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid var(--border)',
          borderRadius: '999px',
          boxShadow: COLLAPSED_WIDGET_SHADOW,
          boxSizing: 'border-box',
          opacity: isCollapsed ? 1 : 0,
          transform: isCollapsed ? 'translateY(0) scale(1)' : 'translateY(-2px) scale(0.995)',
          transformOrigin: collapsedOrigin,
          pointerEvents: isCollapsed ? 'auto' : 'none',
          transition: WIDGET_COLLAPSED_TRANSITION,
          ...collapsedStyle,
        }}
      >
        {collapsedContent}
      </div>

      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: expandedLayerWidth,
          height: expandedHeight,
          opacity: isCollapsed ? 0 : 1,
          transform: isCollapsed ? 'translateY(3px) scale(0.995)' : 'translateY(0) scale(1)',
          transformOrigin: expandedOrigin,
          pointerEvents: isCollapsed ? 'none' : 'auto',
          transition: WIDGET_EXPANDED_TRANSITION,
          ...expandedStyle,
        }}
      >
        {expandedContent}
      </div>
    </div>
  );
}

function getPersonalWidgetMotionHeight(widget) {
  if (widget.type === 'parkingLot') return 286;
  if (widget.type === 'clock') return 188;
  if (widget.type === 'focusTimer') return 404;
  return 246;
}

function WidgetFrame({
  widget,
  icon,
  title,
  onPinToggle,
  onDragStart,
  onCollapsedChange,
  children,
  footer,
  className = '',
}) {
  const collapsedWidth = getCollapsedWidgetWidthByTitle(title);
  const expandedHeight = getPersonalWidgetMotionHeight(widget);
  const expandedContent = (
    <div
      className={`workspace-widget ${className}${widget.isPinned ? ' pinned' : ' unpinned'}`}
      style={{ height: '100%' }}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <div
        className="workspace-widget-header"
        style={{ cursor: 'move' }}
        onPointerDown={onDragStart}
        onClick={() => onCollapsedChange(true)}
      >
        <div className="workspace-widget-title">
          <span className="workspace-widget-title-icon">{icon}</span>
          <span>{title}</span>
        </div>
        <div className="workspace-widget-actions">
          <WidgetActionButton
            title={widget.isPinned ? '取消固定，移回画布' : '固定到工作台'}
            onClick={(event) => {
              event.stopPropagation();
              onPinToggle();
            }}
            active={widget.isPinned}
          >
            <Pin
              size={13}
              fill={widget.isPinned ? 'currentColor' : 'none'}
              style={!widget.isPinned ? { transform: 'rotate(-45deg)' } : undefined}
            />
          </WidgetActionButton>
          <WidgetActionButton
            title="折叠挂件"
            onClick={(event) => {
              event.stopPropagation();
              onCollapsedChange(true);
            }}
          >
            <ChevronDown size={14} />
          </WidgetActionButton>
        </div>
      </div>

      <div className="workspace-widget-body">{children}</div>
      {footer ? <div className="workspace-widget-footer">{footer}</div> : null}
    </div>
  );

  return (
    <AnimatedWidgetShell
      isCollapsed={widget.isCollapsed}
      collapsedWidth={collapsedWidth}
      expandedHeight={`${expandedHeight}px`}
      collapsedOrigin={widget.isPinned ? 'top left' : 'top left'}
      expandedOrigin={widget.isPinned ? 'top left' : 'top left'}
      onPointerDown={(event) => event.stopPropagation()}
      collapsedContent={
        <CollapsedWidgetPill
          icon={icon}
          title={title}
          onExpand={() => onCollapsedChange(false)}
          onDragStart={onDragStart}
        />
      }
      expandedContent={expandedContent}
    />
  );
}

function formatClock(date, { timeZone, hour12 }) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12,
    timeZone,
  }).format(date);
}

function formatDateLabel(date) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatDuration(totalSeconds) {
  const safeSeconds = Math.max(0, totalSeconds);
  const minutes = String(Math.floor(safeSeconds / 60)).padStart(2, '0');
  const seconds = String(safeSeconds % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

export function TimelineScrubber({
  isPinned = true,
  onPinToggle,
  onDragStart,
  isCollapsed = true,
  onCollapsedChange,
  canvasSections = {},
  onFocusCard,
  style,
}) {
  const collapsed = isCollapsed;
  const timeline = useMemo(() => buildTimelineProjection(canvasSections), [canvasSections]);
  const collapsedWidth = getCollapsedWidgetWidthByTitle('项目时间轴');
  const containerStyle = isPinned
    ? {
        position: 'absolute',
        left: '12px',
        bottom: '12px',
        width: collapsed ? `${collapsedWidth}px` : '720px',
        height: collapsed ? `${COLLAPSED_WIDGET_HEIGHT}px` : '160px',
        zIndex: 95,
        overflow: 'visible',
        ...style,
      }
    : {
        position: 'relative',
        width: '100%',
        height: collapsed ? `${COLLAPSED_WIDGET_HEIGHT}px` : '160px',
        overflow: 'visible',
      };
  const expandedContent = (
    <div
      style={{
        width: '100%',
        height: '100%',
        padding: '14px 20px var(--sp-4) 20px',
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        boxShadow: '0 12px 30px rgba(15, 23, 42, 0.1)',
        boxSizing: 'border-box',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%', width: '100%' }}>
        <div
          className="timeline-header"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            width: '100%',
            cursor: 'move',
          }}
          onPointerDown={onDragStart}
          onClick={() => onCollapsedChange?.(true)}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>项目时间轴</span>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{timeline.currentStage.caption}</span>
          </div>
          <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <WidgetActionButton
              title={isPinned ? '取消固定，移入画布漂移' : '固定在左下角'}
              onClick={(event) => {
                event.stopPropagation();
                onPinToggle();
              }}
              active={isPinned}
            >
              <Pin size={13} fill={isPinned ? 'currentColor' : 'none'} style={!isPinned ? { transform: 'rotate(-45deg)' } : undefined} />
            </WidgetActionButton>
            <WidgetActionButton
              title="收起时间轴"
              onClick={(event) => {
                event.stopPropagation();
                onCollapsedChange?.(true);
              }}
            >
              <ChevronDown size={14} />
            </WidgetActionButton>
          </div>
        </div>

        <div className="timeline-body" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 12 }}>
          <div className="timeline-ticks">
            {timeline.stages.map((stage, index) => (
              <div key={stage.key} className="tick-item" style={{ left: `${12 + index * 24}%` }}>
                <span className="tick-label">{stage.label}</span>
                <div className="tick-line" />
              </div>
            ))}
          </div>

          <div className="timeline-segmented-track" style={{ marginTop: 8 }}>
            {timeline.stages.map((stage, index) => (
              <div
                key={stage.key}
                className={`track-segment ${index <= timeline.currentStageIndex ? 'segment-blue' : 'segment-gray'}`}
                style={{ width: '25%' }}
              >
                <span>{stage.label}</span>
              </div>
            ))}

            <div className="timeline-current-pointer" style={{ left: `${timeline.progressLeft}%` }}>
              <div className="pointer-line" />
              <span className="pointer-label">当前：{timeline.currentStage.label}</span>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 1fr)',
              gap: 14,
              marginTop: 2,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)' }}>下一步焦点</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{timeline.nextStage.caption}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)' }}>当前缺口</span>
              {timeline.blockerTitles.length ? (
                timeline.blockerTitles.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onFocusCard?.(item.id)}
                    style={{
                      border: 'none',
                      background: 'none',
                      padding: 0,
                      textAlign: 'left',
                      fontSize: 12,
                      color: '#2563eb',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                    title={item.title}
                  >
                    {item.title}
                  </button>
                ))
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>当前没有阻塞性缺口</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <AnimatedWidgetShell
      isCollapsed={collapsed}
      collapsedWidth={collapsedWidth}
      expandedWidth={isPinned ? '720px' : '100%'}
      expandedLayerWidth="720px"
      expandedHeight="160px"
      collapsedOrigin={isPinned ? 'bottom left' : 'top left'}
      expandedOrigin={isPinned ? 'bottom left' : 'top left'}
      className={`timeline-scrubber-fixed ${isPinned ? 'pinned' : 'unpinned'}`}
      style={containerStyle}
      onPointerDown={isPinned ? (event) => event.stopPropagation() : undefined}
      collapsedContent={
        <CollapsedWidgetPill
          icon={<Sparkles size={14} />}
          title="项目时间轴"
          onExpand={() => onCollapsedChange?.(false)}
          onDragStart={onDragStart}
        />
      }
      expandedContent={expandedContent}
    />
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
  onFocusCard,
  uploadedMaterials = [],
  style,
}) {
  const activeItems = useMemo(() => buildActiveGapItems(canvasSections), [canvasSections]);
  const activeClarifications = activeItems.filter((item) => item.gapType === '待澄清');
  const activeDecisions = activeItems.filter((item) => item.gapType === '待决策');
  const activeDefinitions = activeItems.filter((item) => item.gapType === '待定义');
  const activeCount = activeItems.length;
  const expandedWidth = '320px';
  const expandedHeight = '520px';
  const collapsedWidth = getCollapsedWidgetWidthByTitle('活跃缺口');

  const renderPanelBody = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, height: '100%' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #f1f5f9',
          paddingBottom: 10,
          cursor: 'move',
        }}
        onPointerDown={onDragStart}
        onClick={() => onCollapsedChange?.(true)}
      >
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
          <ListTodo size={16} color="var(--text-secondary)" /> 活跃缺口
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            className="canvas-badge"
            style={{
              fontSize: 10,
              padding: '2px 6px',
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              borderRadius: '4px',
              fontWeight: '600',
            }}
          >
            {activeCount} 活跃
          </span>
          <WidgetActionButton
            title={isPinned ? '取消固定，移入画布漂移' : '固定在右上角'}
            onClick={(event) => {
              event.stopPropagation();
              onPinToggle();
            }}
            active={isPinned}
          >
            <Pin size={13} fill={isPinned ? 'currentColor' : 'none'} style={!isPinned ? { transform: 'rotate(-45deg)' } : undefined} />
          </WidgetActionButton>
          <WidgetActionButton
            title="收起看板"
            onClick={(event) => {
              event.stopPropagation();
              onCollapsedChange?.(true);
            }}
          >
            <ChevronDown size={14} />
          </WidgetActionButton>
        </div>
      </div>

      <div
        data-canvas-wheel-region="true"
        onWheel={(event) => event.stopPropagation()}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overscrollBehavior: 'contain',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          paddingRight: 4,
        }}
      >
        <div style={{ textAlign: 'left' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
            待澄清问题
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {activeClarifications.map((item) => (
              <BacklogCard key={item.id} icon={<HelpCircle size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />} item={item} selectedCardId={selectedCardId} setSelectedCardId={setSelectedCardId} onFocusCard={onFocusCard} />
            ))}
            {activeClarifications.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>当前没有活跃缺口</div>
            ) : null}
          </div>
        </div>

        <div style={{ textAlign: 'left' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
            待决策事项
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {activeDecisions.map((item) => (
              <BacklogCard key={item.id} icon={<Scale size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />} item={item} selectedCardId={selectedCardId} setSelectedCardId={setSelectedCardId} onFocusCard={onFocusCard} />
            ))}
            {activeDecisions.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无活跃决策</div>
            ) : null}
          </div>
        </div>

        <div style={{ textAlign: 'left' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8, letterSpacing: '0.05em' }}>
            待定义事项
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {activeDefinitions.map((item) => (
              <BacklogCard key={item.id} icon={<AlertTriangle size={14} style={{ color: 'var(--text-secondary)', marginTop: 1, flexShrink: 0 }} />} item={item} selectedCardId={selectedCardId} setSelectedCardId={setSelectedCardId} onFocusCard={onFocusCard} />
            ))}
            {activeDefinitions.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', paddingLeft: 4, textAlign: 'left' }}>无待定义事项</div>
            ) : null}
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
      </div>
    </div>
  );

  if (isPinned) {
    return (
      <AnimatedWidgetShell
        isCollapsed={isCollapsed}
        collapsedWidth={collapsedWidth}
        expandedWidth={expandedWidth}
        expandedLayerWidth={expandedWidth}
        expandedHeight={expandedHeight}
        collapsedOrigin="top right"
        expandedOrigin="top right"
        className="active-backlog-sidepanel pinned"
        style={{
          position: 'absolute',
          top: '24px',
          right: isChatOpen ? '452px' : '156px',
          width: `${collapsedWidth}px`,
          height: `${COLLAPSED_WIDGET_HEIGHT}px`,
          zIndex: 90,
          overflow: 'visible',
          ...style,
        }}
        onPointerDown={(event) => event.stopPropagation()}
        collapsedStyle={{ left: 'auto', right: 0 }}
        expandedStyle={{ left: 'auto', right: 0 }}
        collapsedContent={
          <CollapsedWidgetPill
            icon={<ListTodo size={14} />}
            title="活跃缺口"
            onExpand={() => onCollapsedChange?.(false)}
            onDragStart={onDragStart}
          />
        }
        expandedContent={
          <div
            data-canvas-wheel-region="true"
            onWheel={(event) => event.stopPropagation()}
            style={{
              width: expandedWidth,
              height: expandedHeight,
              maxHeight: 'calc(100vh - 64px)',
              padding: '16px',
              border: '1px solid var(--border)',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.96)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              boxShadow: '0 12px 30px rgba(15, 23, 42, 0.1)',
              boxSizing: 'border-box',
              overflow: 'hidden',
            }}
          >
            {renderPanelBody()}
          </div>
        }
      />
    );
  }

  return (
    <AnimatedWidgetShell
      isCollapsed={isCollapsed}
      collapsedWidth={collapsedWidth}
      expandedWidth={expandedWidth}
      expandedLayerWidth={expandedWidth}
      expandedHeight="450px"
      className="active-backlog-sidepanel unpinned"
      style={{ zIndex: 10, ...style }}
      collapsedContent={
        <CollapsedWidgetPill
          icon={<ListTodo size={14} />}
          title="活跃缺口"
          onExpand={() => onCollapsedChange?.(false)}
          onDragStart={onDragStart}
        />
      }
      expandedContent={
        <div
          data-canvas-wheel-region="true"
          onWheel={(event) => event.stopPropagation()}
          style={{
            width: expandedWidth,
            height: '450px',
            maxHeight: '450px',
            background: 'rgba(255, 255, 255, 0.96)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            border: '1px solid var(--border)',
            borderRadius: '12px',
            padding: '16px',
            boxShadow: '0 12px 30px rgba(15, 23, 42, 0.1)',
            overflow: 'hidden',
            boxSizing: 'border-box',
          }}
        >
          {renderPanelBody()}
        </div>
      }
    />
  );
}

function BacklogCard({ icon, item, selectedCardId, setSelectedCardId, onFocusCard }) {
  return (
    <div
      onClick={() => {
        setSelectedCardId(item.id);
        onFocusCard?.(item.id);
      }}
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.title}</span>
          <span
            style={{
              padding: '1px 6px',
              borderRadius: 999,
              fontSize: 10,
              background: item.priority === '高' ? 'rgba(239, 68, 68, 0.08)' : item.priority === '中' ? 'rgba(245, 158, 11, 0.08)' : 'rgba(148, 163, 184, 0.1)',
              color: item.priority === '高' ? '#dc2626' : item.priority === '中' ? '#b45309' : '#64748b',
            }}
          >
            {item.priority}
          </span>
          <span
            style={{
              padding: '1px 6px',
              borderRadius: 999,
              fontSize: 10,
              background: 'rgba(37, 99, 235, 0.08)',
              color: '#2563eb',
            }}
          >
            {item.gapType}
          </span>
        </div>
        <span style={{ fontSize: 11, lineHeight: 1.45, color: 'var(--text-secondary)' }}>{item.desc}</span>
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
          来自 {item.sourceLabel}
          {item.isBlocked ? ' · 阻塞推进' : ''}
        </span>
      </div>
    </div>
  );
}

export function StickyNoteWidget({ widget, onUpdate, onPinToggle, onDragStart }) {
  const preview = widget.content?.trim() || widget.title?.trim() || '记一句临时想法';

  return (
    <WidgetFrame
      widget={widget}
      icon={<StickyNote size={14} />}
      title={widget.title?.trim() || '便签'}
      preview={preview}
      onPinToggle={onPinToggle}
      onDragStart={onDragStart}
      onCollapsedChange={(nextCollapsed) => onUpdate({ isCollapsed: nextCollapsed })}
      className={`note-tone-${widget.theme || 'sun'}`}
      footer={<span>创建于 {formatDateLabel(new Date(widget.createdAt))}</span>}
    >
      <input
        className="workspace-widget-input"
        value={widget.title || ''}
        onChange={(event) => onUpdate({ title: event.target.value })}
        placeholder="便签标题（可选）"
      />
      <textarea
        className="workspace-widget-textarea note-body"
        value={widget.content || ''}
        onChange={(event) => onUpdate({ content: event.target.value })}
        placeholder="写下一句提醒、判断或灵感..."
        rows={6}
      />
    </WidgetFrame>
  );
}

export function ParkingLotWidget({ widget, onUpdate, onPinToggle, onDragStart }) {
  const [draft, setDraft] = useState('');
  const preview = widget.items?.length ? `${widget.items.length} 条暂缓事项` : '当前无暂缓事项';

  const moveItem = (itemId, direction) => {
    const items = [...(widget.items || [])];
    const currentIndex = items.findIndex((item) => item.id === itemId);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= items.length) return;
    const [targetItem] = items.splice(currentIndex, 1);
    items.splice(targetIndex, 0, targetItem);
    onUpdate({ items });
  };

  const addItem = () => {
    const value = draft.trim();
    if (!value) return;
    onUpdate({
      items: [
        ...(widget.items || []),
        {
          id: `parking-${Date.now()}`,
          text: value,
          state: 'parked',
        },
      ],
    });
    setDraft('');
  };

  return (
    <WidgetFrame
      widget={widget}
      icon={<Archive size={14} />}
      title="停车区"
      preview={preview}
      onPinToggle={onPinToggle}
      onDragStart={onDragStart}
      onCollapsedChange={(nextCollapsed) => onUpdate({ isCollapsed: nextCollapsed })}
      className="parking-widget"
    >
      <div className="workspace-widget-inline-form">
        <input
          className="workspace-widget-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="新增暂缓事项"
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              addItem();
            }
          }}
        />
        <button type="button" className="workspace-widget-cta" onClick={addItem}>
          添加
        </button>
      </div>

      <div className="workspace-widget-list">
        {widget.items?.length ? (
          widget.items.map((item, index) => (
            <div key={item.id} className="workspace-widget-list-item">
              <div className="workspace-widget-list-copy">
                <span>{item.text}</span>
                <span className={`workspace-widget-badge${item.state === 'ready' ? ' ready' : ''}`}>
                  {item.state === 'ready' ? '准备恢复' : '暂放中'}
                </span>
              </div>
              <div className="workspace-widget-list-actions">
                <button type="button" className="workspace-widget-mini-btn" onClick={() => moveItem(item.id, -1)} disabled={index === 0}>
                  上移
                </button>
                <button type="button" className="workspace-widget-mini-btn" onClick={() => moveItem(item.id, 1)} disabled={index === widget.items.length - 1}>
                  下移
                </button>
                <button
                  type="button"
                  className="workspace-widget-mini-btn primary"
                  onClick={() =>
                    onUpdate({
                      items: widget.items.map((entry) =>
                        entry.id === item.id ? { ...entry, state: entry.state === 'ready' ? 'parked' : 'ready' } : entry,
                      ),
                    })
                  }
                >
                  {item.state === 'ready' ? '撤回恢复' : '恢复处理'}
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="workspace-widget-empty">当前无暂缓事项</div>
        )}
      </div>
    </WidgetFrame>
  );
}

export function ClockWidget({ widget, onUpdate, onPinToggle, onDragStart }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const hour12 = !widget.is24Hour;
  const secondaryTime = widget.secondaryTimezone ? formatClock(now, { timeZone: widget.secondaryTimezone, hour12 }) : null;
  const secondaryLabel = useMemo(() => {
    if (!widget.secondaryTimezone) return null;
    if (widget.secondaryTimezone === 'UTC') return 'UTC';
    if (widget.secondaryTimezone === 'America/New_York') return '纽约';
    if (widget.secondaryTimezone === 'Europe/London') return '伦敦';
    return widget.secondaryTimezone;
  }, [widget.secondaryTimezone]);

  return (
    <WidgetFrame
      widget={widget}
      icon={<Clock3 size={14} />}
      title="时钟"
      preview={`${formatClock(now, { timeZone: 'Asia/Shanghai', hour12 })} · ${widget.is24Hour ? '24h' : '12h'}`}
      onPinToggle={onPinToggle}
      onDragStart={onDragStart}
      onCollapsedChange={(nextCollapsed) => onUpdate({ isCollapsed: nextCollapsed })}
      className="clock-widget"
    >
      <div className="workspace-clock-primary">{formatClock(now, { timeZone: 'Asia/Shanghai', hour12 })}</div>
      <div className="workspace-clock-label">北京时间</div>
      {secondaryTime ? (
        <div className="workspace-clock-secondary">
          <span>{secondaryLabel}</span>
          <strong>{secondaryTime}</strong>
        </div>
      ) : null}
      <div className="workspace-widget-inline-form compact">
        <button
          type="button"
          className="workspace-widget-mini-btn primary"
          onClick={() => onUpdate({ is24Hour: !widget.is24Hour })}
        >
          {widget.is24Hour ? '切到 12h' : '切到 24h'}
        </button>
        <select
          className="workspace-widget-select"
          value={widget.secondaryTimezone || 'UTC'}
          onChange={(event) => onUpdate({ secondaryTimezone: event.target.value })}
        >
          <option value="UTC">UTC</option>
          <option value="America/New_York">纽约</option>
          <option value="Europe/London">伦敦</option>
        </select>
      </div>
    </WidgetFrame>
  );
}

export function FocusTimerWidget({ widget, onUpdate, onPinToggle, onDragStart }) {
  const modes = ['收敛', '整理', '交接'];
  const presetMinutes = widget.durationMinutes || 20;
  const preview = '';
  const totalSeconds = Math.max(1, presetMinutes * 60);
  const elapsedRatio = 1 - widget.remainingSeconds / totalSeconds;
  const visualProgress = widget.isCompleted ? 1 : widget.isRunning ? Math.max(0.08, elapsedRatio) : 0.08;

  const applyPreset = (nextMinutes) => {
    onUpdate({
      durationMinutes: nextMinutes,
      remainingSeconds: nextMinutes * 60,
      isRunning: false,
      isCompleted: false,
    });
  };

  const handleStartPause = () => {
    onUpdate({
      isRunning: !widget.isRunning,
      isCompleted: false,
    });
  };

  const handleReset = () => {
    onUpdate({
      remainingSeconds: presetMinutes * 60,
      isRunning: false,
      isCompleted: false,
    });
  };

  const handleAdvance = () => {
    const currentIndex = modes.indexOf(widget.mode || '收敛');
    const nextMode = modes[(currentIndex + 1) % modes.length];
    onUpdate({
      mode: nextMode,
      remainingSeconds: presetMinutes * 60,
      isRunning: false,
      isCompleted: false,
    });
  };

  return (
    <WidgetFrame
      widget={widget}
      icon={<Timer size={14} />}
      title="专注计时器"
      preview={preview}
      onPinToggle={onPinToggle}
      onDragStart={onDragStart}
      onCollapsedChange={(nextCollapsed) => onUpdate({ isCollapsed: nextCollapsed })}
      className="timer-widget"
    >
      <div className="workspace-timer-shell">
        <div className="workspace-timer-dial" style={{ '--timer-progress': visualProgress }}>
          <div className="workspace-timer-dial-track" />
          <div className="workspace-timer-dial-progress" />
          <div className="workspace-timer-dial-head" />
          <div className="workspace-timer-dial-core">
            <div className="workspace-timer-display">{formatDuration(widget.remainingSeconds)}</div>
            <select
              className="workspace-timer-mode-select"
              value={widget.mode || '收敛'}
              onChange={(event) => onUpdate({ mode: event.target.value })}
            >
              <option value="收敛">收敛</option>
              <option value="整理">整理</option>
              <option value="交接">交接</option>
            </select>
          </div>
        </div>

        <div className="workspace-timer-presets" role="group" aria-label="专注时长">
          {[15, 20, 25].map((minutes, index) => (
            <React.Fragment key={minutes}>
              {index > 0 ? <span className="workspace-timer-preset-divider" aria-hidden="true" /> : null}
              <button
                type="button"
                className={`workspace-timer-preset${presetMinutes === minutes ? ' active' : ''}`}
                onClick={() => applyPreset(minutes)}
              >
                {minutes}
              </button>
            </React.Fragment>
          ))}
        </div>

        <div className="workspace-timer-action-row">
          <button type="button" className="workspace-timer-side-action" onClick={handleReset}>
            <span className="workspace-timer-side-icon">
              <RotateCcw size={16} />
            </span>
            <span className="workspace-timer-side-label">重置</span>
          </button>

          <button type="button" className="workspace-timer-primary-action" onClick={handleStartPause}>
            <span className="workspace-timer-primary-circle">
              {widget.isRunning ? <Pause size={28} fill="currentColor" /> : <Play size={28} fill="currentColor" />}
            </span>
            <span className="workspace-timer-primary-label">
              {widget.isRunning ? '暂停' : widget.remainingSeconds === 0 || widget.isCompleted ? '开始下一轮' : '开始'}
            </span>
          </button>

          <button type="button" className="workspace-timer-side-action" onClick={handleAdvance}>
            <span className="workspace-timer-side-icon">
              <ChevronsRight size={16} />
            </span>
            <span className="workspace-timer-side-label">{widget.isCompleted ? '下一轮' : '跳过休息'}</span>
          </button>
        </div>
      </div>
    </WidgetFrame>
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
