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
} from 'lucide-react';
import './workspace.css';

// ── Mock 数据 ──
const MOCK_STEPS = [
  {
    id: 's1', role: 'Compiler', title: '分析需求', status: 'done', expanded: false,
    summary: '已提取核心目标：积分防刷网关，包含幂等校验、熔断降级、布隆过滤器三个关键模块。',
    output: '已提取核心目标：积分防刷网关，包含幂等校验、熔断降级、布隆过滤器三个关键模块。\n\n识别到高优先级约束：P95 延迟 < 100ms，日志留存率 100%。',
    startedAt: new Date(Date.now() - 65000).toISOString(),
    endedAt: new Date(Date.now() - 53000).toISOString(),
  },
  {
    id: 's2', role: 'Reviewer', title: '质量评审', status: 'done', expanded: false,
    summary: '方案健壮性通过评审。建议补充业务方接入规范说明，其余逻辑符合预期。',
    output: '方案健壮性通过评审。\n\n**建议**：\n1. 强调业务方接入规范（流水唯一、设备指纹）\n2. 影子模式需明确切换条件\n3. 熔断阈值建议写入配置文件而非硬编码',
    startedAt: new Date(Date.now() - 52000).toISOString(),
    endedAt: new Date(Date.now() - 38000).toISOString(),
  },
  {
    id: 's3', role: 'Writer', title: '生成文档', status: 'running', expanded: true,
    summary: null, output: '',
    startedAt: new Date(Date.now() - 12000).toISOString(), endedAt: null,
  },
];
const MOCK_DOC = `# 结构化交接物：积分防刷网关\n\n## 当前目标\n\n- 降低作弊刷分风险\n- 保证正常积分发放链路可继续推进\n\n## 已确认约束\n\n- P95 延迟 < 100ms\n- 日志留存率 100%\n- 需要支持幂等校验与熔断降级\n\n## 待决策\n\n- 布隆过滤器是否在 1.0 首版启用\n\n## 仍未解决的问题\n\n- 业务侧接入规范是否由平台统一下发\n`;
const MOCK_STREAM = '正在整理当前约束、冲突点和待决策项，并生成可继续交给 AI 推进的结构化交接物……▋';

// ── 常量 ──
const STEP_LABELS = { Compiler: '分析需求', Reviewer: '质量评审', Writer: '生成文档', SYSTEM: '系统调度' };
const STEP_COLORS = { Compiler: '#7c3aed', Reviewer: '#d97706', Writer: '#16a34a', SYSTEM: '#6b7280' };
const stepLabel = (role) => STEP_LABELS[role] || role || '执行中';
const stepColor = (role) => STEP_COLORS[role] || '#6b7280';

// ── 子组件 ──
function StepIcon({ status, color }) {
  if (status === 'running') return <Loader2 size={14} className="spin" style={{ color }} />;
  if (status === 'done') return <CheckCircle2 size={14} style={{ color: '#16a34a' }} />;
  if (status === 'failed') return <AlertCircle size={14} style={{ color: '#dc2626' }} />;
  return <div className="step-dot-pending" />;
}

