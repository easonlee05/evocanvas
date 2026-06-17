import React, { useEffect, useState } from 'react';
import { getPortPosition, routeEdge } from './edgeRouter.js';

function getCanvasRect(rect, containerRect, scale, id = null) {
  return {
    id,
    left: (rect.left - containerRect.left) / scale,
    right: (rect.right - containerRect.left) / scale,
    top: (rect.top - containerRect.top) / scale,
    bottom: (rect.bottom - containerRect.top) / scale,
  };
}

function getElementCanvasRect(element, container, scale) {
  return getCanvasRect(
    element.getBoundingClientRect(),
    container.getBoundingClientRect(),
    scale,
    element.id,
  );
}

function getCanvasCardObstacles(container, scale) {
  return [...document.querySelectorAll('.canvas-card')]
    .filter((cardElement) => cardElement.id)
    .map((cardElement) => getElementCanvasRect(cardElement, container, scale));
}

export function CustomArrow({
  start,
  end,
  transform,
  visualState = 'muted',
  accentColor,
  outIndex = 0,
  outCount = 1,
  inIndex = 0,
  inCount = 1,
  onDelete,
  canDelete = false,
  startPort = null,
  endPort = null,
}) {
  const [path, setPath] = useState('');
  const [arrowHead, setArrowHead] = useState('');
  const [midPoint, setMidPoint] = useState(null);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const update = () => {
      const sourceElement = document.getElementById(start);
      const targetElement = document.getElementById(end);
      const container = document.querySelector('.canvas-lanes');
      if (!sourceElement || !targetElement || !container) return;

      const sourceRect = getElementCanvasRect(sourceElement, container, transform.scale);
      const targetRect = getElementCanvasRect(targetElement, container, transform.scale);
      const route = routeEdge({
        sourceRect,
        targetRect,
        sourcePort: startPort,
        targetPort: endPort,
        sourceOffsetIndex: outIndex,
        sourceOffsetTotal: outCount,
        targetOffsetIndex: inIndex,
        targetOffsetTotal: inCount,
        obstacles: getCanvasCardObstacles(container, transform.scale),
      });

      setMidPoint(route.midPoint);
      setPath(route.path);
      setArrowHead(route.arrowHead);
    };

    update();
    const interval = window.setInterval(update, 50);
    return () => window.clearInterval(interval);
  }, [start, end, transform, outIndex, outCount, inIndex, inCount, startPort, endPort]);

  if (!path) return null;

  let opacity = 1;
  let strokeColor = '#94a3b8';
  let strokeWidth = 1.8;
  const isHidden = visualState === 'hidden';

  if (visualState === 'active' || visualState === 'focused') {
    strokeColor = accentColor || '#1f6fff';
    strokeWidth = 2.8;
  } else if (visualState === 'hidden') {
    opacity = 0;
    strokeColor = '#cbd5e1';
    strokeWidth = 1.5;
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        overflow: 'visible',
        zIndex: 1,
        pointerEvents: 'none',
      }}
    >
      <svg
        className="canvas-arrow-svg"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          overflow: 'visible',
        }}
      >
        <path
          d={path}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          fill="none"
          style={{ opacity, transition: 'stroke 0.2s, stroke-width 0.2s, opacity 0.2s' }}
        />
        {arrowHead && (
          <polygon
            points={arrowHead}
            fill={strokeColor}
            style={{ opacity, transition: 'fill 0.2s, opacity 0.2s' }}
          />
        )}
        <path
          d={path}
          stroke="transparent"
          strokeWidth="10"
          fill="none"
          style={{ cursor: 'pointer', pointerEvents: isHidden ? 'none' : 'stroke' }}
          onMouseEnter={() => {
            if (!isHidden) setIsHovered(true);
          }}
          onMouseLeave={() => setIsHovered(false)}
        />
      </svg>
      {!isHidden && isHovered && midPoint && onDelete && canDelete && (
        <button
          style={{
            position: 'absolute',
            left: midPoint.x - 10,
            top: midPoint.y - 10,
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: '#ef4444',
            color: '#ffffff',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '10px',
            fontWeight: 'bold',
            lineHeight: 1,
            zIndex: 99,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            pointerEvents: 'auto',
          }}
          onClick={(event) => {
            event.stopPropagation();
            onDelete(start, end);
          }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          title="删除连接线"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export function TempConnectionLine({ startCardId, startPort, targetCardId, endX, endY, endPort, transform }) {
  const [routePath, setRoutePath] = useState('');
  const [arrowHead, setArrowHead] = useState('');

  useEffect(() => {
    const sourceElement = document.getElementById(startCardId);
    const container = document.querySelector('.canvas-lanes');
    if (!sourceElement || !container) return;

    const targetElement = targetCardId ? document.getElementById(targetCardId) : null;
    const sourceRect = getElementCanvasRect(sourceElement, container, transform.scale);
    const targetRect = targetElement ? getElementCanvasRect(targetElement, container, transform.scale) : null;
    const route = routeEdge({
      sourceRect,
      targetRect,
      targetPoint: { x: endX, y: endY },
      sourcePort: startPort,
      targetPort: endPort,
      obstacles: getCanvasCardObstacles(container, transform.scale),
    });

    setRoutePath(route.path);
    setArrowHead(route.arrowHead);
  }, [startCardId, startPort, targetCardId, endX, endY, endPort, transform.scale]);

  if (!routePath) return null;

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 100,
        overflow: 'visible',
      }}
    >
      <path
        d={routePath}
        stroke="#1f6fff"
        strokeWidth="2"
        strokeDasharray="4 4"
        fill="none"
      />
      {arrowHead && <polygon points={arrowHead} fill="#1f6fff" />}
    </svg>
  );
}

export function getCardPorts(rect) {
  return {
    top: getPortPosition(rect, 'top'),
    right: getPortPosition(rect, 'right'),
    bottom: getPortPosition(rect, 'bottom'),
    left: getPortPosition(rect, 'left'),
  };
}

export function getPortPointByName(element, container, scale, port) {
  return getPortPosition(getElementCanvasRect(element, container, scale), port || 'right');
}

export function getCardRectInCanvas(rect, containerRect, scale, id = null) {
  return getCanvasRect(rect, containerRect, scale, id);
}
