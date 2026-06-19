import React, { useState } from 'react';
import { Timer, RotateCcw, Pause, Play, ChevronsRight } from 'lucide-react';
import { WidgetFrame, formatDuration } from '../../CanvasOverlays.jsx';

export function FocusTimerWidget({ widget, onUpdate, onPinToggle, onDragStart }) {
  const modes = ['收敛', '整理', '交接'];
  const presetMinutes = widget.durationMinutes || 20;
  const preview = '';
  const totalSeconds = Math.max(1, presetMinutes * 60);
  const elapsedRatio = 1 - widget.remainingSeconds / totalSeconds;
  const visualProgress = widget.isCompleted ? 1 : widget.isRunning ? Math.max(0.08, elapsedRatio) : 0.08;

  const [isEditing, setIsEditing] = useState(false);
  const [inputVal, setInputVal] = useState(String(presetMinutes));

  const applyPreset = (nextMinutes) => {
    setIsEditing(false);
    onUpdate({
      durationMinutes: nextMinutes,
      remainingSeconds: nextMinutes * 60,
      isRunning: false,
      isCompleted: false,
    });
  };

  const handleStartPause = () => {
    setIsEditing(false);
    onUpdate({
      isRunning: !widget.isRunning,
      isCompleted: false,
    });
  };

  const handleReset = () => {
    setIsEditing(false);
    onUpdate({
      remainingSeconds: presetMinutes * 60,
      isRunning: false,
      isCompleted: false,
    });
  };

  const handleAdvance = () => {
    setIsEditing(false);
    const currentIndex = modes.indexOf(widget.mode || '收敛');
    const nextMode = modes[(currentIndex + 1) % modes.length];
    onUpdate({
      mode: nextMode,
      remainingSeconds: presetMinutes * 60,
      isRunning: false,
      isCompleted: false,
    });
  };

  const handleTimeClick = () => {
    if (!widget.isRunning) {
      setInputVal(String(presetMinutes));
      setIsEditing(true);
    }
  };

  const handleFinishEditing = () => {
    setIsEditing(false);
    const parsed = parseInt(inputVal, 10);
    if (!isNaN(parsed) && parsed > 0 && parsed <= 999) {
      onUpdate({
        durationMinutes: parsed,
        remainingSeconds: parsed * 60,
        isRunning: false,
        isCompleted: false,
      });
    }
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
            {isEditing ? (
              <input
                type="text"
                className="workspace-timer-display-input"
                value={inputVal}
                onChange={(event) => {
                  const val = event.target.value.replace(/\D/g, '');
                  setInputVal(val);
                }}
                onBlur={handleFinishEditing}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    handleFinishEditing();
                  } else if (event.key === 'Escape') {
                    setIsEditing(false);
                  }
                }}
                autoFocus
              />
            ) : (
              <div
                className={`workspace-timer-display${!widget.isRunning ? ' editable' : ''}`}
                onClick={handleTimeClick}
                title={!widget.isRunning ? '点击修改时间' : undefined}
              >
                {formatDuration(widget.remainingSeconds)}
              </div>
            )}
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
              <RotateCcw size={14} />
            </span>
            <span className="workspace-timer-side-label">重置</span>
          </button>

          <button type="button" className="workspace-timer-primary-action" onClick={handleStartPause}>
            <span className="workspace-timer-primary-circle">
              {widget.isRunning ? <Pause size={22} fill="currentColor" /> : <Play size={22} fill="currentColor" />}
            </span>
            <span className="workspace-timer-primary-label">
              {widget.isRunning ? '暂停' : widget.remainingSeconds === 0 || widget.isCompleted ? '开始下一轮' : '开始'}
            </span>
          </button>

          <button type="button" className="workspace-timer-side-action" onClick={handleAdvance}>
            <span className="workspace-timer-side-icon">
              <ChevronsRight size={14} />
            </span>
            <span className="workspace-timer-side-label">{widget.isCompleted ? '下一轮' : '跳过休息'}</span>
          </button>
        </div>
      </div>
    </WidgetFrame>
  );
}
