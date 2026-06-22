import React, { useEffect, useMemo, useState } from 'react';
import { Clock3 } from 'lucide-react';
import { WidgetFrame, formatClock } from '../../CanvasOverlays.jsx';

export function ClockWidget({ widget, onUpdate, onPinToggle, onDragStart, onDelete }) {
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
      onDelete={onDelete}
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
