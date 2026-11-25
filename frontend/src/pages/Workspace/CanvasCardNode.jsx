/**
 * @file CanvasCardNode.jsx
 * @description EvoCanvas 主画布卡片节点渲染与画布常量配置模块（从 Canvas.jsx 拆分，保持行为不变）。
 */

import { useLayoutEffect, useRef } from 'react';
import rough from 'roughjs/bin/rough';
import {
  Archive,
  Clock3,
  ListTodo,
  MessageCircle,
  MoreHorizontal,
  Paperclip,
  Sparkles,
  StickyNote,
  Timer,
} from 'lucide-react';
import { DEMO_PERSONA_AVATARS } from './demoScenario.js';
import { getCanvasStatusLabel } from './canvasProjection.js';

export const LANE_DEFINITIONS = [
  { sectionKey: 'clarify', laneTitle: '待澄清项', clusterTitle: '问题与不确定性' },
  { sectionKey: 'rules', laneTitle: '规则约束', clusterTitle: '核心业务规则' },
  { sectionKey: 'options', laneTitle: '方案与决策', clusterTitle: '备选方案与拍板' },
  { sectionKey: 'evidence', laneTitle: '探索发现', clusterTitle: '原始证据池' },
  { sectionKey: 'problems', laneTitle: '焦点问题', clusterTitle: '问题定义' },
  { sectionKey: 'planning', laneTitle: '落地交接', clusterTitle: '结构化交接物' },
];

export const CONNECT_SNAP_RADIUS = 64;
export const EXPLICIT_PORT_SNAP_RADIUS = 20;

const CARD_TYPE_META = {
  evidence: { label: '证据', iconSrc: '/card-type-icons/handdrawn/evidence.png', tone: 'evidence' },
  problem: { label: '问题', iconSrc: '/card-type-icons/handdrawn/problem.png', tone: 'problem' },
  clarification: { label: '待澄清', iconSrc: '/card-type-icons/handdrawn/clarify.png', tone: 'clarify' },
  constraint: { label: '约束', iconSrc: '/card-type-icons/handdrawn/rules.png', tone: 'rules' },
  decision: { label: '决策', iconSrc: '/card-type-icons/handdrawn/decision.png', tone: 'decision' },
  'decision-or-option': { label: '决策', iconSrc: '/card-type-icons/handdrawn/decision.png', tone: 'decision' },
  option: { label: '方案', iconSrc: '/card-type-icons/handdrawn/decision.png', tone: 'decision' },
  handoff: { label: '交接', iconSrc: '/card-type-icons/handdrawn/handoff.png', tone: 'handoff' },
};

const SECTION_KIND_MAP = {
  evidence: 'evidence',
  problems: 'problem',
  clarify: 'clarification',
  rules: 'constraint',
  options: 'decision',
  planning: 'handoff',
};

function autoResizeTextarea(element) {
  if (!element) return;
  element.style.height = 'auto';
  element.style.height = `${element.scrollHeight}px`;
}

function getCardTypeMeta(card, sectionKey) {
  const kind = card.kind || SECTION_KIND_MAP[sectionKey] || 'evidence';
  return CARD_TYPE_META[kind] || CARD_TYPE_META.evidence;
}

function CardTypeIconImage({ src, label, className = '' }) {
  return <img className={`card-type-icon-image${className ? ` ${className}` : ''}`} src={src} alt={`${label}图标`} />;
}

function getStatusColor(status = '') {
  if (['clarified', 'effective', 'decided', 'converged', 'closed'].includes(status)) return 'green';
  if (/已确认|已审批|已完成|done|confirmed|approved/.test(status)) return 'green';
  if (/待|需要|审批中|open|pending/.test(status)) return 'yellow';
  if (/风险|阻塞|异常|blocked|risk/.test(status)) return 'red';
  return 'gray';
}

function getStatusLabel(status = '') {
  return getCanvasStatusLabel(status);
}

function getUiKitStatusTone(sectionKey, statusLabel = '', statusColor = 'gray') {
  if (sectionKey === 'clarify') {
    if (/待决策|待审批|风险|阻塞/.test(statusLabel)) return 'yellow';
    return 'blue';
  }

  if (sectionKey === 'rules') {
    if (statusColor === 'green') return 'green';
    if (statusColor === 'yellow') return 'yellow';
    if (statusColor === 'red') return 'red';
    return 'green';
  }

  if (sectionKey === 'options') {
    if (statusColor === 'blue') return 'blue';
    if (statusColor === 'green') return 'green';
    if (statusColor === 'red') return 'red';
    return 'yellow';
  }

  if (sectionKey === 'planning') {
    if (statusColor === 'blue') return 'blue';
    if (statusColor === 'green') return 'green';
    if (statusColor === 'yellow') return 'yellow';
    if (statusColor === 'red') return 'red';
    if (statusColor === 'gray') return 'purple';
    return 'purple';
  }

  if (statusColor === 'green') return 'green';
  if (statusColor === 'yellow') return 'yellow';
  if (statusColor === 'blue') return 'blue';
  if (statusColor === 'red') return 'red';
  return 'gray';
}
export const NOTE_THEMES = ['sun', 'mint', 'sky', 'rose'];
export const COLLAPSED_WIDGET_HEIGHT = 36;
export const SCREEN_WIDGET_PADDING = 16;
export const AGENT_ENTRY_WIDTH = 112;
export const WIDGET_ENTRY_GAP = 12;
export const WIDGET_LAYOUT_TRANSITION = 'left 0.26s cubic-bezier(0.2, 0, 0, 1), top 0.26s cubic-bezier(0.2, 0, 0, 1), width 0.26s cubic-bezier(0.2, 0, 0, 1), height 0.26s cubic-bezier(0.2, 0, 0, 1)';

