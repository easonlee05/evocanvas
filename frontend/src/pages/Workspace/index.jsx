import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiGet, apiPost, apiPut, apiUrl, apiUpload } from '../../api';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import { shouldAutoRunTaskOnOpen } from './workspaceSession';
import { sanitizeWorkspaceContent } from './workspaceContent';
import {
  Zap, Settings2, Send, Mic, Paperclip,
  Square, CheckCircle2, ChevronRight, ChevronDown, ChevronUp, X,
  BookOpen, AlertCircle, Clock, Loader2, Terminal, Bot,
  Bold, Italic, Underline, List, Code, RotateCcw, PanelRight,
  CheckSquare, FileText, ArrowUp,
} from 'lucide-react';
import './workspace.css';
import Canvas from './Canvas';
import {
  DEMO_CHAT,
  DEMO_DOC,
  DEMO_DOC_SECONDARY,
  DEMO_PROJECT_TITLE,
} from './demoScenario.js';

function TiptapEditor({ content, onChange, onBlur }) {
  const editor = useEditor({
    extensions: [StarterKit, Markdown],
    content,
    editorProps: { attributes: { class: 'doc-editor markdown-body', style: 'outline:none;min-height:100%' } },
    onUpdate: ({ editor }) => onChange(editor.storage.markdown.getMarkdown()),
    onBlur: ({ editor }) => { if (onBlur) onBlur(editor.storage.markdown.getMarkdown()); },
  });
  useEffect(() => {
    if (editor && content !== editor.storage.markdown.getMarkdown() && !editor.isFocused)
      editor.commands.setContent(content);
  }, [content, editor]);
  return <EditorContent editor={editor} style={{ height: '100%' }} />;
}

