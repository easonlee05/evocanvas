import React, { useState } from 'react';
import { Archive } from 'lucide-react';
import { WidgetFrame } from '../../CanvasOverlays.jsx';

export function ParkingLotWidget({ widget, onUpdate, onPinToggle, onDragStart, onDelete }) {
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
      onDelete={onDelete}
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
