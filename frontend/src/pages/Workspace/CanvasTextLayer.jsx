import React from 'react';

export default function CanvasTextLayer({
  canvasTexts,
  onBeginDrag,
  onTextChange,
  onTextFinishEdit,
  onTextStartEdit,
}) {
  return canvasTexts.map((item) => (
    <div
      key={item.id}
      className={`canvas-text-node${item.isEditing ? ' editing' : ''}`}
      style={{
        position: 'absolute',
        left: item.x,
        top: item.y,
        zIndex: 20,
      }}
      onPointerDown={(event) => onBeginDrag(item.id, event)}
    >
      {item.isEditing ? (
        <textarea
          id={`canvas-text-editor-${item.id}`}
          style={{
            background: '#ffffff',
            border: '1px dashed #1f6fff',
            outline: 'none',
            fontFamily: 'inherit',
            fontSize: '13px',
            color: 'var(--text-primary)',
            padding: '6px 10px',
            borderRadius: '6px',
            resize: 'both',
            minWidth: '120px',
            minHeight: '36px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          }}
          value={item.text}
          placeholder="输入注释文字..."
          onChange={(event) => onTextChange(item.id, event.target.value)}
          onBlur={(event) => onTextFinishEdit(item.id, event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              onTextFinishEdit(item.id, event.target.value);
            } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              onTextFinishEdit(item.id, event.target.value);
            }
          }}
        />
      ) : (
        <div
          className="canvas-text-label"
          style={{
            background: 'transparent',
            border: '1px solid transparent',
            color: 'var(--text-primary)',
            padding: '6px 10px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'text',
            whiteSpace: 'pre-wrap',
            userSelect: 'none',
            lineHeight: '1.4',
          }}
          onClick={(event) => {
            event.stopPropagation();
          }}
          onDoubleClick={(event) => {
            event.stopPropagation();
            onTextStartEdit(item.id);
          }}
          title="双击编辑，拖拽移动"
        >
          {item.text}
        </div>
      )}
    </div>
  ));
}
