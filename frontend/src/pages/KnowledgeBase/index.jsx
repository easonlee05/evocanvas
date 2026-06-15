import React, { useEffect, useState, useRef } from 'react';
import { Search, Plus, FileText, Shield, Layout, X, Eye } from 'lucide-react';
import { apiGet, apiPost } from '../../api';
import './knowledge-base.css';

const tabs = ['全部', '文档', '规则', '模板'];
const typeMap = { doc: '文档', rule: '规则', template: '模板' };

const typeConfig = {
  doc:      { label: '文档',  icon: <FileText size={14} />, color: '#3b82f6' }, // 经典 Figma 亮蓝
  rule:     { label: '规则',  icon: <Shield size={14} />,   color: '#8b5cf6' }, // 霓虹紫
  template: { label: '模板',  icon: <Layout size={14} />,   color: '#f59e0b' }, // 亮橙
};

// 预设的依赖连接关系
const initialRelations = [
  { id: 'rel_1', source: 'kb_002', target: 'kb_001', label: '约束于' },
  { id: 'rel_2', source: 'kb_003', target: 'kb_001', label: '衍生自' }
];

export default function KnowledgeBase() {
  const [tab, setTab] = useState('全部');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState([]);
  const [relations, setRelations] = useState(initialRelations);
  const [positions, setPositions] = useState({});
  const [showModal, setShowModal] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNodeId, setHoveredNodeId] = useState(null);

  // Pan / Zoom 状态
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(0.85); // 初始略微缩放以展示全景
  
  const isDraggingCanvas = useRef(false);
  const startPan = useRef({ x: 0, y: 0 });
  
  // 实时力学模拟状态
  const draggingNodeId = useRef(null);
  const startNodePos = useRef({ x: 0, y: 0 });
  const startMousePos = useRef({ x: 0, y: 0 });
  const velocities = useRef({});

  const containerRef = useRef(null);

  // 1. 数据拉取与位置初始化
  useEffect(() => {
    apiGet('/api/knowledge').then(data => {
      const rawItems = data.items || [];
      const fetchedItems = rawItems.map(item => {
        let title = item.title;
        let desc = item.desc;
        
        // 映射旧文案为 EvoCanvas 新产品语义
        if (title === "PM-Agent 后端架构契约") {
          title = "EvoCanvas 协作与编译协议";
          desc = "定义 TaskDefinition 规格、Workspace 引擎及多源输入事件。";
        } else if (title === "Agent 必须通过 ToolPolicy 调用能力") {
          title = "EvoCanvas 编译防泄漏安全规则";
          desc = "限制编译引擎访问未经授权的外部系统，确立数据沙箱边界。";
        } else if (title === "PRD Markdown 输出模板") {
          title = "EvoCanvas PRD 交付物标准模板";
          desc = "规范编译输出的结构化交接物模板，包含目标、不确定性及动作设计。";
        }
        
        return { ...item, title, desc };
      });

      setItems(fetchedItems);
      
      // 读取坐标缓存
      let cachedPositions = {};
      try {
        const stored = localStorage.getItem('kb_node_positions_v2');
        if (stored) cachedPositions = JSON.parse(stored);
      } catch (e) {
        console.error(e);
      }

      // 初次加载时在画布中央散落
      const newPositions = { ...cachedPositions };
      fetchedItems.forEach((item, idx) => {
        if (!newPositions[item.id]) {
          const angle = (idx / Math.max(fetchedItems.length, 1)) * 2 * Math.PI;
          const radius = 120 + Math.random() * 80;
          newPositions[item.id] = {
            x: 400 + radius * Math.cos(angle),
            y: 260 + radius * Math.sin(angle)
          };
        }
      });
      setPositions(newPositions);
    }).catch(err => {
      console.error(err);
    });
  }, []);

  // 2. Obsidian 实时力导向排布算法 (Force-Directed Engine)
  useEffect(() => {
    if (items.length === 0) return;

    let animFrame;
    const tick = () => {
      setPositions(prev => {
        const next = { ...prev };
        const keys = Object.keys(next);

        // 初始化速度
        keys.forEach(id => {
          if (!velocities.current[id]) {
            velocities.current[id] = { vx: 0, vy: 0 };
          }
        });

        // A. 节点间排斥力 (Repulsion) - 距离近的节点弹开
        for (let i = 0; i < keys.length; i++) {
          for (let j = i + 1; j < keys.length; j++) {
            const id1 = keys[i];
            const id2 = keys[j];
            const p1 = next[id1];
            const p2 = next[id2];
            if (!p1 || !p2) continue;

            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const distSq = dx * dx + dy * dy || 1;
            const dist = Math.sqrt(distSq);

            // 斥力范围：180px
            if (dist < 180) {
              const force = (180 - dist) / dist * 0.35; // 斥力大小系数
              if (draggingNodeId.current !== id1) {
                velocities.current[id1].vx -= dx * force;
                velocities.current[id1].vy -= dy * force;
              }
              if (draggingNodeId.current !== id2) {
                velocities.current[id2].vx += dx * force;
                velocities.current[id2].vy += dy * force;
              }
            }
          }
        }

        // B. 连线拉力 (Attraction) - 关联节点向中心连线长度缩进
        relations.forEach(rel => {
          const p1 = next[rel.source];
          const p2 = next[rel.target];
          if (!p1 || !p2) return;

          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          // 理想连线距离为 110px
          const force = (dist - 110) / dist * 0.045; // 引力系数
          if (draggingNodeId.current !== rel.source) {
            velocities.current[rel.source].vx += dx * force;
            velocities.current[rel.source].vy += dy * force;
          }
          if (draggingNodeId.current !== rel.target) {
            velocities.current[rel.target].vx -= dx * force;
            velocities.current[rel.target].vy -= dy * force;
          }
        });

        // C. 中心重力 (Gravity) - 向画布中心聚拢，防止飞散
        const centerX = 400;
        const centerY = 260;
        keys.forEach(id => {
          if (draggingNodeId.current === id) return;
          const p = next[id];
          if (!p) return;
          const dx = centerX - p.x;
          const dy = centerY - p.y;
          velocities.current[id].vx += dx * 0.0035;
          velocities.current[id].vy += dy * 0.0035;
        });

        // D. 摩擦阻尼力 (Damping) - 衰减速度以保证稳定
        let hasMoved = false;
        keys.forEach(id => {
          if (draggingNodeId.current === id) return;
          const vel = velocities.current[id];
          vel.vx *= 0.82;
          vel.vy *= 0.82;
          
          if (Math.abs(vel.vx) > 0.05 || Math.abs(vel.vy) > 0.05) {
            next[id] = {
              x: next[id].x + vel.vx,
              y: next[id].y + vel.vy
            };
            hasMoved = true;
          }
        });

        if (hasMoved) {
          localStorage.setItem('kb_node_positions_v2', JSON.stringify(next));
          return next;
        }
        return prev;
      });

      animFrame = requestAnimationFrame(tick);
    };

    animFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrame);
  }, [items, relations]);

  // 3. 画布拖拽事件 (Pan)
  const handleCanvasMouseDown = (e) => {
    if (e.target.closest('circle') || draggingNodeId.current) return;
    isDraggingCanvas.current = true;
    startPan.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleCanvasMouseMove = (e) => {
    if (isDraggingCanvas.current) {
      setPan({
        x: e.clientX - startPan.current.x,
        y: e.clientY - startPan.current.y
      });
    } else if (draggingNodeId.current) {
      const dx = (e.clientX - startMousePos.current.x) / zoom;
      const dy = (e.clientY - startMousePos.current.y) / zoom;
      const nodeId = draggingNodeId.current;

      if (velocities.current[nodeId]) {
        velocities.current[nodeId].vx = 0;
        velocities.current[nodeId].vy = 0;
      }

      setPositions(prev => {
        const updated = {
          ...prev,
          [nodeId]: {
            x: startNodePos.current.x + dx,
            y: startNodePos.current.y + dy
          }
        };
        localStorage.setItem('kb_node_positions_v2', JSON.stringify(updated));
        return updated;
      });
    }
  };

  const handleCanvasMouseUp = () => {
    isDraggingCanvas.current = false;
    draggingNodeId.current = null;
  };

  // 4. 滚动缩放 (Zoom)
  const handleCanvasWheel = (e) => {
    e.preventDefault();
    const zoomFactor = 1.06;
    let newZoom = zoom;
    if (e.deltaY < 0) {
      newZoom = Math.min(zoom * zoomFactor, 2.5);
    } else {
      newZoom = Math.max(zoom / zoomFactor, 0.3);
    }
    setZoom(newZoom);
  };

  // 5. 双击/按钮自适应视角
  const handleResetView = () => {
    setPan({ x: 0, y: 0 });
    setZoom(0.85);
  };

  // 6. 节点按下拖拽与选中
  const handleNodeMouseDown = (e, nodeId) => {
    e.stopPropagation();
    draggingNodeId.current = nodeId;
    const pos = positions[nodeId] || { x: 400, y: 260 };
    startNodePos.current = { ...pos };
    startMousePos.current = { x: e.clientX, y: e.clientY };
    const node = items.find(i => i.id === nodeId);
    setSelectedNode(node);
  };

  // 7. 新建节点
  const handleCreate = async (newItem) => {
    try {
      const created = await apiPost('/api/knowledge', newItem);
      const savedItem = {
        ...created,
        id: created.id || `kb_${Math.random().toString(36).substr(2, 9)}`,
        updated: '刚刚',
        author: 'User'
      };

      setItems(prev => [savedItem, ...prev]);

      // 初始化新节点坐标
      setPositions(prev => {
        const angle = Math.random() * 2 * Math.PI;
        const radius = 100 + Math.random() * 80;
        const updated = {
          ...prev,
          [savedItem.id]: {
            x: 400 + radius * Math.cos(angle),
            y: 260 + radius * Math.sin(angle)
          }
        };
        localStorage.setItem('kb_node_positions_v2', JSON.stringify(updated));
        return updated;
      });

      // 建立连线关系
      if (newItem.relatedNodeId) {
        const newRelation = {
          id: `rel_${Date.now()}`,
          source: savedItem.id,
          target: newItem.relatedNodeId,
          label: newItem.relationType || '关联于'
        };
        setRelations(prev => [...prev, newRelation]);
      }

      setShowModal(false);
    } catch (err) {
      console.error(err);
    }
  };

  // 8. 抽屉内联动平移居中
  const handleFocusNode = (nodeId) => {
    const pos = positions[nodeId];
    if (pos && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const targetPanX = rect.width / 2 - pos.x * zoom;
      const targetPanY = rect.height / 2 - pos.y * zoom;
      setPan({ x: targetPanX, y: targetPanY });
      const node = items.find(i => i.id === nodeId);
      setSelectedNode(node);
    }
  };

  // 9. 检索逻辑
  const matchQuery = (node) => {
    if (!query) return true;
    return node.title.toLowerCase().includes(query.toLowerCase()) || 
           (node.desc && node.desc.toLowerCase().includes(query.toLowerCase()));
  };

  const matchTab = (node) => {
    if (tab === '全部') return true;
    return typeMap[node.type] === tab;
  };

  const getLinkCount = (nodeId) => {
    return relations.filter(r => r.source === nodeId || r.target === nodeId).length;
  };

  return (
    <div className="kb-page">
      {/* 顶部固定工具栏 */}
      <div className="kb-toolbar">
        <div className="kb-toolbar-left">
          <div className="kb-title-area">
            <h1 className="kb-title">EvoCanvas 知识库</h1>
            <p className="kb-subtitle">本地沉淀的规范文档、安全规制与模板的血缘依赖图谱</p>
          </div>
          <div className="kb-search-container">
            <Search size={13} className="kb-search-icon" />
            <input 
              placeholder="搜索知识节点..." 
              value={query} 
              onChange={e => setQuery(e.target.value)} 
            />
          </div>
        </div>

        <div className="kb-toolbar-right">
          <div className="kb-filter-tabs">
            {tabs.map(t => (
              <button 
                key={t} 
                className={`kb-tab-btn${tab === t ? ' active' : ''}`} 
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>

          <button className="kb-ctrl-btn" title="重置自适应视角" onClick={handleResetView}>
            <Eye size={13} />
          </button>

          <button className="kb-btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={12} />新建知识点
          </button>
        </div>
      </div>

      {/* SVG Canvas 主体区 */}
      <div 
        ref={containerRef}
        className="kb-canvas-container"
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleCanvasMouseMove}
        onMouseUp={handleCanvasMouseUp}
        onMouseLeave={handleCanvasMouseUp}
        onWheel={handleCanvasWheel}
      >
        <svg width="100%" height="100%" style={{ pointerEvents: 'none' }}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="15" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 2 L 10 5 L 0 8 z" />
            </marker>
          </defs>

          {/* SVG 平移与缩放核心群组 */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`} style={{ pointerEvents: 'auto' }}>
            
            {/* A. 绘制超细 Obsidian 直线连线 */}
            {relations.map(rel => {
              const p1 = positions[rel.source];
              const p2 = positions[rel.target];
              if (!p1 || !p2) return null;

              const sourceNode = items.find(i => i.id === rel.source);
              const targetNode = items.find(i => i.id === rel.target);
              
              const isSourceMatch = sourceNode && matchQuery(sourceNode) && matchTab(sourceNode);
              const isTargetMatch = targetNode && matchQuery(targetNode) && matchTab(targetNode);
              const isDimmed = !isSourceMatch || !isTargetMatch;

              const isSelectedRelation = selectedNode && (selectedNode.id === rel.source || selectedNode.id === rel.target);
              const isHoveredRelation = hoveredNodeId && (hoveredNodeId === rel.source || hoveredNodeId === rel.target);

              // 连线中点
              const midX = (p1.x + p2.x) / 2;
              const midY = (p1.y + p2.y) / 2;

              return (
                <g key={rel.id} style={{ opacity: isDimmed ? 0.12 : 1, transition: 'opacity 0.2s' }}>
                  <line 
                    x1={p1.x} 
                    y1={p1.y} 
                    x2={p2.x} 
                    y2={p2.y} 
                    stroke={isSelectedRelation || isHoveredRelation ? "#2563eb" : "#e2e8f0"} 
                    strokeWidth={isSelectedRelation || isHoveredRelation ? 1.6 : 1}
                    className="relation-path"
                    markerEnd="url(#arrow)"
                  />
                  {/* 在 Hover 或选中时才在连线中点渲染关系文本，防止堆叠 */}
                  {(isSelectedRelation || isHoveredRelation) && (
                    <g>
                      <rect 
                        x={midX - 22} 
                        y={midY - 8} 
                        width={44} 
                        height={16} 
                        className="relation-text-bg" 
                      />
                      <text 
                        x={midX} 
                        y={midY + 3} 
                        className="relation-text"
                      >
                        {rel.label}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* B. 绘制 Obsidian 极小节点 */}
            {items.map(node => {
              const pos = positions[node.id];
              if (!pos) return null;

              const isMatch = matchQuery(node) && matchTab(node);
              const isDimmed = !isMatch;

              const tc = typeConfig[node.type] || typeConfig.doc;
              const isNodeSelected = selectedNode?.id === node.id;
              const isHovered = hoveredNodeId === node.id;

              return (
                <g 
                  key={node.id} 
                  transform={`translate(${pos.x}, ${pos.y})`}
                  style={{ 
                    opacity: isDimmed ? 0.2 : 1, 
                    transition: 'opacity 0.2s', 
                    cursor: 'grab' 
                  }}
                  onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                >
                  {/* 节点外层隐形高灵敏 Hover 判定区 */}
                  <circle r={18} fill="transparent" style={{ pointerEvents: 'auto' }} />
                  
                  {/* 核心圆点 (Obsidian风格) */}
                  <circle 
                    r={isNodeSelected ? 6.5 : (isHovered ? 5.5 : 4)} 
                    fill={tc.color} 
                    stroke={isNodeSelected ? "#0f172a" : "rgba(255,255,255,0.9)"}
                    strokeWidth={isNodeSelected ? 2.5 : 1}
                    style={{ transition: 'r 0.15s, stroke-width 0.15s', pointerEvents: 'none' }}
                  />

                  {/* 节点名字标签，支持智能渐隐避让 */}
                  {(zoom > 0.65 || isHovered || isNodeSelected) && (
                    <text
                      x={10}
                      y={3.5}
                      fontSize="10.5px"
                      fill={isNodeSelected ? "#0f172a" : (isHovered ? "#1e293b" : "#475569")}
                      fontWeight={isNodeSelected || isHovered ? "600" : "400"}
                      style={{ pointerEvents: 'none', userSelect: 'none', transition: 'fill 0.15s' }}
                    >
                      {node.title}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* C. 右侧详情预览抽屉 (100% 贴右贴底高度) */}
      {selectedNode && (
        <div className="kb-details-drawer">
          <div className="drawer-header">
            <div className="drawer-title-area">
              <span style={{ color: typeConfig[selectedNode.type]?.color, display: 'flex', alignItems: 'center' }}>
                {typeConfig[selectedNode.type]?.icon}
              </span>
              <span className="kb-title" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {selectedNode.title}
              </span>
            </div>
            <button className="drawer-close" onClick={() => setSelectedNode(null)}>
              <X size={14} />
            </button>
          </div>

          <div className="drawer-body">
            <div className="drawer-section">
              <div className="drawer-label">分类</div>
              <div className="drawer-value">{typeMap[selectedNode.type]}</div>
            </div>

            <div className="drawer-section">
              <div className="drawer-label">规范详述</div>
              <div className="drawer-value">{selectedNode.desc || '尚无描述内容'}</div>
            </div>

            <div className="drawer-section">
              <div className="drawer-label">关联标签</div>
              <div className="drawer-tags">
                {selectedNode.tags && selectedNode.tags.length > 0 ? (
                  selectedNode.tags.map((tag, i) => (
                    <span key={i} className="drawer-tag">{tag}</span>
                  ))
                ) : (
                  <span className="drawer-value" style={{ fontSize: '11px', color: '#94a3b8' }}>无标签</span>
                )}
              </div>
            </div>

            <div className="drawer-section">
              <div className="drawer-label">血缘关联拓扑</div>
              <div className="drawer-relations-list">
                {relations.filter(r => r.source === selectedNode.id || r.target === selectedNode.id).length > 0 ? (
                  relations.filter(r => r.source === selectedNode.id || r.target === selectedNode.id).map(r => {
                    const otherNodeId = r.source === selectedNode.id ? r.target : r.source;
                    const otherNode = items.find(i => i.id === otherNodeId);
                    return (
                      <div 
                        key={r.id} 
                        className="drawer-relation-item"
                        onClick={() => handleFocusNode(otherNodeId)}
                      >
                        <span className="drawer-value" style={{ fontSize: '11.5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
                          {otherNode ? otherNode.title : '未知节点'}
                        </span>
                        <span className="drawer-relation-type">{r.label}</span>
                      </div>
                    );
                  })
                ) : (
                  <span className="drawer-value" style={{ fontSize: '11px', color: '#94a3b8' }}>当前节点为独立经验点</span>
                )}
              </div>
            </div>

            <div className="drawer-section">
              <div className="drawer-label">最后更新</div>
              <div className="drawer-value" style={{ fontSize: '11px', color: '#64748b' }}>
                由 {selectedNode.author || 'User'} 提交于 {selectedNode.updated || '刚刚'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* D. 新建条目弹窗模态框 */}
      {showModal && (
        <NewItemModal 
          items={items}
          onClose={() => setShowModal(false)} 
          onCreate={handleCreate} 
        />
      )}
    </div>
  );
}

function NewItemModal({ items, onClose, onCreate }) {
  const [type, setType] = useState('doc');
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [tags, setTags] = useState('');
  
  const [relatedNodeId, setRelatedNodeId] = useState('');
  const [relationType, setRelationType] = useState('衍生自');

  const handleSubmit = () => {
    if (!title.trim()) return;
    onCreate({
      type,
      title: title.trim(),
      desc: desc.trim(),
      tags: tags.split(/[,，]/).map(t => t.trim()).filter(Boolean),
      relatedNodeId: relatedNodeId || null,
      relationType
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ width: '400px', padding: '16px', boxSizing: 'border-box' }}>
        <div className="drawer-header" style={{ padding: '0 0 10px 0', marginBottom: '12px', borderBottom: '1px solid rgba(0, 0, 0, 0.05)' }}>
          <span className="kb-title" style={{ fontSize: '13px' }}>新建知识图谱节点</span>
          <button className="drawer-close" onClick={onClose}><X size={14} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* 类型 */}
          <div>
            <label className="drawer-label">类型</label>
            <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
              {Object.entries(typeConfig).map(([key, cfg]) => (
                <button
                  key={key}
                  className={`kb-tab-btn${type === key ? ' active' : ''}`}
                  style={{ flexGrow: 1, border: '1px solid rgba(0,0,0,0.06)', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  onClick={() => setType(key)}
                >
                  {cfg.label}
                </button>
              ))}
            </div>
          </div>

          {/* 标题 */}
          <div>
            <label className="drawer-label">标题</label>
            <input
              style={{ width: '100%', height: '28px', marginTop: '4px', background: '#fff', border: '1px solid rgba(0, 0, 0, 0.08)', borderRadius: '6px', color: '#0f172a', padding: '0 8px', boxSizing: 'border-box', outline: 'none', fontSize: '11.5px' }}
              placeholder="输入标题..."
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
          </div>

          {/* 描述 */}
          <div>
            <label className="drawer-label">描述</label>
            <textarea
              style={{ width: '100%', marginTop: '4px', background: '#fff', border: '1px solid rgba(0, 0, 0, 0.08)', borderRadius: '6px', color: '#0f172a', padding: '6px 8px', boxSizing: 'border-box', minHeight: '52px', outline: 'none', resize: 'vertical', fontSize: '11.5px', lineHeight: '1.4' }}
              placeholder="简要描述这条知识的含义与用处..."
              value={desc}
              onChange={e => setDesc(e.target.value)}
            />
          </div>

          {/* 标签 */}
          <div>
            <label className="drawer-label">标签（以逗号分隔）</label>
            <input
              style={{ width: '100%', height: '28px', marginTop: '4px', background: '#fff', border: '1px solid rgba(0, 0, 0, 0.08)', borderRadius: '6px', color: '#0f172a', padding: '0 8px', boxSizing: 'border-box', outline: 'none', fontSize: '11.5px' }}
              placeholder="例如：规范, 安全, 计费"
              value={tags}
              onChange={e => setTags(e.target.value)}
            />
          </div>

          {/* 关联血缘 */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <div style={{ flexGrow: 1 }}>
              <label className="drawer-label">关联到已有节点</label>
              <select
                style={{ width: '100%', height: '28px', marginTop: '4px', background: '#fff', border: '1px solid rgba(0, 0, 0, 0.08)', borderRadius: '6px', color: '#0f172a', padding: '0 4px', outline: 'none', fontSize: '11.5px' }}
                value={relatedNodeId}
                onChange={e => setRelatedNodeId(e.target.value)}
              >
                <option value="">-- 不进行关联 --</option>
                {items.map(i => (
                  <option key={i.id} value={i.id}>{i.title}</option>
                ))}
              </select>
            </div>
            
            <div style={{ width: '100px' }}>
              <label className="drawer-label">关系类型</label>
              <select
                style={{ width: '100%', height: '28px', marginTop: '4px', background: '#fff', border: '1px solid rgba(0, 0, 0, 0.08)', borderRadius: '6px', color: '#0f172a', padding: '0 4px', outline: 'none', fontSize: '11.5px' }}
                value={relationType}
                onChange={e => setRelationType(e.target.value)}
                disabled={!relatedNodeId}
              >
                <option value="衍生自">衍生自</option>
                <option value="约束于">约束于</option>
                <option value="关联于">关联于</option>
                <option value="阻塞">阻塞</option>
              </select>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
          <button className="kb-tab-btn" onClick={onClose}>取消</button>
          <button 
            className="kb-btn-primary" 
            onClick={handleSubmit} 
            disabled={!title.trim()}
          >
            确认创建
          </button>
        </div>
      </div>
    </div>
  );
}