export const createEmptyCanvasSections = () => ({
  evidence: [],
  problems: [],
  clarify: [],
  rules: [],
  options: [],
  planning: [],
});

export const getCollapsedWidgetWidthByTitle = (title = '') => {
  const textWidth = Array.from(title).reduce((width, char) => {
    if (/[\u4e00-\u9fff]/.test(char)) return width + 12.5;
    if (/\s/.test(char)) return width + 4;
    return width + 7;
  }, 0);

  // 左右 padding + 图标 + 两处间距 + 展开箭头，保留与 Canvas AI 相近的紧凑胶囊。
  return Math.ceil(Math.max(96, textWidth + 78));
};

export const getSystemWidgetCollapsedWidth = (type) =>
  getCollapsedWidgetWidthByTitle(type === 'backlog' ? '活跃缺口' : '项目时间轴');

export const WIDGET_LIBRARY = [
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
  const hasAvatarImage = Boolean(meta.avatarSrc);
  return (
    <div className="card-persona-row">
      <span className="owner-label">{meta.label || '负责人'}</span>
      <div className={`card-avatar ${hasAvatarImage ? 'card-avatar-image-only' : `card-avatar-${meta.avatarTone || 'slate'}`}`}>
        {meta.avatarSrc ? <img className="card-avatar-image" src={meta.avatarSrc} alt="" /> : meta.avatar}
      </div>
      <span className="owner-name">{meta.name}</span>
    </div>
  );
}

function StructuredContent({ kind = 'list', items = [] }) {
  if (!items?.length) return null;

  const textForItem = (item) => {
    if (item && typeof item === 'object') return String(item.text || '');
    return String(item ?? '');
  };

  if (kind === 'quote') {
    return (
      <div className="structured-block structured-quote">
        <div className="structured-quote-item">
          {items.map((item) => (
            <div key={textForItem(item)} className="structured-list-item">
              <span className="fact-dot" />
              <span className="structured-quote-text">{textForItem(item)}</span>
            </div>
          ))}
        </div>
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
          <div key={textForItem(item)} className="structured-list-item">
            <span className="fact-dot" />
            <span className="structured-list-text">{textForItem(item)}</span>
        </div>
      ))}
    </div>
  );
}

function serializeStructuredItemsForEditor(items, { isCheckpointCard = false } = {}) {
  if (!Array.isArray(items)) return '';

  if (!isCheckpointCard) {
    return items.join('\n');
  }

  return items.map((item) => {
    if (typeof item === 'string') return item;
    const text = item?.text || '';
    const date = item?.date ? ` | ${item.date}` : '';
    return `${text}${date}`.trim();
  }).join('\n');
}

function parseStructuredItemsFromEditor(rawValue, existingItems, { isCheckpointCard = false } = {}) {
  const lines = String(rawValue)
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);

  if (!isCheckpointCard) {
    return lines;
  }

  return lines.map((line, index) => {
    const [textPart, datePart] = line.split('|').map((part) => part?.trim());
    const previous = typeof existingItems?.[index] === 'object' ? existingItems[index] : {};
    return {
      ...previous,
      text: textPart || previous.text || '',
      state: previous.state || 'pending',
      ...(datePart ? { date: datePart } : previous.date ? { date: previous.date } : {}),
    };
  });
}

export function normalizeEditableValue(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') {
          const text = item.trim();
          return text || null;
        }

        if (item && typeof item === 'object') {
          const text = String(item.text || '').trim();
          if (!text) return null;

          return {
            text,
            ...(item.state ? { state: String(item.state).trim() } : {}),
            ...(item.date ? { date: String(item.date).trim() } : {}),
          };
        }

        const text = String(item ?? '').trim();
        return text || null;
      })
      .filter(Boolean);
  }

  return String(value ?? '').trim();
}

function buildRoundedRectPath(x, y, width, height, radius) {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2));
  return [
    `M ${x + r} ${y}`,
    `L ${x + width - r} ${y}`,
    `Q ${x + width} ${y} ${x + width} ${y + r}`,
    `L ${x + width} ${y + height - r}`,
    `Q ${x + width} ${y + height} ${x + width - r} ${y + height}`,
    `L ${x + r} ${y + height}`,
    `Q ${x} ${y + height} ${x} ${y + height - r}`,
    `L ${x} ${y + r}`,
    `Q ${x} ${y} ${x + r} ${y}`,
    'Z',
  ].join(' ');
}

