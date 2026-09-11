/**
 * @file LandingPage.jsx
 * @description EvoCanvas 起始页。提供对话式输入入口，让 PM 用自然语言、
 * 多源材料和上下文片段启动一张新的需求收敛工作面。
 */

import React, { useEffect, useState, useRef } from 'react';
import { ArrowUp, Zap, Search, Database, Paperclip, MoreHorizontal, ArrowRight, Loader, Loader2, ChevronDown, Check, Plus, AlertCircle, X, Layers } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiPostWithStatus, apiUpload } from '../../api';
import { getSelectedModel, readConfiguredModel, readModelList } from '../../modelConfig';
import './landing-page.css';

/**
 * 快捷推荐引导 prompt 列表
 * @type {Array<{icon: string, label: string}>}
 */
const suggestions = [
  { icon: '🧩', label: '我刚接到一个新需求，先帮我把当前已知信息和待澄清问题整理出来' },
  { icon: '📝', label: '这里有一段会议纪要，帮我提取冲突点、约束和待决策事项' },
  { icon: '🔎', label: '我想确认这个需求现在是否已经足够收敛到可以交接给 AI 继续推进' },
];

/**
 * 辅助功能片配置列表（知识输入与附件补充）
 * @type {Array<{id: string, icon: React.ReactNode, label: string}>}
 */
const chips = [
  { id: 'context', icon: <Search size={13} />, label: '上下文' },
  { id: 'notes', icon: <Database size={13} />, label: '笔记' },
  { id: 'attachment', icon: <Paperclip size={13} />, label: '附件' },
];

/**
 * 文件卡片组件 (极简展示)
 */
const FileCard = ({ file, onRemove }) => {
  const extMatch = file.name.match(/\.([^.]+)$/);
  const ext = extMatch ? extMatch[1].toLowerCase() : 'file';
  
  const formatSize = (bytes) => {
    if (!bytes) return '未知大小';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  let iconBg = '#94a3b8';
  let iconText = 'FILE';
  let typeLabel = '文件';
  
  if (['doc', 'docx'].includes(ext)) {
    iconBg = '#2563eb';
    iconText = 'W';
    typeLabel = '文档';
  } else if (['xls', 'xlsx'].includes(ext)) {
    iconBg = '#16a34a';
    iconText = 'X';
    typeLabel = '表格';
  } else if (['ppt', 'pptx'].includes(ext)) {
    iconBg = '#ea580c';
    iconText = 'P';
    typeLabel = '演示文稿';
  } else if (ext === 'pdf') {
    iconBg = '#dc2626';
    iconText = 'PDF';
    typeLabel = 'PDF文档';
  } else if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) {
    iconBg = '#0d9488';
    iconText = 'IMG';
    typeLabel = '图片';
  } else if (['txt', 'md', 'json', 'csv'].includes(ext)) {
    iconBg = '#4b5563';
    iconText = ext.toUpperCase();
    typeLabel = '文本';
  } else if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) {
    iconBg = '#7c3aed';
    iconText = 'ZIP';
    typeLabel = '压缩包';
  }

  return (
    <div className={`simple-file-card ${file.status}`}>
      <div className="file-card-icon" style={{ backgroundColor: iconBg }}>
        {file.status === 'uploading' ? (
          <Loader2 size={14} className="spin" style={{ color: '#ffffff' }} />
        ) : file.status === 'error' ? (
          <AlertCircle size={14} style={{ color: '#ffffff' }} />
        ) : (
          <span className="file-card-ext-label">{iconText}</span>
        )}
      </div>
      <div className="file-card-info">
        <div className="file-card-name" title={file.name}>
          {file.name}
        </div>
        <div className="file-card-meta">
          {typeLabel} · {formatSize(file.size || file.bytes)}
        </div>
      </div>
      <button className="file-card-remove-btn" onClick={onRemove} title="删除">
        <X size={12} strokeWidth={2.5} />
      </button>
    </div>
  );
};

/**
 * LandingPage 首页欢迎组件
 * @component
 */
