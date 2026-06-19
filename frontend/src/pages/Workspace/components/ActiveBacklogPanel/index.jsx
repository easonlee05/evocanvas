import React, { useMemo, useState } from 'react';
import {
  ListTodo,
  Pin,
  ChevronDown,
  HelpCircle,
  Scale,
  AlertTriangle,
  Paperclip,
} from 'lucide-react';
import {
  buildActiveGapItems,
  getCollapsedWidgetWidthByTitle,
  COLLAPSED_WIDGET_HEIGHT,
  WidgetActionButton,
  AnimatedWidgetShell,
  CollapsedWidgetPill,
} from '../../CanvasOverlays.jsx';

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
