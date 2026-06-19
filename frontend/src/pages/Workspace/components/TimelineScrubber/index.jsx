import React, { useMemo } from 'react';
import { Pin, ChevronDown, Sparkles } from 'lucide-react';
import {
  buildTimelineProjection,
  getCollapsedWidgetWidthByTitle,
  COLLAPSED_WIDGET_HEIGHT,
  WidgetActionButton,
  AnimatedWidgetShell,
  CollapsedWidgetPill,
} from '../../CanvasOverlays.jsx';

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