function LiveTimer({ startedAt, endedAt }) {
  const [label, setLabel] = useState('');
  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    const fmt = () => {
      const end = endedAt ? new Date(endedAt).getTime() : Date.now();
      const s = Math.max(0, Math.floor((end - start) / 1000));
      setLabel(`${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`);
    };
    fmt();
    if (endedAt) return;
    const t = setInterval(fmt, 1000);
    return () => clearInterval(t);
  }, [startedAt, endedAt]);
  if (!label) return null;
  return <span className="step-timer"><Clock size={10} />{label}</span>;
}

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

  const [steps, setSteps] = useState([]);
  const [streamingStep, setStreamingStep] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [taskTitle, setTaskTitle] = useState('AI 工作台');
  const [isLive, setIsLive] = useState(false);
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
      setTaskTitle('积分防刷网关 EvoCanvas 工作面'); setTaskType('evocanvas');
      setSteps(MOCK_STEPS);
      setStreamingStep({ stepId: 's3', text: MOCK_STREAM, isThinking: false });
      setDoc(MOCK_DOC);
      setDocSecondary('# 画布快照说明\n\n当前仅展示结构化交接物与工作面状态。');
      setIsLive(true);
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
  }, [steps, streamingStep, userMessages, arbitration]);

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
    <div className="workspace">

      {/* ── 执行看板 ── */}
      <div className="ws-chat">
        <div className="ws-chat-header">
          <div className="ws-chat-title">
            <span>{taskTitle}</span>
            {isLive && <span className="live-badge"><span className="live-dot" />运行中</span>}
            {isDone && <span className="done-badge"><CheckCircle2 size={12} />已完成</span>}
            {isFailed && <span className="failed-badge"><AlertCircle size={12} />执行失败</span>}
            {taskStatus === 'cancelled' && <span className="paused-badge">已暂停</span>}
          </div>
          <div className="ws-chat-header-actions">
            <button className="icon-btn" title="设置"><Settings2 size={15} /></button>
            {hasOutput && !openedDoc && (
              <button
                className="icon-btn panel-toggle-btn"
                title="展开侧边栏"
                onClick={() => setOpenedDoc(outputItems.find(i => i.content)?.key || null)}
              >
                <PanelRight size={15} />
              </button>
            )}
          </div>
        </div>

        <div className="ws-messages" ref={scrollRef}>
          {steps.length === 0 && !isLive && <div className="step-empty">暂无执行记录</div>}

          {steps.map((step, idx) => {
            const isStreaming = streamingStep?.stepId === step.id;
            const streamText = isStreaming ? streamingStep.text : '';
            const isThinking = isStreaming && streamingStep?.isThinking;
            return (
              <div key={step.id} className={`step-row step-${step.status}`}>
                <div className="step-track">
                  <StepIcon status={step.status} color={stepColor(step.role)} />
                  {idx < steps.length - 1 && <div className={`step-line${step.status === 'done' ? ' done' : ''}`} />}
                </div>
                <div className="step-body">
                  <div className="step-header"
                    onClick={() => step.status !== 'running' &&
                      setSteps(prev => prev.map(s => s.id === step.id ? { ...s, expanded: !s.expanded } : s))}>
                    <span className="step-title" style={{ color: step.status === 'running' ? stepColor(step.role) : undefined }}>
                      {step.title}
                    </span>
                    <LiveTimer startedAt={step.startedAt} endedAt={step.endedAt} />
                    {step.status === 'running' && (
                      <button className="interrupt-btn" onClick={e => { e.stopPropagation(); handleInterrupt(); }}>
                        <Square size={9} />打断
                      </button>
                    )}
                    {step.status !== 'running' && (
                      <button className="step-expand-btn">
                        {step.expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      </button>
                    )}
                  </div>
                  {step.status === 'running' && (
                    <div className="step-stream markdown-body">
                      {isThinking
                        ? <span className="thinking-inline"><span className="thinking-dots"><span /><span /><span /></span>深度思考中...</span>
                        : <ReactMarkdown remarkPlugins={[remarkGfm]}>{sanitizeWorkspaceContent(streamText)}</ReactMarkdown>}
                    </div>
                  )}
                  {step.status !== 'running' && step.expanded && (step.output || step.summary) && (
                    <div className="step-output markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{sanitizeWorkspaceContent(step.output || step.summary)}</ReactMarkdown>
                    </div>
                  )}
                  {step.status === 'done' && !step.expanded && step.summary && (
                    <div className="step-summary">{step.summary.slice(0, 80)}{step.summary.length > 80 ? '…' : ''}</div>
                  )}
                  {step.status === 'failed' && !step.expanded && (
                    <div className="step-summary" style={{ color: '#dc2626' }}>执行失败，点击展开查看详情</div>
                  )}
                </div>
              </div>
            );
          })}

          {userMessages.map(m => (
            <div key={m.id} className="msg msg-user"><div className="msg-user-bubble">{m.text}</div></div>
          ))}
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
              <div className="ws-input-row">
                <textarea className="ws-input"
                  placeholder={isLive ? '运行中，可打断并下达新指令…' : '向 EvoLoop 发送指令…'}
                  value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  rows={1}
                />
                <button className={`ws-send${input.trim() ? ' active' : ''}`} onClick={handleSend}>
                  <Send size={14} />
                </button>
              </div>
              <div className="ws-input-tools">
                <button className="tool-btn"><Mic size={13} /></button>
                <button className="tool-btn" onClick={() => fileInputRef.current?.click()}>
                  <Paperclip size={13} />上传文件
                </button>
                <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }}
                  onChange={async e => {
                    for (const f of Array.from(e.target.files)) await apiUpload('/api/materials', f, null);
                    e.target.value = '';
                  }}
                />
                <div className="peer-icons">
                  {PEERS.map(p => (
                    <button key={p.id} className="peer-icon-btn" title={p.label}
                      onClick={() => taskId && taskId !== 'new' && taskId !== 'demo' &&
                        apiPost(`/api/tasks/${taskId}/peer-dispatch`, { peer_target: p.id }, null)}>
                      <p.Icon size={13} />
                    </button>
                  ))}
                </div>
                {canResume && (
                  <button className="tool-btn resume-tool-btn" onClick={handleResume}><Zap size={13} />继续执行</button>
                )}
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
