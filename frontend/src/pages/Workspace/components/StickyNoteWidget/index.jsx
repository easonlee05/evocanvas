import React from 'react';
import { StickyNote } from 'lucide-react';
import { WidgetFrame, formatDateLabel } from '../../CanvasOverlays.jsx';

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