function SketchCardFrame({ cardRef, contentRef }) {
  const svgRef = useRef(null);

  useLayoutEffect(() => {
    if (!svgRef.current) return undefined;

    let frameId = null;
    let observedCard = null;
    let observedContent = null;

    const scheduleDraw = () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      frameId = requestAnimationFrame(() => {
        frameId = null;
        draw();
      });
    };

    const draw = () => {
      const cardEl = cardRef.current;
      const contentEl = contentRef.current;
      const currentSvgEl = svgRef.current;
      if (!cardEl || !contentEl || !currentSvgEl) return;

      const cardRect = cardEl.getBoundingClientRect();
      const contentRect = contentEl.getBoundingClientRect();
      const cardStyle = window.getComputedStyle(cardEl);
      const width = Math.max(1, Math.round(cardRect.width));
      const height = Math.max(1, Math.round(cardRect.height));
      const innerX = Math.max(0, Math.round(contentRect.left - cardRect.left));
      const innerY = Math.max(0, Math.round(contentRect.top - cardRect.top));
      const innerWidth = Math.max(1, Math.round(contentRect.width));
      const innerHeight = Math.max(1, Math.round(contentRect.height));
      const outerStroke = cardStyle.getPropertyValue('--sketch-card-outer-stroke').trim() || 'rgba(32, 32, 29, 0.82)';
      const outerFill = cardStyle.getPropertyValue('--sketch-card-outer-fill').trim() || 'rgba(255, 255, 253, 0.985)';
      const outerStrokeWidth = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-outer-stroke-width')) || 1.02;
      const outerRoughness = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-outer-roughness')) || 0.85;
      const outerBowing = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-outer-bowing')) || 0.9;
      const offsetStroke = cardStyle.getPropertyValue('--sketch-card-offset-stroke').trim() || 'rgba(32, 32, 29, 0.1)';
      const offsetStrokeWidth = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-offset-stroke-width')) || 0.56;
      const offsetRoughness = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-offset-roughness')) || 1.05;
      const offsetBowing = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-offset-bowing')) || 1.1;
      const innerStroke = cardStyle.getPropertyValue('--sketch-card-inner-stroke').trim() || 'rgba(32, 32, 29, 0.18)';
      const innerFill = cardStyle.getPropertyValue('--sketch-card-inner-fill').trim() || 'rgba(255, 254, 250, 0.28)';
      const innerStrokeWidth = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-inner-stroke-width')) || 0.82;
      const innerRoughness = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-inner-roughness')) || 0.7;
      const innerBowing = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-inner-bowing')) || 0.75;
      const outerRadius = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-outer-radius')) || 10;
      const offsetRadius = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-offset-radius')) || 9;
      const innerRadius = Number.parseFloat(cardStyle.getPropertyValue('--sketch-card-inner-radius')) || 8;

      currentSvgEl.setAttribute('viewBox', `0 0 ${width} ${height}`);
      currentSvgEl.setAttribute('width', String(width));
      currentSvgEl.setAttribute('height', String(height));
      currentSvgEl.replaceChildren();

      const rc = rough.svg(currentSvgEl);

      const outer = rc.path(buildRoundedRectPath(3, 3, width - 6, height - 6, outerRadius), {
        seed: 14,
        stroke: outerStroke,
        strokeWidth: outerStrokeWidth,
        fill: outerFill,
        fillStyle: 'solid',
        roughness: outerRoughness,
        bowing: outerBowing,
        preserveVertices: true,
        disableMultiStrokeFill: true,
      });
      outer.classList.add('kit-rough-outer');
      currentSvgEl.appendChild(outer);

      const offsetOutline = rc.path(buildRoundedRectPath(4, 4, width - 8, height - 8, offsetRadius), {
        seed: 21,
        stroke: offsetStroke,
        strokeWidth: offsetStrokeWidth,
        roughness: offsetRoughness,
        bowing: offsetBowing,
        preserveVertices: true,
      });
      offsetOutline.classList.add('kit-rough-offset');
      currentSvgEl.appendChild(offsetOutline);

      const inner = rc.path(buildRoundedRectPath(innerX, innerY, innerWidth, innerHeight, innerRadius), {
        seed: 31,
        stroke: innerStroke,
        strokeWidth: innerStrokeWidth,
        fill: innerFill,
        fillStyle: 'solid',
        roughness: innerRoughness,
        bowing: innerBowing,
        preserveVertices: true,
        disableMultiStrokeFill: true,
      });
      inner.classList.add('kit-rough-inner');
      currentSvgEl.appendChild(inner);
    };

    const resizeObserver = new ResizeObserver(() => {
      syncObservedNodes();
      scheduleDraw();
    });

    const mutationObserver = new MutationObserver(() => {
      syncObservedNodes();
      scheduleDraw();
    });

    const syncObservedNodes = () => {
      const nextCard = cardRef.current;
      const nextContent = contentRef.current;

      if (nextCard && nextCard !== observedCard) {
        if (observedCard) resizeObserver.unobserve(observedCard);
        observedCard = nextCard;
        resizeObserver.observe(observedCard);
        mutationObserver.disconnect();
        mutationObserver.observe(observedCard, {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
        });
      }

      if (nextContent && nextContent !== observedContent) {
        if (observedContent) resizeObserver.unobserve(observedContent);
        observedContent = nextContent;
        resizeObserver.observe(observedContent);
      }
    };

    syncObservedNodes();
    scheduleDraw();

    return () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      mutationObserver.disconnect();
    };
  }, [cardRef, contentRef]);

  return <svg ref={svgRef} className="kit-rough-frame" aria-hidden="true" />;
}

