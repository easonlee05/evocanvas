import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Search, 
  LayoutGrid, 
  List as ListIcon, 
  Star, 
  MoreHorizontal, 
  Trash2, 
  Edit3, 
  ExternalLink,
  Plus,
  ChevronDown,
  Check
} from 'lucide-react';
import { apiGet, apiPatch } from '../../api';
import { buildRecentProjectCard } from './recentProjectsView';
import './recent-projects.css';

/**
 * 状态映射中文标签
 */
const STATUS_BADGES = {
  confirmed: { text: '已确认交接', color: 'status-confirmed' },
  draft: { text: '交接草稿', color: 'status-draft' },
  not_ready: { text: '待收敛', color: 'status-not-ready' }
};

/**
 * 真实画布内容微缩缩略图生成组件
 * 基于工作区实际包含的卡片数据（按列 Discovery / Define / Handoff 聚合渲染迷你节点）
 */
function MiniCanvasThumbnail({ cards, seed }) {
  // 极致的空值与类型防御，防止 cards 为 null/undefined 时调用 filter 报错导致 React 页面白屏挂掉
  const safeCards = Array.isArray(cards) ? cards : [];
  
  const discoveryCards = safeCards.filter(c => c && (c.stage === 'discovery'));
  const defineCards = safeCards.filter(c => c && (c.stage === 'define' || c.stage === 'definition'));
  const handoffCards = safeCards.filter(c => c && (c.stage === 'handoff'));

  const hasCards = safeCards.length > 0;

  const getNodeColor = (kind) => {
    switch (kind) {
      case 'evidence': 
        return '#5c5cf0'; // 蓝色
      case 'problem':
      case 'clarification': 
        return '#f59e0b'; // 橙黄色
      case 'constraint': 
        return '#a855f7'; // 紫色
      case 'decision': 
        return '#ef4444'; // 红色
      case 'handoff': 
        return '#10b981'; // 绿色
      default: 
        return '#94a3b8';
    }
  };

  if (!hasCards) {
    return (
      <div className="mini-canvas-thumbnail">
        <svg className="thumbnail-svg" width="100%" height="100%" viewBox="0 0 260 140" preserveAspectRatio="xMidYMid meet">
          <radialGradient id={`glow-empty-${seed}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(92, 92, 240, 0.05)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
          <rect width="260" height="140" fill={`url(#glow-empty-${seed})`} pointerEvents="none" />
          
          <g opacity="0.3">
            <path d="M 50 70 L 130 70 L 210 70" fill="none" stroke="var(--text-tertiary, #94a3b8)" strokeWidth="1.5" strokeDasharray="3,3" />
            <rect x="32" y="58" width="36" height="24" rx="4" fill="none" stroke="var(--text-tertiary, #94a3b8)" strokeWidth="1.5" strokeDasharray="3,3" />
            <rect x="112" y="58" width="36" height="24" rx="4" fill="none" stroke="var(--text-tertiary, #94a3b8)" strokeWidth="1.5" strokeDasharray="3,3" />
            <rect x="192" y="58" width="36" height="24" rx="4" fill="none" stroke="var(--text-tertiary, #94a3b8)" strokeWidth="1.5" strokeDasharray="3,3" />
          </g>
        </svg>
      </div>
    );
  }

  const getCoords = (cardsList, xCenter) => {
    if (!Array.isArray(cardsList)) return [];
    const list = cardsList.filter(Boolean).slice(0, 3);
    const len = list.length;
    if (len === 1) return [{ x: xCenter, y: 70, kind: list[0].kind }];
    if (len === 2) return [
      { x: xCenter, y: 45, kind: list[0].kind },
      { x: xCenter, y: 95, kind: list[1].kind }
    ];
    if (len >= 3) return [
      { x: xCenter, y: 30, kind: list[0].kind },
      { x: xCenter, y: 70, kind: list[1].kind },
      { x: xCenter, y: 110, kind: list[2].kind }
    ];
    return [];
  };

  const discoveryNodes = getCoords(discoveryCards, 50);
  const defineNodes = getCoords(defineCards, 130);
  const handoffNodes = getCoords(handoffCards, 210);

  const getAverageY = (nodes) => {
    if (!nodes || !nodes.length) return null;
    const validNodes = nodes.filter(n => n && typeof n.y === 'number' && !isNaN(n.y));
    if (!validNodes.length) return null;
    return validNodes.reduce((sum, n) => sum + n.y, 0) / validNodes.length;
  };

  const y1 = getAverageY(discoveryNodes);
  const y2 = getAverageY(defineNodes);
  const y3 = getAverageY(handoffNodes);

  let pathD = '';
  if (y1 !== null && y2 !== null && y3 !== null) {
    pathD = `M 50 ${y1} L 130 ${y2} L 210 ${y3}`;
  } else if (y1 !== null && y2 !== null) {
    pathD = `M 50 ${y1} L 130 ${y2}`;
  } else if (y2 !== null && y3 !== null) {
    pathD = `M 130 ${y2} L 210 ${y3}`;
  } else if (y1 !== null && y3 !== null) {
    pathD = `M 50 ${y1} L 210 ${y3}`;
  }

  const allNodes = [...discoveryNodes, ...defineNodes, ...handoffNodes];

  return (
    <div className="mini-canvas-thumbnail">
      <svg className="thumbnail-svg" width="100%" height="100%" viewBox="0 0 260 140" preserveAspectRatio="xMidYMid meet">
        <radialGradient id={`glow-${seed}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(92, 92, 240, 0.05)" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <rect width="260" height="140" fill={`url(#glow-${seed})`} pointerEvents="none" />

        {pathD && (
          <path 
            d={pathD} 
            fill="none" 
            stroke="var(--text-tertiary, #94a3b8)" 
            strokeWidth="1.5" 
            strokeDasharray="4,4" 
            opacity="0.3"
          />
        )}
        
        {allNodes.map((node, i) => (
          <g key={i} transform={`translate(${node.x - 18}, ${node.y - 12})`} className="mini-node">
            <rect width="36" height="24" rx="4" fill={getNodeColor(node.kind)} opacity="0.9" />
            <line x1="6" y1="8" x2="30" y2="8" stroke="#fff" strokeWidth="1.5" opacity="0.6" />
            <line x1="6" y1="16" x2="20" y2="16" stroke="#fff" strokeWidth="1.5" opacity="0.4" />
          </g>
        ))}
      </svg>
    </div>
  );
}

export default function RecentProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('recents'); // 'recents' | 'my-canvases'
  const [sortBy, setSortBy] = useState('recent'); // 'recent' | 'alphabetical'
  const [viewMode, setViewMode] = useState(() => {
    return localStorage.getItem('evocanvas_view_mode') || 'grid';
  });
  
  // 运行期崩溃状态捕捉（防白屏设计）
  const [errorBoundary, setErrorBoundary] = useState(null);

  // 本地持久化交互状态
  const [starredIds, setStarredIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('evocanvas_starred_ids') || '[]');
    } catch {
      return [];
    }
  });
  const [deletedIds, setDeletedIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('evocanvas_deleted_ids') || '[]');
    } catch {
      return [];
    }
  });

  const [activeMenuId, setActiveMenuId] = useState(null);
  const [isSortOpen, setIsSortOpen] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const fetchWorkspaces = async () => {
    setLoading(true);
    const data = await apiGet('/api/canvas/workspaces', { items: [] });
    console.log('[EvoCanvas Debug] Loaded raw workspaces data:', data);
    if (data && data.items) {
      setProjects(data.items);
    }
    setLoading(false);
  };

  const handleToggleView = (mode) => {
    setViewMode(mode);
    localStorage.setItem('evocanvas_view_mode', mode);
  };

  const handleToggleStar = (id, e) => {
    e.stopPropagation();
    const updated = starredIds.includes(id) 
      ? starredIds.filter(x => x !== id) 
      : [...starredIds, id];
    setStarredIds(updated);
    localStorage.setItem('evocanvas_starred_ids', JSON.stringify(updated));
  };

  const handleDelete = (id, title, e) => {
    e.stopPropagation();
    setActiveMenuId(null);
    if (window.confirm(`确定要删除项目 "${title}" 吗？此操作不可撤销。`)) {
      const updated = [...deletedIds, id];
      setDeletedIds(updated);
      localStorage.setItem('evocanvas_deleted_ids', JSON.stringify(updated));
    }
  };

  const handleRename = async (id, currentTitle, e) => {
    e.stopPropagation();
    setActiveMenuId(null);
    const newTitle = window.prompt('请输入新的项目名称：', currentTitle);
    if (newTitle !== null && newTitle.trim() !== '') {
      const result = await apiPatch(`/api/canvas/workspaces/${id}`, { title: newTitle.trim() });
      if (result && result.title) {
        setProjects(prev => prev.map(p => 
          p.workspace_id === id ? { ...p, title: result.title } : p
        ));
      } else {
        alert('重命名失败，请确保后端服务正常运行。');
      }
    }
  };

  // 错误渲染展示
  if (errorBoundary) {
    return (
      <div style={{ padding: '40px', color: '#ef4444', background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: '8px', margin: '20px' }}>
        <h3>页面发生运行期崩溃 (Render Crash)</h3>
        <p>错误原因：{errorBoundary.message}</p>
        <pre style={{ fontSize: '12px', whiteSpace: 'pre-wrap', background: '#fff', padding: '10px', borderRadius: '4px', border: '1px solid #eee' }}>{errorBoundary.stack}</pre>
        <button 
          onClick={() => {
            localStorage.clear();
            setErrorBoundary(null);
            window.location.reload();
          }} 
          className="empty-action-btn"
          style={{ background: '#ef4444', color: '#fff', border: 'none', height: '36px', borderRadius: '4px', padding: '0 15px', cursor: 'pointer' }}
        >
          清空本地缓存并重试
        </button>
      </div>
    );
  }

  try {
    const safeProjects = Array.isArray(projects) ? projects.filter(Boolean) : [];
    const formattedProjects = safeProjects.map(item => {
      const card = buildRecentProjectCard(item);
      return {
        ...card,
        rawUpdatedAt: item.updated_at || item.created_at || '',
        rawStatus: item.handoff_status || 'not_ready',
        isStarred: starredIds.includes(item.workspace_id),
        cards: Array.isArray(item.cards) ? item.cards : []
      };
    });

    // 滤除被本地删除的项目
    let displayProjects = formattedProjects.filter(p => p && !deletedIds.includes(p.workspaceId));

    // 搜索过滤
    if (searchQuery.trim()) {
      displayProjects = displayProjects.filter(p => 
        p && p.title && p.title.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // 排序
    if (sortBy === 'alphabetical') {
      displayProjects.sort((a, b) => {
        const titleA = a?.title || '';
        const titleB = b?.title || '';
        return titleA.localeCompare(titleB, 'zh-CN');
      });
    } else {
      displayProjects.sort((a, b) => {
        const timeA = new Date(a?.rawUpdatedAt || 0);
        const timeB = new Date(b?.rawUpdatedAt || 0);
        return timeB - timeA;
      });
    }

    console.log(
      '[EvoCanvas Debug] Total loaded projects:', projects.length, 
      'Displaying projects:', displayProjects.length, 
      'Locally deleted IDs:', deletedIds
    );

    return (
      <div className="recent-projects-page" onClick={() => { setActiveMenuId(null); setIsSortOpen(false); }}>
        <div className="recent-header">
          <h1 className="recent-page-title">我的工作区</h1>
          <button className="new-project-btn" onClick={() => navigate('/')}>
            <Plus size={16} />
            <span>新建收敛画布</span>
          </button>
        </div>

        <div className="recent-toolbar">
          <div className="recent-tabs">
            <button 
              className={`tab-item ${activeTab === 'recents' ? 'active' : ''}`}
              onClick={() => setActiveTab('recents')}
            >
              最近浏览过
            </button>
            <button 
              className={`tab-item ${activeTab === 'my-canvases' ? 'active' : ''}`}
              onClick={() => setActiveTab('my-canvases')}
            >
              我的画布
            </button>
          </div>

          <div className="recent-controls">
            <div className="search-wrapper">
              <Search size={14} className="search-icon" />
              <input 
                type="text" 
                placeholder="搜索项目名称..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
            </div>

            <div className="sort-wrapper" onClick={(e) => e.stopPropagation()}>
              <button 
                className={`sort-trigger ${isSortOpen ? 'active' : ''}`}
                onClick={() => setIsSortOpen(!isSortOpen)}
              >
                <span>{sortBy === 'recent' ? '最近浏览' : '按字母顺序'}</span>
                <ChevronDown size={12} className="chevron" />
              </button>
              {isSortOpen && (
                <div className="sort-dropdown">
                  <div 
                    className={`sort-item ${sortBy === 'recent' ? 'selected' : ''}`}
                    onClick={() => { setSortBy('recent'); setIsSortOpen(false); }}
                  >
                    <span>最近浏览</span>
                    {sortBy === 'recent' && <Check size={12} />}
                  </div>
                  <div 
                    className={`sort-item ${sortBy === 'alphabetical' ? 'selected' : ''}`}
                    onClick={() => { setSortBy('alphabetical'); setIsSortOpen(false); }}
                  >
                    <span>按字母顺序</span>
                    {sortBy === 'alphabetical' && <Check size={12} />}
                  </div>
                </div>
              )}
            </div>

            <div className="view-toggle">
              <button 
                className={`toggle-btn ${viewMode === 'grid' ? 'active' : ''}`}
                onClick={() => handleToggleView('grid')}
                title="网格视图"
              >
                <LayoutGrid size={15} />
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
                onClick={() => handleToggleView('list')}
                title="列表视图"
              >
                <ListIcon size={15} />
              </button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="recent-grid skeleton-grid">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="recent-card skeleton-card">
                <div className="skeleton-preview placeholder-shimmer" />
                <div className="skeleton-info">
                  <div className="skeleton-line title-line placeholder-shimmer" />
                  <div className="skeleton-line time-line placeholder-shimmer" />
                </div>
              </div>
            ))}
          </div>
        ) : displayProjects.length === 0 ? (
          <div className="recent-empty">
            <div className="empty-graphic">🎨</div>
            <h3>暂无相关的项目画布</h3>
            
            {projects.length > 0 && (
              <div style={{ marginTop: '12px', marginBottom: '24px' }}>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary, #64748b)', margin: '0 0 12px 0' }}>
                  检测到本地存在被隐藏/删除的画布记录，你可以一键恢复它们。
                </p>
                <button 
                  onClick={() => {
                    localStorage.removeItem('evocanvas_deleted_ids');
                    setDeletedIds([]);
                  }}
                  className="empty-action-btn"
                  style={{ 
                    background: 'var(--bg-active, #f1f5f9)', 
                    color: 'var(--text-primary, #0f172a)', 
                    border: '1px solid var(--border, #e2e8f0)',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                  }}
                >
                  恢复所有被删项目
                </button>
              </div>
            )}
            
            <button className="empty-action-btn" onClick={() => navigate('/')}>
              立即开始
            </button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="recent-grid">
            {displayProjects.map((project) => {
              if (!project) return null;
              return (
                <div 
                  key={project.workspaceId} 
                  className="recent-card"
                  onClick={() => navigate(`/workspace/${project.workspaceId}`)}
                >
                  <div className="recent-card-preview">
                    <div className="figma-grid-overlay" />
                    <MiniCanvasThumbnail cards={project.cards} seed={project.workspaceId} />

                    {STATUS_BADGES[project.rawStatus] && (
                      <span className={`status-badge ${STATUS_BADGES[project.rawStatus].color}`}>
                        {STATUS_BADGES[project.rawStatus].text}
                      </span>
                    )}

                    <button 
                      className={`card-star-btn ${project.isStarred ? 'starred' : ''}`}
                      onClick={(e) => handleToggleStar(project.workspaceId, e)}
                    >
                      <Star size={14} fill={project.isStarred ? 'var(--clr-amber, #f59e0b)' : 'none'} />
                    </button>

                    <div className="card-menu-wrapper" onClick={(e) => e.stopPropagation()}>
                      <button 
                        className="card-menu-btn"
                        onClick={() => setActiveMenuId(activeMenuId === project.workspaceId ? null : project.workspaceId)}
                      >
                        <MoreHorizontal size={14} />
                      </button>
                      {activeMenuId === project.workspaceId && (
                        <div className="card-dropdown-menu">
                          <button onClick={(e) => handleRename(project.workspaceId, project.title, e)}>
                            <Edit3 size={12} />
                            <span>重命名</span>
                          </button>
                          <button 
                            onClick={(e) => handleDelete(project.workspaceId, project.title, e)}
                            className="menu-danger"
                          >
                            <Trash2 size={12} />
                            <span>删除</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="recent-card-info">
                    <div className="project-icon-box">
                      <div className="mini-icon-square">
                        <div className="inner-dot" />
                      </div>
                    </div>
                    <div className="project-detail">
                      <h4 className="project-title" title={project.title}>{project.title}</h4>
                      <span className="project-time">{project.updatedLabel}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="recent-list-container">
            <table className="recent-list-table">
              <thead>
                <tr>
                  <th width="45%">名称</th>
                  <th width="20%">最后修改</th>
                  <th width="20%">收敛状态</th>
                  <th width="15%" style={{ textAlign: 'right' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {displayProjects.map((project) => {
                  if (!project) return null;
                  return (
                    <tr 
                      key={project.workspaceId}
                      onClick={() => navigate(`/workspace/${project.workspaceId}`)}
                      className="recent-list-row"
                    >
                      <td>
                        <div className="list-name-cell">
                          <button 
                            className={`list-star-btn ${project.isStarred ? 'starred' : ''}`}
                            onClick={(e) => handleToggleStar(project.workspaceId, e)}
                          >
                            <Star size={13} fill={project.isStarred ? 'var(--clr-amber, #f59e0b)' : 'none'} />
                          </button>
                          <div className="mini-icon-square">
                            <div className="inner-dot" />
                          </div>
                          <span className="list-project-title" title={project.title}>
                            {project.title}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="list-project-time">{project.updatedLabel}</span>
                      </td>
                      <td>
                        {STATUS_BADGES[project.rawStatus] && (
                          <span className={`status-badge-inline ${STATUS_BADGES[project.rawStatus].color}`}>
                            {STATUS_BADGES[project.rawStatus].text}
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="list-action-cell" onClick={(e) => e.stopPropagation()}>
                          <button 
                            onClick={(e) => handleRename(project.workspaceId, project.title, e)} 
                            title="重命名"
                            className="list-action-icon-btn"
                          >
                            <Edit3 size={12} />
                          </button>
                          <button 
                            onClick={(e) => handleDelete(project.workspaceId, project.title, e)} 
                            title="删除"
                            className="list-action-icon-btn list-danger"
                          >
                            <Trash2 size={12} />
                          </button>
                          <button 
                            onClick={() => navigate(`/workspace/${project.workspaceId}`)} 
                            title="打开"
                            className="list-action-icon-btn"
                          >
                            <ExternalLink size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  } catch (err) {
    setErrorBoundary(err);
    return null;
  }
}
