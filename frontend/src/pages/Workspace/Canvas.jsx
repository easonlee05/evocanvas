import React, { useState, useEffect } from 'react';
import './Canvas.css';
import { FileText, MessageSquare, AlertCircle, FileCode2, CheckSquare, ListTodo, MoreHorizontal, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';
import { DEMO_CANVAS_SECTIONS } from './demoScenario.js';

function CustomArrow({ start, end, transform }) {
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
      const startX = (sRect.right - cRect.left) / scale;
      const startY = (sRect.top + sRect.height / 2 - cRect.top) / scale;
      const endX = (eRect.left - cRect.left) / scale;
      const endY = (eRect.top + eRect.height / 2 - cRect.top) / scale;
      
      const cp1X = startX + (endX - startX) / 2;
      const cp1Y = startY;
      const cp2X = cp1X;
      const cp2Y = endY;
      
      setPath(`M ${startX} ${startY} C ${cp1X} ${cp1Y}, ${cp2X} ${cp2Y}, ${endX} ${endY}`);
    };
    
    update();
    const interval = setInterval(update, 50);
    return () => clearInterval(interval);
  }, [start, end, transform]);
  
  if (!path) return null;
  return (
    <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1, overflow: 'visible' }}>
      <defs>
        <marker id="arrowhead" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill="#cbd5e1" />
        </marker>
      </defs>
      <path d={path} fill="none" stroke="#cbd5e1" strokeWidth="2" markerEnd="url(#arrowhead)" />
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

function CanvasCard({ data }) {
  const primaryTag = data.tags?.[0];
  const secondaryTags = data.tags?.slice(1) || [];

  return (
    <div className="canvas-card" id={data.id}>
      {primaryTag && (
        <div className="card-eyebrow-row">
          <span className={`canvas-tag canvas-tag-eyebrow tag-${primaryTag.color}`}>{primaryTag.label}</span>
          {secondaryTags.length > 0 && (
            <div className="card-secondary-tags">
              {secondaryTags.map((t, i) => (
                <span key={i} className={`canvas-tag canvas-tag-subtle tag-${t.color}`}>{t.label}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="canvas-card-header">
        <span className="canvas-card-title">{data.title}</span>
        <button className="icon-btn" style={{width: 20, height: 20}}><MoreHorizontal size={14}/></button>
      </div>

      {data.statusPill && (
        <div className="card-status-row">
          <span className={`canvas-tag tag-${data.statusPill.color}`}>{data.statusPill.label}</span>
        </div>
      )}

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

  // 收集所有箭头的配置
  const arrows = [];
  Object.values(DEMO_CANVAS_SECTIONS).flat().forEach(card => {
    if (card.next) {
      const nextArr = Array.isArray(card.next) ? card.next : [card.next];
      nextArr.forEach(targetId => {
        arrows.push({
          start: card.id,
          end: targetId,
          color: '#cbd5e1',
          strokeWidth: 2,
          path: 'smooth',
          showHead: true,
          headSize: 4
        });
      });
    }
  });

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
                  {DEMO_CANVAS_SECTIONS.evidence.map(card => <CanvasCard key={card.id} data={card} />)}
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
                  {DEMO_CANVAS_SECTIONS.problems.map(card => <CanvasCard key={card.id} data={card} />)}
                </div>
              </div>
              <div className="module-cluster">
                <div className="cluster-title">待澄清问题</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.clarify.map(card => <CanvasCard key={card.id} data={card} />)}
                </div>
              </div>
            </div>
          </div>

          <div className="canvas-lane">
            <div className="lane-header">
              <h3>3. 方案规划</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">决策确认</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.rules.map(card => <CanvasCard key={card.id} data={card} />)}
                </div>
              </div>
            </div>
          </div>

          <div className="canvas-lane">
            <div className="lane-header">
              <h3>4. 落地执行</h3>
            </div>
            <div className="lane-content">
              <div className="module-cluster">
                <div className="cluster-title">迭代计划</div>
                <div className="cluster-cards">
                  {DEMO_CANVAS_SECTIONS.planning.map(card => <CanvasCard key={card.id} data={card} />)}
                </div>
              </div>
            </div>
          </div>

          {/* 渲染所有箭头 */}
          {arrows.map((arr, i) => <CustomArrow key={i} start={arr.start} end={arr.end} transform={transform} />)}

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