// ── 主组件 ──
export default function Workspace() {
  const { id: taskId } = useParams();

  const [chatMessages, setChatMessages] = useState([]);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [steps, setSteps] = useState([]);
  const [streamingStep, setStreamingStep] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [taskTitle, setTaskTitle] = useState('Canvas AI');
  const [isLive, setIsLive] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [model, setModel] = useState('Gemini 3.5 Flash');
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [arbitration, setArbitration] = useState(null);
  const [userMessages, setUserMessages] = useState([]);
  const [input, setInput] = useState('');
  const [taskType, setTaskType] = useState(null);
  const [doc, setDoc] = useState('');
  const [docSecondary, setDocSecondary] = useState('');
  const [saved, setSaved] = useState(true);
  const [openedDoc, setOpenedDoc] = useState(null); // null | 'primary' | 'secondary'

  const PEERS = [
    { id: 'codex', label: 'Codex', Icon: Terminal },
    { id: 'claude', label: 'Claude', Icon: Bot },
  ];

  const streamRef = useRef(null);
  const savedRef = useRef(true);
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  const writerMsgIdRef = useRef(null);

  useEffect(() => { savedRef.current = saved; }, [saved]);

  useEffect(() => {
    setSteps([]); setStreamingStep(null); setTaskStatus(null); setArbitration(null);
    setUserMessages([]); setInput(''); setDoc(''); setDocSecondary('');
    setSaved(true); setOpenedDoc(null); setTaskType(null); setIsLive(false);
    writerMsgIdRef.current = null;

    if (!taskId || taskId === 'new') { setTaskTitle('新建任务'); setIsLive(true); return; }

    if (taskId === 'demo') {
      setTaskTitle(DEMO_PROJECT_TITLE); setTaskType('evocanvas');
      setChatMessages(DEMO_CHAT);
      setDoc(DEMO_DOC);
      setDocSecondary(DEMO_DOC_SECONDARY);
      setIsLive(false);
      return;
    }

    let closed = false;
    apiGet(`/api/tasks/${taskId}`, null).then(data => {
      if (closed) return;
      if (data?.title) setTaskTitle(data.title);
      if (data?.type) setTaskType(data.type);
      if (data && shouldAutoRunTaskOnOpen({ rawStatus: data.raw_status }))
        apiPost(`/api/tasks/${taskId}/run`, {}, null).catch(() => {});
      const finished = ['completed', 'cancelled', 'failed'].includes(data?.raw_status);
      setTaskStatus(data?.raw_status || null);
      setIsLive(!finished);
      connectStream(taskId);
      loadDocument(taskId);
    });
    return () => { closed = true; if (streamRef.current) streamRef.current.close(); };
  }, [taskId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [chatMessages, streamingMessage, userMessages, arbitration]);

  function connectStream(id) {
    if (streamRef.current) streamRef.current.close();
    const source = new EventSource(apiUrl(`/api/tasks/${id}/events`));
    streamRef.current = source;
    const handle = (e) => { try { handleEvent(JSON.parse(e.data)); } catch (_) {} };
    ['message','workflow.step.started','workflow.step.completed','agent.message.chunk',
      'agent.message.completed','arbitration.requested','artifact.created',
      'task.completed','task.cancelled','task.failed','tool.call.denied','model.fallback',
    ].forEach(t => source.addEventListener(t, handle));
    source.onerror = () => { source.close(); loadStoredMessages(id); };
  }

  function handleEvent(data) {
    const msg = data.frontend_message;
    if (!msg || msg.type === 'toast') return;
    const evType = data.type;

    if (evType === 'workflow.step.started') {
      const p = data.payload || {};
      if (p.step_type !== 'agent') return;
      const role = data.role || 'SYSTEM';
      setSteps(prev => prev.some(s => s.id === p.step_id) ? prev : [...prev, {
        id: p.step_id, role, title: p.title || stepLabel(role),
        status: 'running', output: '', summary: null,
        startedAt: data.created_at, endedAt: null, expanded: true,
      }]);
      setStreamingStep({ stepId: p.step_id, text: '', isThinking: true });
      setIsLive(true); return;
    }
    if (evType === 'workflow.step.completed') {
      const p = data.payload || {};
      setSteps(prev => prev.map(s => s.id === p.step_id
        ? { ...s, status: 'done', summary: p.summary || null, endedAt: data.created_at, expanded: false } : s));
      setStreamingStep(prev => prev?.stepId === p.step_id ? null : prev); return;
    }
    if (evType === 'workflow.step.failed') {
      const p = data.payload || {};
      setSteps(prev => prev.map(s => s.id === p.step_id
        ? { ...s, status: 'failed', endedAt: data.created_at, expanded: false } : s));
      setStreamingStep(prev => prev?.stepId === p.step_id ? null : prev); return;
    }
    if (msg.type === 'typing') { setStreamingStep(prev => prev ? { ...prev, isThinking: true } : null); return; }
    if (msg.type === 'chunk') {
      const isWriter = msg.avatar === 'W' || msg.avatar === 'Writer' || msg.agent?.toLowerCase().includes('writer');
      if (isWriter) {
        if (writerMsgIdRef.current !== msg.id) { writerMsgIdRef.current = msg.id; setDoc(sanitizeWorkspaceContent(msg.content)); }
        else setDoc(prev => sanitizeWorkspaceContent((prev || '') + msg.content));
      }
      setStreamingStep(prev => prev ? { ...prev, isThinking: false, text: (prev.text || '') + msg.content } : null); return;
    }
    if (evType === 'agent.message.completed') {
      const p = data.payload || {};
      setSteps(prev => prev.map(s => s.id === p.step_id ? { ...s, output: p.content || p.summary || '' } : s)); return;
    }
    if (evType === 'arbitration.requested') {
      const d = data.payload?.dispute_package || {};
      setArbitration({ stepId: data.payload?.step_id, title: d.title || '需要你的判断',
        question: d.decision_needed || '请选择一个方向继续。', options: d.options || [] });
      setIsLive(false); return;
    }
    if (evType === 'artifact.created') { if (taskId && taskId !== 'new') loadDocument(taskId); return; }
    if (evType === 'task.completed') {
      setIsLive(false); setTaskStatus('completed');
      if (streamRef.current) streamRef.current.close();
      if (taskId && taskId !== 'new') loadDocument(taskId); return;
    }
    if (evType === 'task.cancelled') { setIsLive(false); setTaskStatus('cancelled'); return; }
    if (evType === 'task.failed') { setIsLive(false); setTaskStatus('failed'); return; }
  }

  async function loadStoredMessages(id) {
    const result = await apiGet(`/api/tasks/${id}/trace`, null);
    if (!result) return;
    const stepMap = {};
    for (const ev of result.events || []) {
      const p = ev.payload || {};
      if (ev.type === 'workflow.step.started' && p.step_type === 'agent')
        stepMap[p.step_id] = { id: p.step_id, role: ev.role || 'SYSTEM', title: p.title || stepLabel(ev.role),
          status: 'running', output: '', summary: null, startedAt: ev.created_at, endedAt: null, expanded: false };
      if (ev.type === 'workflow.step.completed' && stepMap[p.step_id])
        Object.assign(stepMap[p.step_id], { status: 'done', summary: p.summary || null, endedAt: ev.created_at });
      if (ev.type === 'agent.message.completed' && stepMap[p.step_id])
        stepMap[p.step_id].output = p.content || p.summary || '';
    }
    setSteps(Object.values(stepMap));
  }

  async function loadDocument(id) {
    const result = await apiGet(`/api/tasks/${id}/document`, null);
    if (result && typeof result.content === 'string') { setDoc(result.content); setSaved(true); }
  }

  function saveDocument(content) {
    if (savedRef.current || !taskId || taskId === 'new' || taskId === 'demo') return;
    apiPut(`/api/tasks/${taskId}/document`, { content }, null).then(() => setSaved(true));
  }

  function handleInterrupt() {
    if (taskId && taskId !== 'new' && taskId !== 'demo') apiPost(`/api/tasks/${taskId}/interrupt`, {}, null);
    setIsLive(false); setStreamingStep(null);
  }

  function handleResume() {
    if (!taskId || taskId === 'new' || taskId === 'demo') return;
    setIsLive(true); apiPost(`/api/tasks/${taskId}/run`, {}, null).catch(() => {});
  }

  function handleSend() {
    const text = input.trim();
    if (!text) return;
    setUserMessages(prev => [...prev, { id: Date.now(), text }]);
    setInput('');
    if (taskId && taskId !== 'new' && taskId !== 'demo')
      apiPost(`/api/tasks/${taskId}/decisions`, { instruction: text }, null);
    if (!isLive) handleResume();
  }

  function handleArbitrationChoice(option) {
    if (!arbitration) return;
    if (taskId && taskId !== 'new' && taskId !== 'demo')
      apiPost(`/api/tasks/${taskId}/decisions`,
        { instruction: option.pm_position || option.label || '', step_id: arbitration.stepId }, null);
    setArbitration(null); setIsLive(true);
  }

  const isDone = taskStatus === 'completed';
  const isFailed = taskStatus === 'failed';

  const outputItems = taskType === 'prd'
    ? [{ key: 'primary', label: '结构化交接物', content: doc }, { key: 'secondary', label: '画布说明', content: docSecondary }]
    : [{ key: 'primary', label: '结构化交接物', content: doc }];
  const hasOutput = outputItems.some(i => i.content);
  const canResume = !isLive && taskStatus !== 'completed';
  const currentDocContent = openedDoc === 'secondary' ? docSecondary : doc;

  return (
    <div className="workspace" style={{ position: 'relative' }}>
      <Canvas isChatOpen={isChatOpen} />

      {/* 展开按钮 */}
      {!isChatOpen && (
        <button 
          className="chat-toggle-btn"
          onClick={() => setIsChatOpen(true)}
        >
          <Bot size={14} color="var(--clr-blue)" /> Canvas AI
        </button>
      )}

      {/* ── 执行看板 ── */}
      <div className={`ws-chat ${isChatOpen ? 'open' : 'closed'}`}>
        <div className="ws-chat-header">
          <div className="ws-chat-title">
            <span>{taskTitle}</span>
            {isLive && <span className="live-badge"><span className="live-dot" />运行中</span>}
            {isDone && <span className="done-badge"><CheckCircle2 size={12} />已完成</span>}
            {isFailed && <span className="failed-badge"><AlertCircle size={12} />执行失败</span>}
            {taskStatus === 'cancelled' && <span className="paused-badge">已暂停</span>}
          </div>
          <div className="ws-chat-header-actions">
            <button
              className="icon-btn"
              title="收起助手"
              onClick={() => setIsChatOpen(false)}
            >
              <PanelRight size={15} />
            </button>
          </div>
        </div>

        <div className="ws-messages" ref={scrollRef}>
          {chatMessages.length === 0 && !isLive && <div className="step-empty">暂无对话记录</div>}

          {chatMessages.map(m => (
            <div key={m.id} className={`chat-bubble-row ${m.role}`}>
              <div className={`chat-bubble ${m.role}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
              </div>
            </div>
          ))}

          {isLive && (
            <div className="chat-bubble-row ai">
              <div className="chat-bubble ai">
                {streamingMessage ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingMessage}</ReactMarkdown>
                ) : (
                  <span className="thinking-dots"><span/><span/><span/></span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 快捷追问指令 */}
        <div className="chat-suggestions">
          <button className="suggestion-chip" onClick={() => setInput('总结一下需求')}><List size={12}/> 总结需求</button>
          <button className="suggestion-chip" onClick={() => setInput('检查一致性')}><CheckSquare size={12}/> 检查一致性</button>
          <button className="suggestion-chip" onClick={() => setInput('生成用户故事')}><FileText size={12}/> 生成用户故事</button>
        </div>

        {/* 输入区 / 裁决卡 */}
        <div className="ws-input-wrap">
          {arbitration ? (
            <div className="arbitration-card">
              <div className="arb-title">{arbitration.title}</div>
              <div className="arb-question">{arbitration.question}</div>
              <div className="arb-options">
                {arbitration.options.map((opt, i) => (
                  <button key={i} className="arb-option-btn" onClick={() => handleArbitrationChoice(opt)}>
                    {opt.pm_position || opt.label || `选项 ${i + 1}`}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="ws-input-box">
              <textarea className="ws-input"
                placeholder={isLive ? 'AI 正在思考...' : '输入您的想法，与助手探讨...'}
                value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                rows={1}
              />
              <div className="ws-input-bottom-bar">
                <div className="bottom-bar-left">
                  <button className="tool-btn" onClick={() => fileInputRef.current?.click()} data-tooltip="上传文件">
                    <Paperclip size={13} />
                  </button>
                  <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }}
                    onChange={async e => {
                      for (const f of Array.from(e.target.files)) await apiUpload('/api/materials', f, null);
                      e.target.value = '';
                    }}
                  />
                </div>

                <div className="bottom-bar-right">
                  <div className="model-selector-wrap">
                    <button className="model-selector-btn" onClick={() => setShowModelMenu(!showModelMenu)} title="选择模型">
                      <span>{model === 'Gemini 3.5 Flash' ? '3.5 Flash' : '3.1 Pro'}</span>
                      <ChevronDown size={10} style={{ marginLeft: 2 }} />
                    </button>
                    {showModelMenu && (
                      <div className="model-dropdown-menu">
                        <div className="model-dropdown-item" onClick={() => { setModel('Gemini 3.5 Flash'); setShowModelMenu(false); }}>Gemini 3.5 Flash</div>
                        <div className="model-dropdown-item" onClick={() => { setModel('Gemini 3.1 Pro'); setShowModelMenu(false); }}>Gemini 3.1 Pro</div>
                      </div>
                    )}
                  </div>
                  <button 
                    className={`ws-send-codex${isLive ? ' active stop' : (input.trim() ? ' active' : '')}`} 
                    onClick={isLive ? handleInterrupt : handleSend}
                    data-tooltip={isLive ? '停止生成' : '发送消息'}
                  >
                    {isLive ? <Square size={10} fill="#fff" style={{ stroke: 'none' }} /> : <ArrowUp size={14} />}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 右侧产出抽屉 ── */}
      <div className={`output-drawer${openedDoc ? ' open' : ''}`}>
        {/* 文件胶囊标签 + 固定在右侧的收起按钮 */}
        <div className="output-drawer-header">
          <div className="output-drawer-tags">
            {outputItems.filter(i => i.content).map(item => (
              <button
                key={item.key}
                className={`output-file-tag${openedDoc === item.key ? ' active' : ''}`}
                onClick={() => setOpenedDoc(item.key)}
              >
                <span>{item.label}</span>
                <span className="output-tag-close" onClick={e => { e.stopPropagation(); setOpenedDoc(null); }}>
                  <X size={10} />
                </span>
              </button>
            ))}
          </div>
          <button
            className="icon-btn output-drawer-toggle"
            title="收起侧边栏"
            onClick={() => setOpenedDoc(null)}
          >
            <PanelRight size={15} />
          </button>
        </div>
        {/* 抽屉内容 */}
        <div className="output-drawer-body">
          {openedDoc && (
            <TiptapEditor
              key={`${taskId}-${openedDoc}`}
              content={currentDocContent}
              onChange={d => { openedDoc === 'secondary' ? setDocSecondary(d) : setDoc(d); setSaved(false); }}
              onBlur={saveDocument}
            />
          )}
        </div>
        {/* 保存状态 */}
        {openedDoc && (
          <div className="output-drawer-footer">
            <span className={`save-status${saved ? ' saved' : ''}`}>{saved ? '已保存' : '未保存'}</span>
          </div>
        )}
      </div>
    </div>
  );
}
