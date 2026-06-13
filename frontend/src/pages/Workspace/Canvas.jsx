import React, { useState, useEffect } from 'react';
import './Canvas.css';
import { FileText, MessageSquare, AlertCircle, FileCode2, CheckSquare, ListTodo, MoreHorizontal, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';

function CustomArrow({ start, end, transform, activeCardId, outIndex = 0, outCount = 1, inIndex = 0, inCount = 1 }) {
  const [path, setPath] = useState('');
  
  useEffect(() => {
    const update = () => {
      const s = document.getElementById(start);
      const e = document.getElementById(end);
      const container = document.querySelector('.canvas-lanes');
      if (!s || !e || !container) return;
      
      const sRect = s.getBoundingClientRect();
      const eRect = e.getBoundingClientRect();
      const cRect = container.getBoundingClientRect();
      
      const scale = transform.scale;
      
      // 检测起止点是否处于同一列
      const isSameColumn = Math.abs(sRect.left - eRect.left) < 10;
      
      // 基础起点坐标
      const startX = (sRect.right - cRect.left) / scale;
      const startYBase = (sRect.top + sRect.height / 2 - cRect.top) / scale;
      
      // 基础终点坐标：如果是同列，终点重定向至右边缘，否则取左边缘
      let endX = 0;
      if (isSameColumn) {
        endX = (eRect.right - cRect.left) / scale;
      } else {
        endX = (eRect.left - cRect.left) / scale;
      }
      const endYBase = (eRect.top + eRect.height / 2 - cRect.top) / scale;
      
      // 流出起点偏置 (垂直方向错开 16px 间距)
      const outOffset = outCount > 1 ? (outIndex - (outCount - 1) / 2) * 16 : 0;
      const startY = startYBase + outOffset;
      
      // 流入终点偏置 (垂直方向错开 16px 间距)
      const inOffset = inCount > 1 ? (inIndex - (inCount - 1) / 2) * 16 : 0;
      const endY = endYBase + inOffset;
      
      // 计算折点 X 轴坐标
      let midX = 0;
      if (isSameColumn) {
        // 同列连接：折向右侧通道绕行，多条线水平错开 12px
        midX = startX + 24 + outIndex * 12;
      } else {
        // 不同列连接：折点取中点并偏置错开 12px，同时进行无条件强限幅（由于列距拓宽为 56px，在此保留 12px 安全侧距）
        const midXBase = startX + (endX - startX) / 2;
        const midOffset = (outIndex - inIndex) * 12;
        midX = midXBase + midOffset;
        
        const minMidX = startX + 12;
        const maxMidX = endX - 12;
        if (minMidX < maxMidX) {
          midX = Math.max(minMidX, Math.min(maxMidX, midX));
        } else {
          midX = midXBase;
        }
      }
      
      // 动态计算平滑圆角半径，最大 12px，在极窄间距时自适应变小
      const signY = endY > startY ? 1 : -1;
      const r = Math.min(12, Math.abs(midX - startX), Math.abs(endX - midX), Math.abs(endY - startY) / 2);
      
      if (r > 0 && Math.abs(endY - startY) > 2) {
        // 使用 Q 指令绘制圆角折线
        setPath(
          `M ${startX} ${startY} ` +
          `L ${midX - r} ${startY} ` +
          `Q ${midX} ${startY}, ${midX} ${startY + r * signY} ` +
          `L ${midX} ${endY - r * signY} ` +
          `Q ${midX} ${endY}, ${midX + r} ${endY} ` +
          `L ${endX} ${endY}`
        );
      } else {
        // 几乎在同一水平线时，退化为常规直线
        setPath(`M ${startX} ${startY} L ${endX} ${endY}`);
      }
    };
    
    update();
    const interval = setInterval(update, 50);
    return () => clearInterval(interval);
  }, [start, end, transform, outIndex, outCount, inIndex, inCount]);
  
  if (!path) return null;

  // 根据当前 activeCardId 计算高亮状态
  const isRelated = activeCardId === start || activeCardId === end;
  
  let opacity = 1.0; // 平时透明度拉满
  let strokeColor = '#94a3b8'; // 使用高质感中灰
  let strokeWidth = 1.8;
  
  if (activeCardId !== null) {
    if (isRelated) {
      opacity = 1.0;
      strokeColor = '#007aff'; // 苹果系统蓝
      strokeWidth = 2.8;
    } else {
      opacity = 0.18; // 弱化状态保持 0.18，使其依稀可见
      strokeColor = '#cbd5e1';
      strokeWidth = 1.5;
    }
  }

  return (
    <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 10, overflow: 'visible' }}>
      <defs>
        <marker id={`arrowhead-${start}-${end}`} markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill={strokeColor} />
        </marker>
      </defs>
      <path 
        d={path} 
        fill="none" 
        stroke={strokeColor} 
        strokeWidth={strokeWidth} 
        opacity={opacity}
        style={{ transition: 'stroke 0.2s, stroke-width 0.2s, opacity 0.2s' }}
        markerEnd={`url(#arrowhead-${start}-${end})`} 
      />
    </svg>
  );
}

