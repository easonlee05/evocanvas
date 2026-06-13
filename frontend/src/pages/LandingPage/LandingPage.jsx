/**
 * @file LandingPage.jsx
 * @description EvoCanvas 起始页。提供对话式输入入口，让 PM 用自然语言、
 * 多源材料和上下文片段启动一张新的需求收敛工作面。
 */

import React, { useEffect, useState, useRef } from 'react';
import { ArrowUp, Zap, Search, Database, Paperclip, MoreHorizontal, ArrowRight, Loader, ChevronDown, Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiPost, apiUpload } from '../../api';
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
 * 供用户选择的 AI 模型选项
 * @type {Array<{id: string, name: string}>}
 */
const MODELS = [
  { id: 'gpt-5.4', name: 'GPT-5.4' },
  { id: 'gpt-5.5', name: 'GPT-5.5' },
  { id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6' },
  { id: 'claude-opus-4-7', name: 'Claude Opus 4.7' },
  { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro' },
];

/**
 * LandingPage 首页欢迎组件
 * @component
 */
export default function LandingPage() {
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('idle'); // 状态机状态: idle (空闲) | thinking (处理中/创建任务中) | done (完成)
  const [error, setError] = useState('');
  const [model, setModel] = useState('gpt-5.4'); // 选中的模型 ID
  const [isModelOpen, setIsModelOpen] = useState(false); // 模型下拉框的展示状态
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

  /**
   * 附件上传处理函数
   * @param {React.ChangeEvent<HTMLInputElement>} e - 文件输入框变更事件
   */
  const handleUpload = async (e) => {
    const picked = Array.from(e.target.files);
    e.target.value = ''; // 清空以允许重复上传同名文件
    for (const file of picked) {
      await apiUpload('/api/materials', file, null);
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
    
    // 调用 API 接口，向后端发起新任务包的编译与创建请求
    const task = await apiPost('/api/tasks', { prompt: msg, model }, null);
    const taskId = task?.taskId || task?.task_id || task?.id;
    if (taskId) {
      // 创建成功后，使用 react-router-dom 的 navigate 进行页面重定向，进入该任务的独立工作台
      navigate(`/workspace/${taskId}`);
      return;
    }
    setError('任务创建失败：请确认后端 API 已启动并可访问。');
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
          <div className="input-box">
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
                  {MODELS.find(m => m.id === model)?.name || 'Default'}
                  <ChevronDown size={12} className={`model-chevron ${isModelOpen ? 'open' : ''}`} />
                </button>
                {isModelOpen && (
                  <>
                    {/* 点击背景区域关闭下拉框 */}
                    <div className="model-dropdown-backdrop" onClick={() => setIsModelOpen(false)} />
                    <div className="model-dropdown">
                      <div className="model-dropdown-header">协作模型</div>
                      {MODELS.map(m => (
                        <div 
                          key={m.id} 
                          className={`model-item ${m.id === model ? 'selected' : ''}`}
                          onClick={() => { setModel(m.id); setIsModelOpen(false); }}
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
