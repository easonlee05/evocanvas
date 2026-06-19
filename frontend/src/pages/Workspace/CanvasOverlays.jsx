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
export const COLLAPSED_WIDGET_HEIGHT = 36;
const COLLAPSED_WIDGET_SHADOW = '0 4px 12px rgba(0, 0, 0, 0.06)';
const WIDGET_EASE = 'cubic-bezier(0.2, 0, 0, 1)';
export const WIDGET_ROOT_TRANSITION = `left 0.26s ${WIDGET_EASE}, top 0.26s ${WIDGET_EASE}, width 0.26s ${WIDGET_EASE}, height 0.26s ${WIDGET_EASE}`;
export const WIDGET_COLLAPSED_TRANSITION = `opacity 0.14s ease-out, transform 0.22s ${WIDGET_EASE}`;
export const WIDGET_EXPANDED_TRANSITION = `opacity 0.2s ease-out, transform 0.26s ${WIDGET_EASE}`;

export const getCollapsedWidgetWidthByTitle = (title = '') => {
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

export function buildActiveGapItems(canvasSections = {}) {
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

export function buildTimelineProjection(canvasSections = {}) {
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

export function WidgetActionButton({ title, onClick, children, active = false }) {
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

export function CollapsedWidgetPill({
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

export function AnimatedWidgetShell({
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

export function WidgetFrame({
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

export function formatClock(date, { timeZone, hour12 }) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12,
    timeZone,
  }).format(date);
}

export function formatDateLabel(date) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatDuration(totalSeconds) {
  const safeSeconds = Math.max(0, totalSeconds);
  const minutes = String(Math.floor(safeSeconds / 60)).padStart(2, '0');
  const seconds = String(safeSeconds % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

export { TimelineScrubber } from './components/TimelineScrubber';
export { ActiveBacklogPanel } from './components/ActiveBacklogPanel';
export { StickyNoteWidget } from './components/StickyNoteWidget';
export { ParkingLotWidget } from './components/ParkingLotWidget';
export { ClockWidget } from './components/ClockWidget';
export { FocusTimerWidget } from './components/FocusTimerWidget';
export { CardCreatorBubble } from './components/CardCreatorBubble';