export default function LandingPage() {
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('idle'); // 状态机状态: idle (空闲) | thinking (处理中/创建任务中) | done (完成)
  const [error, setError] = useState('');
  const [models, setModels] = useState(() => readModelList());
  const [model, setModel] = useState(() => getSelectedModel());
  const [isModelOpen, setIsModelOpen] = useState(false); // 模型下拉框的展示状态
  const [uploadedMaterials, setUploadedMaterials] = useState([]);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const navigate = useNavigate();

  // 副作用：监控输入内容 (value) 变化，使多行输入框 (textarea) 高度随内容自适应伸缩，最大高度限制在 220px
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
    // 若在 thinking 状态，将滚动条重置回顶部
    if (status === 'thinking') textarea.scrollTop = 0;
  }, [value, status]);

  // 设置页保存模型目录后，首页下拉框无需刷新即可同步。
  useEffect(() => {
    const syncModelCatalog = () => {
      const nextModels = readModelList();
      setModels(nextModels);
      setModel(current => nextModels.some(item => item.id === current) ? getSelectedModel() : (nextModels[0]?.id || ''));
    };
    window.addEventListener('evocanvas:model-config-changed', syncModelCatalog);
    return () => window.removeEventListener('evocanvas:model-config-changed', syncModelCatalog);
  }, []);

  /**
   * 附件上传处理函数
   * @param {React.ChangeEvent<HTMLInputElement>} e - 文件输入框变更事件
   */
  const handleUpload = async (e) => {
    const picked = Array.from(e.target.files);
    e.target.value = ''; // 清空以允许重复上传同名文件
    for (const file of picked) {
      const tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      setUploadedMaterials(prev => [...prev, {
        id: tempId,
        name: file.name,
        status: 'uploading'
      }]);

      try {
        const res = await apiUpload('/api/materials', file, null);
        if (res && res.material_id) {
          setUploadedMaterials(prev => prev.map(m =>
            m.id === tempId
              ? { ...m, status: 'success', material_id: res.material_id }
              : m
          ));
        } else {
          setUploadedMaterials(prev => prev.map(m =>
            m.id === tempId
              ? { ...m, status: 'error' }
              : m
          ));
        }
      } catch (err) {
        setUploadedMaterials(prev => prev.map(m =>
          m.id === tempId
            ? { ...m, status: 'error' }
            : m
        ));
      }
    }
  };

  /**
   * 发送/创建任务
   * @param {string} [text] - 可选的直接发送文本（用于点击 suggestions 时）
   */
  const handleSend = async (text) => {
    const msg = text || value;
    if (!msg.trim()) return;
    setValue(msg);
    setError('');
    setStatus('thinking');
    
    const materialIds = uploadedMaterials
      .filter(m => m.status === 'success' && m.material_id)
      .map(m => m.material_id);

    // 生成随机工作区 ID 并在后端初始化新工作区回合
    const workspaceId = 'ws_' + Math.random().toString(36).substring(2, 11);
    const response = await apiPostWithStatus(`/api/canvas/workspaces/${workspaceId}/messages`, {
      message: msg,
      selected_card_ids: [],
      material_ids: materialIds,
      model: model,
      llm_config: readConfiguredModel(model),
    });

    if (response.ok && response.data?.workspace_id) {
      // 创建成功后，将本地上传好的文件存入 localStorage 接力给工作台
      if (uploadedMaterials.length > 0) {
        localStorage.setItem(`evocanvas_materials_${response.data.workspace_id}`, JSON.stringify(uploadedMaterials));
      }
      // 重定向至工作台页面
      navigate(`/workspace/${response.data.workspace_id}`);
      return;
    }
    const detail = response.data?.message || response.data?.detail || response.data?.error_code;
    setError(response.status === 0
      ? '工作区初始化失败：无法连接后端 API，请确认本地后端已启动。'
      : `工作区初始化失败${detail ? `：${detail}` : `（HTTP ${response.status}）`}`);
    setStatus('idle');
  };

  /**
   * 键盘回车快捷键监听。
   * 支持 Enter 直接发送，Shift + Enter 换行。
   * @param {React.KeyboardEvent} e - 键盘事件对象
   */
  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault(); // 阻止默认的回车换行行为
      handleSend();
    }
  };

  return (
    <div className="landing">
      <div className="landing-inner">
        {/* 标语区域 */}
        <div className="landing-hero">
          <h1 className="landing-title">我们先把需求想清楚</h1>
        </div>

        {/* 核心输入区 */}
        <div className={`input-wrap${status === 'thinking' ? ' thinking' : ''}`}>
          <div className="input-box" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '8px' }}>
            {uploadedMaterials.length > 0 && (
              <div className="simple-attachments-list">
                {uploadedMaterials.map((m) => (
                  <FileCard 
                    key={m.id} 
                    file={m} 
                    onRemove={() => setUploadedMaterials(prev => prev.filter(item => item.id !== m.id))} 
                  />
                ))}
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', width: '100%' }}>
              {status === 'thinking' && (
                <Loader size={15} className="input-prefix-icon spinning" />
              )}
              <textarea
                ref={textareaRef}
                className="input-textarea"
                placeholder="输入会议纪要、聊天片段、想法或背景，我来帮你收敛成待澄清问题、约束和待决策项"
                value={value}
                onChange={e => setValue(e.target.value)}
                onKeyDown={handleKey}
                rows={1}
                disabled={status === 'thinking'}
              />
              <button
                className={`send-btn${value && status === 'idle' ? ' active' : ''}`}
                onClick={() => handleSend()}
                disabled={status === 'thinking'}
              >
                {status === 'thinking'
                  ? <span className="thinking-dots"><span /><span /><span /></span>
                  : <ArrowUp size={15} />
                }
              </button>
            </div>
          </div>
          {status === 'thinking' && (
            <div className="thinking-status">
              正在初始化 EvoCanvas 工作面…
            </div>
          )}
          {status === 'idle' && error && (
            <div className="input-error">
              {error}
            </div>
          )}
          {status === 'idle' && (
            <div className="input-footer">
              {/* 功能 Chip 渲染 */}
              {chips.map((c, i) => (
                <button 
                  key={i} 
                  className="chip"
                  onClick={c.id === 'attachment' ? () => fileInputRef.current?.click() : undefined}
                >
                  {c.icon}{c.label}
                </button>
              ))}
              {/* 隐藏的隐藏文件上传框 */}
              <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={handleUpload} />
              <div style={{ flex: 1 }} />
              
              {/* 模型选择下拉框结构 */}
              <div className="model-selector-wrap">
                <button 
                  className={`chip-ghost model-chip ${isModelOpen ? 'active' : ''}`}
                  onClick={() => setIsModelOpen(!isModelOpen)}
                >
                  {models.find(m => m.id === model)?.name || 'Default'}
                  <ChevronDown size={12} className={`model-chevron ${isModelOpen ? 'open' : ''}`} />
                </button>
                {isModelOpen && (
                  <>
                    {/* 点击背景区域关闭下拉框 */}
                    <div className="model-dropdown-backdrop" onClick={() => setIsModelOpen(false)} />
                    <div className="model-dropdown">
                      <div className="model-dropdown-header">协作模型</div>
                      {models.map(m => (
                        <div 
                          key={m.id} 
                          className={`model-item ${m.id === model ? 'selected' : ''}`}
                          onClick={() => { 
                            setModel(m.id); 
                            localStorage.setItem('evocanvas_selected_model', m.id);
                            setIsModelOpen(false); 
                          }}
                        >
                          <span className="model-name">{m.name}</span>
                          {m.id === model && <Check size={14} className="model-check" />}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

            </div>
          )}
        </div>

        {/* 提示与引导推荐词区域 */}
        {status === 'idle' && (
          <div className="suggestions">
            {suggestions.map((s, i) => (
              <div key={i} className="suggestion-row" onClick={() => handleSend(s.label)}>
                <span className="suggestion-emoji">{s.icon}</span>
                <span className="suggestion-text">{s.label}</span>
                <ArrowRight size={13} className="suggestion-arrow" />
              </div>
            ))}
            <div className="suggestion-row text-tertiary">
              <MoreHorizontal size={14} />
              <span className="suggestion-text">后续可以继续接入更多工具和资料来源</span>
              <ArrowRight size={13} className="suggestion-arrow" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