export function CanvasCard({
  data,
  sectionKey,
  isUiKitFocusCard = false,
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
  const typeMeta = getCardTypeMeta(data, sectionKey);
  const statusLabel = data.statusPill?.label || getStatusLabel(data.status);
  const statusColor = data.statusPill?.color || getStatusColor(data.status);
  const tags = data.tags || [];
  const hasTags = tags.length > 0;

  const isEditingTitle = editingState?.cardId === data.id && editingState?.field === 'title';
  const isEditingDesc = editingState?.cardId === data.id && editingState?.field === 'desc';
  const uiKitCardRef = useRef(null);
  const uiKitContentRef = useRef(null);

  const cardClassName = `canvas-card${isSelectedSelf ? ' selected-self' : ''}${isSelectedRelated && !isSelectedSelf ? ' selected-related' : ''}${isPreviewSelf ? ' preview-self' : ''}${isPreviewRelated && !isPreviewSelf && !isSelectedRelated ? ' preview-related' : ''}${isDimmed ? ' is-dimmed' : ''}${isConnectorSource ? ' connector-source' : ''}${isConnectorTarget ? ' connector-target' : ''}`;
  const contentCardClassName = `${cardClassName}${sectionKey === 'evidence' ? ' evidence-card' : ''}`;
  const interactiveProps = {
    id: data.id,
    onClick: () => {
      // 防止在编辑态下误触发 select
      if (editingState?.cardId === data.id) return;
      onSelect(data.id);
    },
    onMouseEnter: () => onPreviewStart(data.id),
    onMouseLeave: onPreviewEnd,
    style: relationAccent ? { '--relation-accent': relationAccent } : undefined,
    onPointerDown,
  };
  const showConnectorPorts = activeTool === 'connector' && onConnectStart;

  if (sectionKey === 'problems') {
    const isEditingTitle = editingState?.cardId === data.id && editingState?.field === 'title';
    const isEditingSummary = editingState?.cardId === data.id && editingState?.field === 'desc';
    const isEditingItems = editingState?.cardId === data.id && editingState?.field === 'structuredItems';
    const isPrimaryProblemCard = isUiKitFocusCard;
    const problemItems = Array.isArray(data.structuredItems) && data.structuredItems.length
      ? data.structuredItems
      : data.isProjection ? [] : ['目标用户是谁？（新手？PM？团队管理员？）', '是否需要手动动作？', '成功的衡量标准？'];
    const previewCard = {
      title: '问题',
      cardTitle: data.title || '618 积分发放链路治理（v1.0）',
      status: isPrimaryProblemCard ? '待解决' : (statusLabel || '待推进'),
      statusTone: isPrimaryProblemCard ? 'problem' : getUiKitStatusTone(sectionKey, statusLabel, statusColor),
      summary: data.desc || '我们要解决的核心问题是什么？明确需要解决的关键点，避免发散讨论。',
      items: problemItems,
      attachCount: isPrimaryProblemCard ? 1 : (data.attachments?.length || 0),
      discussCount: isPrimaryProblemCard ? 3 : problemItems.length,
      ownerName: isPrimaryProblemCard ? '小雨' : (data.owner?.name || '待确认'),
      avatarSrc: isPrimaryProblemCard ? DEMO_PERSONA_AVATARS.xiaoYu : (data.owner?.avatarSrc || DEMO_PERSONA_AVATARS.xiaoYu),
      progressText: isPrimaryProblemCard ? '1 / 5' : `1 / ${Math.max(problemItems.length, 1)}`,
      metaLabel: isPrimaryProblemCard ? '核心问题' : '',
    };

    const isEditingProblemCard = isEditingSummary || isEditingItems;

    return (
      <div
        ref={uiKitCardRef}
        className={`${cardClassName} ui-kit-card ui-kit-card-theme-problem ui-kit-problem-card ui-kit-card-no-footer${isEditingProblemCard ? ' is-editing-problem-card' : ''}`}
        {...interactiveProps}
      >
        <SketchCardFrame cardRef={uiKitCardRef} contentRef={uiKitContentRef} />
        <div className="kit-card-top">
          <div className="kit-card-heading">
            <span className="kit-type-icon kit-type-icon-problem">
              <CardTypeIconImage src={typeMeta.iconSrc} label={typeMeta.label} className="kit-card-type-icon-image" />
            </span>
            <div className="kit-card-title-wrap">
              <span className="kit-card-title">
                <span className="kit-card-title-cn">{previewCard.title}</span>
              </span>
            </div>
          </div>

          <div className="kit-card-actions">
            <div className="kit-status-row kit-status-row-top">
              <span className={`kit-status-pill kit-status-${previewCard.statusTone}`}>{previewCard.status}</span>
            </div>
            <button
              className="icon-btn kit-more-btn"
              onClick={(event) => {
                event.stopPropagation();
                setActiveCardMenuId(activeCardMenuId === data.id ? null : data.id);
              }}
              title="更多操作"
            >
              <MoreHorizontal size={15} />
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

        <div
          className={`kit-card-heading-title${isEditingTitle ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'title', previewCard.cardTitle);
          }}
        >
          {isEditingTitle ? (
            <textarea
              className="kit-card-title-input"
              autoFocus
              defaultValue={previewCard.cardTitle}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) => onSaveEdit(data.id, 'title', event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'title', previewCard.cardTitle);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'title', event.target.value);
                }
              }}
            />
          ) : (
            <span>{previewCard.cardTitle}</span>
          )}
        </div>

        <div
          className={`kit-card-summary${isEditingSummary ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'desc', previewCard.summary);
          }}
        >
          {isEditingSummary ? (
            <textarea
              className="kit-card-desc-input"
              autoFocus
              defaultValue={previewCard.summary}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) => onSaveEdit(data.id, 'desc', event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', previewCard.summary);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', event.target.value);
                }
              }}
            />
          ) : (
            <span>{previewCard.summary}</span>
          )}
        </div>

        <div
          ref={uiKitContentRef}
          className={`kit-card-structured-shell${isEditingItems ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'structuredItems', previewCard.items);
          }}
        >
          {isEditingItems ? (
            <textarea
              className="kit-card-list-input"
              autoFocus
              defaultValue={previewCard.items.join('\n')}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) =>
                onSaveEdit(
                  data.id,
                  'structuredItems',
                  event.target.value.split('\n').map((item) => item.trim()).filter(Boolean),
                )
              }
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'structuredItems', previewCard.items);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(
                    data.id,
                    'structuredItems',
                    event.currentTarget.value.split('\n').map((item) => item.trim()).filter(Boolean),
                  );
                }
              }}
            />
          ) : (
            <StructuredContent kind="list" items={previewCard.items} />
          )}
        </div>

        <div className="kit-card-meta-row">
          <div className="kit-counts">
            <span className="kit-count"><Paperclip size={13} />{previewCard.attachCount}</span>
            <span className="kit-count"><MessageCircle size={13} />{previewCard.discussCount}</span>
          </div>
          {previewCard.metaLabel ? (
            <span className="kit-meta-tag kit-meta-tag-problem">{previewCard.metaLabel}</span>
          ) : <span />}
        </div>

        {showConnectorPorts && (
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
              style={{ left: 0, top: '50%' }}
              onPointerDown={(e) => { e.stopPropagation(); onConnectStart('left', e); }}
              title="向左连线"
              data-port="left"
            />
            <div
              className="connector-hitarea port-right"
              style={{ left: '100%', top: '50%' }}
              onPointerDown={(e) => { e.stopPropagation(); onConnectStart('right', e); }}
              title="向右连线"
              data-port="right"
            />
          </>
        )}
      </div>
    );
  }

  if (sectionKey === 'clarify' || sectionKey === 'rules' || sectionKey === 'options' || sectionKey === 'planning') {
    const isEditingItems = editingState?.cardId === data.id && editingState?.field === 'structuredItems';
    const cardConfigMap = {
      clarify: {
        themeClass: 'ui-kit-card-theme-clarify ui-kit-clarify-card',
        defaultTitle: '这里记录需要补充澄清的问题',
        defaultStatus: '待澄清',
        defaultSummary: '把还没确认的边界、口径和依赖先显性化，不要在模糊状态下继续定方案。',
        defaultItems: ['需要进一步澄清的边界是什么？', '谁来确认口径，何时给结论？'],
        defaultStructureKind: 'list',
        footerMode: 'none',
      },
      rules: {
        themeClass: 'ui-kit-card-theme-rules ui-kit-rules-card',
        defaultTitle: '记录当前阶段已确认的业务边界',
        defaultStatus: '已确认',
        defaultSummary: '记录当前阶段不可忽略的规则、前提或边界条件，避免方案继续发散。',
        defaultItems: [
          { text: '这里记录已确认的约束、前提和边界。', state: 'done' },
          { text: '这里记录仍需确认的规则或补充条件。', state: 'pending' },
        ],
        defaultStructureKind: 'checkpoints',
        footerMode: 'none',
      },
      options: {
        themeClass: 'ui-kit-card-theme-decision ui-kit-decision-card',
        defaultTitle: '这里记录候选方案与关键取舍',
        defaultStatus: '待拍板',
        defaultSummary: '把候选方案、取舍条件和推荐方向显性化，避免讨论一直停留在口头层面。',
        defaultItems: ['方案 A：先做最小闭环，快速止损', '方案 B：补齐更多能力后再整体上线'],
        defaultStructureKind: 'list',
        footerMode: 'none',
      },
      planning: {
        themeClass: 'ui-kit-card-theme-handoff ui-kit-handoff-card',
        defaultTitle: '这里记录需要交接的执行动作',
        defaultStatus: '进行中',
        defaultSummary: '把要落到研发、设计、客服或运营的动作明确下来，让交接不是一句“去做吧”。',
        defaultItems: [
          { text: '明确执行人、交付物和依赖项', state: 'current' },
          { text: '确认本周推进节奏与验收节点', state: 'pending' },
        ],
        defaultStructureKind: 'checkpoints',
        footerMode: 'none',
      },
    };
    const sectionConfig = cardConfigMap[sectionKey];
    const isCheckpointCard = sectionConfig.defaultStructureKind === 'checkpoints';
    const rawItems = Array.isArray(data.structuredItems) && data.structuredItems.length
      ? data.structuredItems
      : data.isProjection ? [] : sectionConfig.defaultItems;
    const completedCount = rawItems.filter((item) => typeof item === 'object' && ['done', 'current'].includes(item?.state)).length;
    const footerText = sectionConfig.footerMode === 'progress'
      ? `${completedCount} / ${rawItems.length}`
      : sectionConfig.footerMode === 'count'
        ? `${rawItems.length} 项`
        : '';
    const previewCard = {
      typeTitle: typeMeta.label,
      cardTitle: data.title || sectionConfig.defaultTitle,
      status: statusLabel || sectionConfig.defaultStatus,
      summary: data.desc || sectionConfig.defaultSummary,
      items: rawItems,
      attachCount: data.attachments?.length || 0,
      discussCount: Array.isArray(rawItems) ? rawItems.length : 0,
      ownerName: data.owner?.name || '待确认',
      avatarSrc: data.owner?.avatarSrc || null,
      footerText,
      structureKind: data.structureKind || sectionConfig.defaultStructureKind,
      statusTone: getUiKitStatusTone(sectionKey, statusLabel, statusColor),
    };

    return (
      <div
        ref={uiKitCardRef}
        className={`${cardClassName} ui-kit-card ${sectionConfig.themeClass}${sectionConfig.footerMode === 'none' ? ' ui-kit-card-no-footer' : ''}`}
        {...interactiveProps}
      >
        <SketchCardFrame cardRef={uiKitCardRef} contentRef={uiKitContentRef} />
        <div className="kit-card-top">
          <div className="kit-card-heading">
            <span className={`kit-type-icon ${
              sectionKey === 'rules'
                ? 'kit-type-icon-rules'
                : sectionKey === 'clarify'
                  ? 'kit-type-icon-clarify'
                  : sectionKey === 'planning'
                    ? 'kit-type-icon-handoff'
                    : 'kit-type-icon-decision'
            }`}>
              <CardTypeIconImage src={typeMeta.iconSrc} label={typeMeta.label} className="kit-card-type-icon-image" />
            </span>
            <div className="kit-card-title-wrap">
              <span className="kit-card-title">
                <span className="kit-card-title-cn">{previewCard.typeTitle}</span>
              </span>
            </div>
          </div>

          <div className="kit-card-actions">
            <div className="kit-status-row kit-status-row-top">
              <span className={`kit-status-pill kit-status-${previewCard.statusTone}`}>{previewCard.status}</span>
            </div>
            <button
              className="icon-btn kit-more-btn"
              onClick={(event) => {
                event.stopPropagation();
                setActiveCardMenuId(activeCardMenuId === data.id ? null : data.id);
              }}
              title="更多操作"
            >
              <MoreHorizontal size={15} />
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

        <div
          className={`kit-card-heading-title${isEditingTitle ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'title', previewCard.cardTitle);
          }}
        >
          {isEditingTitle ? (
            <textarea
              className="kit-card-title-input"
              autoFocus
              defaultValue={previewCard.cardTitle}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) => onSaveEdit(data.id, 'title', event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'title', previewCard.cardTitle);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'title', event.target.value);
                }
              }}
            />
          ) : (
            <span>{previewCard.cardTitle}</span>
          )}
        </div>

        <div
          className={`kit-card-summary${isEditingDesc ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'desc', previewCard.summary);
          }}
        >
          {isEditingDesc ? (
            <textarea
              className="kit-card-desc-input"
              autoFocus
              defaultValue={previewCard.summary}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) => onSaveEdit(data.id, 'desc', event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', previewCard.summary);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', event.target.value);
                }
              }}
            />
          ) : (
            <span>{previewCard.summary}</span>
          )}
        </div>

        <div ref={uiKitContentRef} className="kit-card-inner-frame-anchor">
          <div
            className={`kit-card-structured-shell${isEditingItems ? ' is-editing' : ''}${isCheckpointCard && isEditingItems ? ' is-checkpoint-shell' : ''}`}
            onClick={(event) => {
              if (editingState?.cardId === data.id) return;
              event.stopPropagation();
              onStartEdit(data.id, 'structuredItems', previewCard.items);
            }}
          >
            {isEditingItems ? (
              <textarea
                className={`kit-card-list-input${isCheckpointCard ? ' kit-card-list-input-checkpoint' : ''}`}
                autoFocus
                defaultValue={serializeStructuredItemsForEditor(previewCard.items, { isCheckpointCard })}
                ref={autoResizeTextarea}
                onClick={(event) => event.stopPropagation()}
                onInput={(event) => autoResizeTextarea(event.currentTarget)}
                onBlur={(event) => {
                  onSaveEdit(
                    data.id,
                    'structuredItems',
                    parseStructuredItemsFromEditor(event.target.value, previewCard.items, { isCheckpointCard }),
                  );
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    onSaveEdit(data.id, 'structuredItems', previewCard.items);
                  }

                  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                    event.preventDefault();
                    onSaveEdit(
                      data.id,
                      'structuredItems',
                      parseStructuredItemsFromEditor(event.currentTarget.value, previewCard.items, { isCheckpointCard }),
                    );
                  }
                }}
              />
            ) : (
              <StructuredContent kind={previewCard.structureKind} items={previewCard.items} />
            )}
          </div>
        </div>

        <div className="kit-card-meta-row">
          <div className="kit-counts">
            <span className="kit-count"><Paperclip size={13} />{previewCard.attachCount}</span>
            <span className="kit-count"><MessageCircle size={13} />{previewCard.discussCount}</span>
          </div>
        </div>

        {sectionConfig.footerMode !== 'none' && (
          <div className="kit-card-bottom-row">
            <div className="kit-owner">
              {previewCard.avatarSrc ? (
                <img className="kit-owner-avatar-image" src={previewCard.avatarSrc} alt="" />
              ) : (
                <span className="kit-owner-avatar-fallback" />
              )}
              <span>{previewCard.ownerName}</span>
            </div>
            <span className="kit-progress-text">{previewCard.footerText}</span>
          </div>
        )}

        {showConnectorPorts && (
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
              style={{ left: 0, top: '50%' }}
              onPointerDown={(e) => { e.stopPropagation(); onConnectStart('left', e); }}
              title="向左连线"
              data-port="left"
            />
            <div
              className="connector-hitarea port-right"
              style={{ left: '100%', top: '50%' }}
              onPointerDown={(e) => { e.stopPropagation(); onConnectStart('right', e); }}
              title="向右连线"
              data-port="right"
            />
          </>
        )}
      </div>
    );
  }

  if (sectionKey === 'evidence') {
    const isEditingItems = editingState?.cardId === data.id && editingState?.field === 'structuredItems';
    const previewCard = {
      title: '证据',
      cardTitle: data.title || '活动高峰期刷分投诉与异常补发同时上升',
      summary: data.desc || '客服在 7 天内累计收到 47 条相关投诉，用户核心抱怨不是“没拿到积分”，而是“规则不透明、被拦后没人解释”。',
      items: Array.isArray(data.structuredItems) && data.structuredItems.length
        ? data.structuredItems
        : ['异常集中在晚 8 点到 11 点', '邀请返积分与签到补签占投诉量的 81%'],
      tags,
      sourceMeta: data.source,
      attachCount: data.attachments?.length || 0,
      itemCount: Array.isArray(data.structuredItems) ? data.structuredItems.length : 0,
      confidence: typeof data.confidence === 'number' ? data.confidence : null,
    };

    return (
      <div
        ref={uiKitCardRef}
        className={`${cardClassName} ui-kit-card ui-kit-card-theme-evidence ui-kit-evidence-card ui-kit-card-no-footer`}
        {...interactiveProps}
      >
        <SketchCardFrame cardRef={uiKitCardRef} contentRef={uiKitContentRef} />
        <div className="kit-card-top">
          <div className="kit-card-heading">
            <span className="kit-type-icon kit-type-icon-evidence">
              <CardTypeIconImage src={typeMeta.iconSrc} label={typeMeta.label} className="kit-card-type-icon-image" />
            </span>
            <div className="kit-card-title-wrap">
              <span className="kit-card-title">
                <span className="kit-card-title-cn">{previewCard.title}</span>
              </span>
            </div>
          </div>

          <div className="kit-card-actions">
            {previewCard.tags.length > 0 && (
              <div className="kit-card-actions-tags">
                {previewCard.tags.map((tag, index) => (
                  <span key={`${tag.label}-${index}`} className={`kit-sketch-tag kit-sketch-tag-${tag.color} kit-card-inline-tag`}>{tag.label}</span>
                ))}
              </div>
            )}
            <button
              className="icon-btn kit-more-btn"
              onClick={(event) => {
                event.stopPropagation();
                setActiveCardMenuId(activeCardMenuId === data.id ? null : data.id);
              }}
              title="更多操作"
            >
              <MoreHorizontal size={15} />
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

        <div
          className={`kit-card-heading-title${isEditingTitle ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'title', previewCard.cardTitle);
          }}
        >
          {isEditingTitle ? (
            <textarea
              className="kit-card-title-input"
              autoFocus
              defaultValue={previewCard.cardTitle}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) => onSaveEdit(data.id, 'title', event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'title', previewCard.cardTitle);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'title', event.target.value);
                }
              }}
            />
          ) : (
            <span>{previewCard.cardTitle}</span>
          )}
        </div>

        <div
          className={`kit-card-summary${isEditingDesc ? ' is-editing' : ''}`}
          onClick={(event) => {
            if (editingState?.cardId === data.id) return;
            event.stopPropagation();
            onStartEdit(data.id, 'desc', previewCard.summary);
          }}
        >
          {isEditingDesc ? (
            <textarea
              className="kit-card-desc-input"
              autoFocus
              defaultValue={previewCard.summary}
              ref={autoResizeTextarea}
              onClick={(event) => event.stopPropagation()}
              onInput={(event) => autoResizeTextarea(event.currentTarget)}
              onBlur={(event) => onSaveEdit(data.id, 'desc', event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', previewCard.summary);
                }

                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  onSaveEdit(data.id, 'desc', event.target.value);
                }
              }}
            />
          ) : (
            <span>{previewCard.summary}</span>
          )}
        </div>

        <div ref={uiKitContentRef} className="kit-card-inner-frame-anchor">
          <div
            className={`kit-card-structured-shell${isEditingItems ? ' is-editing' : ''}`}
            onClick={(event) => {
              if (editingState?.cardId === data.id) return;
              event.stopPropagation();
              onStartEdit(data.id, 'structuredItems', previewCard.items);
            }}
          >
            {isEditingItems ? (
              <textarea
                className="kit-card-list-input"
                autoFocus
                defaultValue={previewCard.items.join('\n')}
                ref={autoResizeTextarea}
                onClick={(event) => event.stopPropagation()}
                onInput={(event) => autoResizeTextarea(event.currentTarget)}
                onBlur={(event) =>
                  onSaveEdit(
                    data.id,
                    'structuredItems',
                    event.target.value.split('\n').map((item) => item.trim()).filter(Boolean),
                  )
                }
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    onSaveEdit(data.id, 'structuredItems', previewCard.items);
                  }

                  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                    event.preventDefault();
                    onSaveEdit(
                      data.id,
                      'structuredItems',
                      event.currentTarget.value.split('\n').map((item) => item.trim()).filter(Boolean),
                    );
                  }
                }}
              />
            ) : (
              <StructuredContent kind="quote" items={previewCard.items} />
            )}
          </div>
        </div>

        <div className="kit-card-meta-row">
          <div className="kit-counts">
            <span className="kit-count"><Paperclip size={13} />{previewCard.attachCount}</span>
            <span className="kit-count"><MessageCircle size={13} />{previewCard.itemCount}</span>
          </div>
          {previewCard.confidence !== null && (
            <span className="kit-confidence-text">置信 {previewCard.confidence}%</span>
          )}
        </div>

        {showConnectorPorts && (
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
              style={{ left: 0, top: '50%' }}
              onPointerDown={(e) => { e.stopPropagation(); onConnectStart('left', e); }}
              title="向左连线"
              data-port="left"
            />
            <div
              className="connector-hitarea port-right"
              style={{ left: '100%', top: '50%' }}
              onPointerDown={(e) => { e.stopPropagation(); onConnectStart('right', e); }}
              title="向右连线"
              data-port="right"
            />
          </>
        )}
      </div>
    );
  }

  return (
    <div 
      className={contentCardClassName} 
      {...interactiveProps}
    >
      <div className="canvas-card-header-group">
        <div className="card-eyebrow-row">
          <span className={`card-type-chip card-type-${typeMeta.tone}`}>
            <CardTypeIconImage src={typeMeta.iconSrc} label={typeMeta.label} className="card-type-chip-image" />
            {typeMeta.label}
          </span>
          {statusLabel && (
            <span className={`canvas-tag card-status-pill tag-${statusColor}`}>{statusLabel}</span>
          )}
        </div>

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
            {tags.map((tag, index) => (
              <span key={index} className={`canvas-tag tag-${tag.color}`}>{tag.label}</span>
            ))}
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
              <Paperclip className="att-icon" size={12} strokeWidth={1.9} />
              <span title={attachment.label || attachment.name}>{attachment.label || attachment.name}</span>
            </div>
          ))}
        </div>
      )}

      <div className="canvas-card-bottom">
        <div className="canvas-card-footer">
          <span className="card-count-chip"><Paperclip size={13} />{data.attachments?.length || 0}</span>
          <span className="card-count-chip"><ListTodo size={13} />{Array.isArray(data.structuredItems) ? data.structuredItems.length : 0}</span>
        </div>

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

      {showConnectorPorts && (
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