function CardPersonaRow({ meta }) {
  if (!meta) return null;

  return (
    <div className="card-persona-row">
      <span className="owner-label">{meta.label || '负责人'}</span>
      <div className={`card-avatar card-avatar-${meta.avatarTone || 'slate'}`}>{meta.avatar}</div>
      <span className="owner-name">{meta.name}</span>
    </div>
  );
}

function StructuredContent({ kind = 'list', items = [] }) {
  if (!items?.length) return null;

  if (kind === 'quote') {
    return (
      <div className="structured-block structured-quote">
        {items.map((item) => (
          <div key={item} className="structured-quote-item">
            <span className="structured-quote-text">{item}</span>
            <span className="structured-quote-mark">”</span>
          </div>
        ))}
      </div>
    );
  }

  if (kind === 'checkpoints') {
    return (
      <div className="structured-block structured-checkpoints">
        {items.map((item) => (
          <div key={`${item.text}-${item.date || ''}`} className="structured-checkpoint-item">
            <span className={`checkpoint-dot checkpoint-dot-${item.state || 'pending'}`} />
            <div className="checkpoint-copy">
              <span className="checkpoint-text">{item.text}</span>
            </div>
            {item.date && <span className="checkpoint-date">{item.date}</span>}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="structured-block structured-list">
      {items.map((item) => (
        <div key={item} className="structured-list-item">
          <span className="fact-dot" />
          <span className="structured-list-text">{item}</span>
        </div>
      ))}
    </div>
  );
}

function CanvasCard({ data, activeCardId, setActiveCardId, isActiveSelf, isRelated }) {
  const primaryTag = data.tags?.[0];
  const secondaryTags = data.tags?.slice(1) || [];
  const hasTags = primaryTag || data.statusPill;

  const cardClassName = `canvas-card${isActiveSelf ? ' active-self' : ''}${isRelated && !isActiveSelf ? ' active-related' : ''}`;

  return (
    <div 
      className={cardClassName} 
      id={data.id}
      onMouseEnter={() => setActiveCardId(data.id)}
      onMouseLeave={() => setActiveCardId(null)}
    >
      <div className="canvas-card-header-group">
        <div className="canvas-card-header">
          <span className="canvas-card-title">{data.title}</span>
          <button className="icon-btn" style={{width: 20, height: 20}}><MoreHorizontal size={14}/></button>
        </div>

        {hasTags && (
          <div className="card-tags-row">
            {primaryTag && (
              <span className={`canvas-tag tag-${primaryTag.color}`}>{primaryTag.label}</span>
            )}
            {secondaryTags.length > 0 && secondaryTags.map((t, i) => (
              <span key={i} className={`canvas-tag tag-${t.color}`}>{t.label}</span>
            ))}
            {data.statusPill && (
              <span className={`canvas-tag tag-${data.statusPill.color}`}>{data.statusPill.label}</span>
            )}
          </div>
        )}
      </div>

      {data.desc && <div className="canvas-card-desc">{data.desc}</div>}

      <StructuredContent kind={data.structureKind} items={data.structuredItems} />

      {data.attachments && (
        <div className="card-attachments">
          {data.attachments.map((att, i) => (
            <div key={i} className="attachment-pill">
              <span className="att-icon">{att.icon}</span>
              <span>{att.label}</span>
            </div>
          ))}
        </div>
      )}

      <div className="canvas-card-bottom">
        {(data.source || data.owner) && (
          <div className="card-meta-stack">
            <CardPersonaRow meta={data.source} />
            <CardPersonaRow meta={data.owner} />
          </div>
        )}

        {typeof data.confidence === 'number' && (
          <div className="card-confidence-row">
            <div className="card-confidence-copy">
              <span className="owner-label">置信度</span>
              <span className="confidence-value">{data.confidence}%</span>
            </div>
            <div className="confidence-meter" aria-label={`置信度 ${data.confidence}%`}>
              <div className="confidence-meter-fill" style={{ width: `${data.confidence}%` }} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineScrubber({ isChatOpen }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (isCollapsed) {
    return (
      <div className={`timeline-scrubber collapsed${isChatOpen ? ' chat-open' : ''}`} onClick={() => setIsCollapsed(false)} style={{
        padding: '8px var(--sp-6)',
        cursor: 'pointer',
        width: 'auto',
        maxWidth: '200px',
        height: 'auto',
        gap: 0,
        borderRadius: 'var(--r-xl)'
      }}>
        <div className="timeline-header" style={{ margin: 0, justifyContent: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600 }}>显示项目时间轴</span>
          <ChevronUp size={14} className="text-tertiary" />
        </div>
      </div>
    );
  }

  return (
    <div className={`timeline-scrubber${isChatOpen ? ' chat-open' : ''}`}>
      <div className="timeline-header">
        <span>时间轴：项目里程碑</span>
        <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="icon-btn" title="更多选项" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>
            <MoreHorizontal size={14} />
          </button>
          <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setIsCollapsed(true); }} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>
            <ChevronDown size={14} className="text-tertiary" />
          </button>
        </div>
      </div>

      <div className="timeline-body">
        {/* 顶部的日期和刻度线 */}
        <div className="timeline-ticks">
          <div className="tick-item" style={{ left: '12.5%' }}>
            <span className="tick-label">Q2 - 4月</span>
            <div className="tick-line"></div>
          </div>
          <div className="tick-item" style={{ left: '25%' }}>
            <span className="tick-label">5月</span>
            <div className="tick-line"></div>
          </div>
          <div className="tick-item" style={{ left: '70%' }}>
            <span className="tick-label">6月</span>
            <div className="tick-line"></div>
          </div>
          <div className="tick-item" style={{ left: '92%' }}>
            <span className="tick-label">Q3 - 7月</span>
            <div className="tick-line"></div>
          </div>
        </div>

        {/* 分段轨道 */}
        <div className="timeline-segmented-track">
          <div className="track-segment segment-gray" style={{ width: '25%' }}>
            <span>阶段</span>
          </div>
          <div className="track-segment segment-blue" style={{ width: '45%' }}>
            <span>内测发布</span>
          </div>
          <div className="track-segment segment-gray" style={{ width: '30%' }}>
            <span>MVP 上线</span>
          </div>

          {/* 黑色当前日期指示针 */}
          <div className="timeline-current-pointer" style={{ left: '51%' }}>
            <div className="pointer-line"></div>
            <span className="pointer-label">当前日期：5月18日</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Canvas({ isChatOpen = true }) {
  const [showTodos, setShowTodos] = useState(false);
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [activeCardId, setActiveCardId] = useState(null);
  const isDragging = React.useRef(false);
  const dragStart = React.useRef({ x: 0, y: 0 });

  // 绑定原生 wheel 事件以防止 default scroll
  const containerRef = React.useRef(null);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handleWheel = (e) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const zoomFactor = -e.deltaY * 0.01;
        setTransform(t => {
          let newScale = t.scale * (1 + zoomFactor);
          newScale = Math.min(Math.max(newScale, 0.1), 3);
          return { ...t, scale: newScale };
        });
      } else {
        setTransform(t => ({
          ...t,
          x: t.x - e.deltaX,
          y: t.y - e.deltaY
        }));
      }
    };
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  const handlePointerDown = (e) => {
    if (e.target.closest('.canvas-card') || e.target.closest('.todos-trigger') || e.target.closest('.timeline-scrubber')) return;
    isDragging.current = true;
    dragStart.current = { x: e.clientX - transform.x, y: e.clientY - transform.y };
    e.target.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e) => {
    if (!isDragging.current) return;
    setTransform(t => ({
      ...t,
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y
    }));
  };

  const handlePointerUp = (e) => {
    isDragging.current = false;
    e.target.releasePointerCapture(e.pointerId);
  };

  // 统计每个节点的发出和流入关系以计算偏置
  const outConnections = {};
  const inConnections = {};
  const rawArrows = [];

  Object.values(DEMO_CANVAS_SECTIONS).flat().forEach(card => {
    if (card.next) {
      const nextArr = Array.isArray(card.next) ? card.next : [card.next];
      nextArr.forEach(targetId => {
        rawArrows.push({ start: card.id, end: targetId });
        
        if (!outConnections[card.id]) outConnections[card.id] = [];
        outConnections[card.id].push(targetId);
        
        if (!inConnections[targetId]) inConnections[targetId] = [];
        inConnections[targetId].push(card.id);
      });
    }
  });

  // 映射为带有偏置属性的 arrows 数组
  const arrows = rawArrows.map(arr => {
    const outs = outConnections[arr.start] || [];
    const ins = inConnections[arr.end] || [];
    return {
      start: arr.start,
      end: arr.end,
      outIndex: outs.indexOf(arr.end),
      outCount: outs.length,
      inIndex: ins.indexOf(arr.start),
      inCount: ins.length
    };
  });

  // 辅助函数判断卡片高亮关系
  const checkCardActiveState = (cardId) => {
    if (activeCardId === null) return { isActiveSelf: false, isRelated: false };
    if (activeCardId === cardId) return { isActiveSelf: true, isRelated: true };
    const isRelated = arrows.some(arr => 
      (arr.start === activeCardId && arr.end === cardId) || 
      (arr.end === activeCardId && arr.start === cardId)
    );
    return { isActiveSelf: false, isRelated };
  };

  const renderCard = (card) => {
    const { isActiveSelf, isRelated } = checkCardActiveState(card.id);
    return (
      <CanvasCard 
        key={card.id} 
        data={card} 
        activeCardId={activeCardId}
        setActiveCardId={setActiveCardId}
        isActiveSelf={isActiveSelf}
        isRelated={isRelated}
      />
    );
  };

  return (
    <div 
      className="canvas-container" 
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        backgroundPosition: `${transform.x}px ${transform.y}px`,
        backgroundSize: `${24 * transform.scale}px ${24 * transform.scale}px`
      }}
    >
      {/* 悬浮 Todos 触发按钮 - 独立于缩放画布 */}
      <button 
        className="todos-trigger" 
        style={{position: 'absolute', top: 24, right: isChatOpen ? 452 : 160, zIndex: 10}}
        onClick={() => setShowTodos(!showTodos)}
      >
        <ListTodo size={14} /> 活跃待办 <ChevronRight size={14} style={{transform: showTodos ? 'rotate(90deg)' : 'none', transition: '0.2s'}}/>
      </button>

      {/* 无限缩放平面 */}
      <div 
        className="canvas-lanes"
        style={{
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
          transformOrigin: '0 0'
        }}
      >
          
          <div className="canvas-lane">
            <div className="lane-header">
              <h3>1. 探索发现</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">用户反馈</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.evidence.map(renderCard)}
                </div>
              </div>
            </div>
          </div>

          <div className="canvas-lane">
            <div className="lane-header">
              <h3>2. 需求定义</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">功能设计</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.problems.map(renderCard)}
                </div>
              </div>
            </div>
          </div>

          <div className="canvas-lane">
            <div className="lane-header">
              <h3>3. 问题澄清</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">待澄清问题</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.clarify.map(renderCard)}
                </div>
              </div>
            </div>
          </div>

          <div className="canvas-lane">
            <div className="lane-header">
              <h3>4. 方案规划</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">决策确认</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.rules.map(renderCard)}
                </div>
              </div>
            </div>
          </div>

          <div className="canvas-lane">
            <div className="lane-header">
              <h3>5. 落地执行</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">迭代计划</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.planning.map(renderCard)}
                </div>
              </div>
            </div>
          </div>

          {/* 渲染所有箭头 */}
          {arrows.map((arr, i) => (
            <CustomArrow 
              key={i} 
              start={arr.start} 
              end={arr.end} 
              transform={transform} 
              activeCardId={activeCardId}
              outIndex={arr.outIndex}
              outCount={arr.outCount}
              inIndex={arr.inIndex}
              inCount={arr.inCount}
            />
          ))}

        </div>

      {/* 底部时间轴 */}
      <TimelineScrubber isChatOpen={isChatOpen} />

      {/* 活跃待办浮层 */}
      {showTodos && (
        <div style={{
          position: 'absolute', top: 60, right: isChatOpen ? 452 : 180, width: 280,
          background: '#fff', borderRadius: 12, boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
          border: '1px solid var(--border)', zIndex: 100, padding: 16
        }}>
          <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 12}}>
            <span style={{fontSize: 12, fontWeight: 700}}>活跃待办事项 (3)</span>
            <MoreHorizontal size={14} color="var(--text-tertiary)"/>
          </div>
          <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
            <label style={{display: 'flex', gap: 8, fontSize: 13, alignItems: 'flex-start'}}>
              <input type="checkbox" defaultChecked />
              <div>
                <div style={{fontWeight: 600}}>评估产品原型反馈</div>
                <div style={{fontSize: 11, color: 'var(--text-tertiary)'}}>优先级 · 高</div>
              </div>
            </label>
            <label style={{display: 'flex', gap: 8, fontSize: 13, alignItems: 'flex-start'}}>
              <input type="checkbox" />
              <div>
                <div style={{fontWeight: 600}}>与研发对齐进度</div>
                <div style={{fontSize: 11, color: 'var(--text-tertiary)'}}>截止日期 · 今天</div>
              </div>
            </label>
            <label style={{display: 'flex', gap: 8, fontSize: 13, alignItems: 'flex-start'}}>
              <input type="checkbox" />
              <div>
                <div style={{fontWeight: 600}}>确认 UI 高保真设计</div>
                <div style={{fontSize: 11, color: 'var(--text-tertiary)'}}>优先级 · 高</div>
              </div>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
