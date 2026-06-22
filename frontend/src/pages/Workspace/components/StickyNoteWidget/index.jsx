import React from 'react';
import { StickyNote } from 'lucide-react';
import { WidgetFrame, formatDateLabel } from '../../CanvasOverlays.jsx';

export function StickyNoteWidget({ widget, onUpdate, onPinToggle, onDragStart, onDelete }) {
  const preview = widget.content?.trim() || widget.title?.trim() || '记一句临时想法';

  return (
    <WidgetFrame
      widget={widget}
      icon={<StickyNote size={14} />}
      title="便签"
      preview={preview}
      onPinToggle={onPinToggle}
      onDragStart={onDragStart}
      onDelete={onDelete}
      onCollapsedChange={(nextCollapsed) => onUpdate({ isCollapsed: nextCollapsed })}
      className={`note-tone-${widget.theme || 'sun'}`}
      footer={<span>创建于 {formatDateLabel(new Date(widget.createdAt))}</span>}
    >
      <textarea
        className="workspace-widget-textarea note-body"
        value={widget.content || ''}
        onChange={(event) => onUpdate({ content: event.target.value })}
        placeholder="写下一句提醒、判断或灵感..."
      />
    </WidgetFrame>
  );
}
