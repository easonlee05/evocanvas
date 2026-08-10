import React, { useEffect, useState } from 'react';
import { getPortPosition, routeEdge } from './edgeRouter.js';

function getGeometryCardObstacles(geometry) {
  return Object.values(geometry || {}).filter((rect) => rect?.id);
}

export function CustomArrow({
  start,
  end,
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
  geometry = null,
}) {
  const [path, setPath] = useState('');
  const [arrowHead, setArrowHead] = useState('');
  const [midPoint, setMidPoint] = useState(null);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const sourceRect = geometry?.[start];
    const targetRect = geometry?.[end];
    if (!sourceRect || !targetRect) return;

    const route = routeEdge({
      sourceRect,
      targetRect,
      sourcePort: startPort,
      targetPort: endPort,
      sourceOffsetIndex: outIndex,
      sourceOffsetTotal: outCount,
      targetOffsetIndex: inIndex,
      targetOffsetTotal: inCount,
      obstacles: getGeometryCardObstacles(geometry),
    });

    setMidPoint(route.midPoint);
    setPath(route.path);
    setArrowHead(route.arrowHead);
  // 依赖只收窄为端点卡片的几何引用（geometry?.[start] / geometry?.[end]），
  // 而非整个 geometry 对象。未变化的卡片在 refreshGeometry 中复用旧引用，
  // 因此只有端点卡片几何变化才触发重算。
  // 取舍：非端点卡片移动改变 obstacles 布局时，箭头不会重算避障路由。
  // 箭头不会断裂，只是避障路径可能不是最优，1.0 阶段可接受。
  }, [start, end, outIndex, outCount, inIndex, inCount, startPort, endPort, geometry?.[start], geometry?.[end]]);

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

export function TempConnectionLine({
  startCardId,
  startPort,
  targetCardId,
  endX,
  endY,
  endPort,
  geometry = null,
}) {
  const [routePath, setRoutePath] = useState('');
  const [arrowHead, setArrowHead] = useState('');

  useEffect(() => {
    const sourceRect = geometry?.[startCardId];
    const targetRect = geometry?.[targetCardId] || null;
    if (!sourceRect) return;

    const route = routeEdge({
      sourceRect,
      targetRect,
      targetPoint: { x: endX, y: endY },
      sourcePort: startPort,
      targetPort: endPort,
      obstacles: getGeometryCardObstacles(geometry),
    });

    setRoutePath(route.path);
    setArrowHead(route.arrowHead);
  }, [startCardId, startPort, targetCardId, endX, endY, endPort, geometry?.[startCardId], geometry?.[targetCardId]]);

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