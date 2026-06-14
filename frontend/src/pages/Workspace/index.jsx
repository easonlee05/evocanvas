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
  const [taskType, setTaskType] = useState('evocanvas');
  const [doc, setDoc] = useState('');
  const [docSecondary, setDocSecondary] = useState('');
  const [saved, setSaved] = useState(true);
  const [openedDoc, setOpenedDoc] = useState(null); // null | 'primary' | 'secondary'

  // EvoCanvas 真实状态管理
  const [selectedCardId, setSelectedCardId] = useState(null);
  const [cards, setCards] = useState([]);
  const [relations, setRelations] = useState([]);
  const [todos, setTodos] = useState([]);
  const [confirmations, setConfirmations] = useState([]);
  const [uploadedMaterialIds, setUploadedMaterialIds] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);

  const streamRef = useRef(null);
  const savedRef = useRef(true);
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  const writerMsgIdRef = useRef(null);

  useEffect(() => { savedRef.current = saved; }, [saved]);

  // 加载画布主视图数据
  function loadCanvasData(id) {
    if (!id || id === 'demo' || id === 'new') return;
    apiGet(`/api/canvas/workspaces/${id}/canvas`, null).then(res => {
      if (res) {
        setCards(res.cards || []);
        setRelations(res.relations || []);
        setTodos(res.todo_projection?.items || []);
      }
    });
    apiGet(`/api/canvas/workspaces/${id}/confirmations`, null).then(res => {
      if (res) {
        setConfirmations(res.items || []);
      }
    });
    apiGet(`/api/canvas/workspaces/${id}/handoff`, null).then(res => {
      if (res && res.handoff) {
        setDoc(res.handoff.summary || '');
      }
    });
  }

  useEffect(() => {
    setSteps([]); setStreamingStep(null); setTaskStatus(null); setArbitration(null);
    setUserMessages([]); setInput(''); setDoc(''); setDocSecondary('');
    setSaved(true); setOpenedDoc(null); setTaskType('evocanvas'); setIsLive(false);
    writerMsgIdRef.current = null;
    setSelectedCardId(null);
    setCards([]);
    setRelations([]);
    setTodos([]);
    setConfirmations([]);
    setUploadedMaterialIds([]);
    setUploadedFiles([]);

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
    apiGet(`/api/canvas/workspaces/${taskId}`, null).then(data => {
      if (closed) return;
      if (data) {
        setTaskTitle(data.title || 'EvoCanvas 工作区');
        setTaskType('evocanvas');
        const isRunning = data.active_turn_status === 'running';
        setIsLive(isRunning);
        loadCanvasData(taskId);
        connectStream(taskId);
      }
    });
    return () => { closed = true; if (streamRef.current) streamRef.current.close(); };
  }, [taskId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [chatMessages, streamingMessage, userMessages, arbitration]);

  function connectStream(id) {
    if (streamRef.current) streamRef.current.close();
    const source = new EventSource(apiUrl(`/api/canvas/workspaces/${id}/events`));
    streamRef.current = source;
    const handle = (e) => {
      try {
        const eventData = JSON.parse(e.data);
        handleCanvasEvent(eventData);
      } catch (err) {}
    };
    [
      'canvas.turn.started', 'canvas.mutation.proposed', 'canvas.confirmation.requested',
      'canvas.mutation.applied', 'canvas.turn.completed', 'canvas.turn.failed',
      'canvas.confirmation.approved', 'canvas.confirmation.rejected',
      'canvas.snapshot.created', 'canvas.handoff.refreshed',
      'canvas.card.updated', 'canvas.relation.created', 'canvas.card.moved'
    ].forEach(t => source.addEventListener(t, handle));
    source.onerror = () => { source.close(); };
  }

  function handleCanvasEvent(eventData) {
    const evType = eventData.type;
    const p = eventData.payload || {};

    if (evType === 'canvas.turn.started') {
      setIsLive(true);
      setChatMessages(prev => [...prev, {
        id: 'ev_' + Date.now(),
        role: 'ai',
        text: '🤖 AI 助理已启动并开始分析输入物料...'
      }]);
    }
    else if (evType === 'canvas.mutation.proposed' || evType === 'canvas.confirmation.requested') {
      loadCanvasData(taskId);
      const isHighRisk = p.result_action === 'pending_confirmation';
      const text = `🤖 提炼完成！当前意图: **${p.intent}**，内部角色: **${p.roles?.join(', ') || ''}**。\n\n` + 
                   (isHighRisk 
                     ? `⚠️ 发现高影响变更提案（如确认约束等），已放入**用户确认队列**，请审批后落盘。` 
                     : `✅ 变更提案已自动应用到主画布。`);
      setChatMessages(prev => [...prev, { id: 'ev_' + Date.now(), role: 'ai', text }]);
    }
    else if (evType === 'canvas.turn.completed' || evType === 'canvas.mutation.applied' || evType === 'canvas.confirmation.approved') {
      setIsLive(false);
      loadCanvasData(taskId);
    }
    else if (evType === 'canvas.turn.failed') {
      setIsLive(false);
      setChatMessages(prev => [...prev, {
        id: 'ev_' + Date.now(),
        role: 'ai',
        text: `⚠️ 分析运行失败：${p.error || '未知错误'}`
      }]);
    }
    else if (evType === 'canvas.card.updated' || evType === 'canvas.relation.created' || evType === 'canvas.card.moved' || evType === 'canvas.handoff.refreshed') {
      loadCanvasData(taskId);
    }
  }

  function saveDocument(content) {
    // 1.0 的交接物是由画布卡片自动 refresh_handoff 收束生成的，因此前端设为只读/自动保存态
    setSaved(true);
  }

  function handleInterrupt() {
    // Canvas 回合为异步单向流程，此处可作为 no-op 处理
    setIsLive(false);
  }

  function handleSend() {
    const text = input.trim();
    if (!text) return;
    setChatMessages(prev => [...prev, { id: 'usr_' + Date.now(), role: 'user', text }]);
    setInput('');

    if (taskId && taskId !== 'demo') {
      const selectedIds = selectedCardId ? [selectedCardId] : [];
      apiPost(`/api/canvas/workspaces/${taskId}/messages`, {
        message: text,
        selected_card_ids: selectedIds,
        material_ids: uploadedMaterialIds,
        mode: 'default',
        model: model
      }, null);
      
      setUploadedMaterialIds([]);
      setUploadedFiles([]);
    }
  }

  const isDone = taskStatus === 'completed';
  const isFailed = taskStatus === 'failed';

  const outputItems = [{ key: 'primary', label: '结构化交接物', content: doc }];
  if (docSecondary) {
    outputItems.push({ key: 'secondary', label: '画布说明', content: docSecondary });
  }

  const hasOutput = outputItems.some(i => i.content);
  const currentDocContent = openedDoc === 'secondary' ? docSecondary : doc;

  return (
    <div className="workspace" style={{ position: 'relative' }}>
      <Canvas 
        isChatOpen={isChatOpen} 
        workspaceId={taskId}
        cards={cards}
        relations={relations}
        todos={todos}
        confirmations={confirmations}
        selectedCardId={selectedCardId}
        setSelectedCardId={setSelectedCardId}
        onRefresh={() => loadCanvasData(taskId)}
      />

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
          <button className="suggestion-chip" onClick={() => setInput('总结一下当前画布上的证据')}><List size={12}/> 总结证据</button>
          <button className="suggestion-chip" onClick={() => setInput('检查当前约束与待澄清的冲突点')}><CheckSquare size={12}/> 检查冲突</button>
          <button className="suggestion-chip" onClick={() => setInput('整理并刷新交接物草稿')}><FileText size={12}/> 刷新交接物</button>
        </div>

        {/* 输入区 / 确认提案队列卡 */}
        <div className="ws-input-wrap">
          {uploadedFiles.length > 0 && (
            <div className="input-attachments-preview" style={{ padding: '8px 12px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {uploadedFiles.map((name, i) => (
                <span key={i} className="attachment-preview-chip" style={{ background: 'var(--clr-bg-alt)', fontSize: 11, padding: '2px 8px', borderRadius: 12, display: 'inline-flex', alignItems: 'center' }}>
                  <Paperclip size={10} style={{ marginRight: 4 }} />
                  {name}
                  <button style={{ background: 'none', border: 'none', marginLeft: 4, cursor: 'pointer', padding: 0 }} onClick={() => {
                    setUploadedFiles(prev => prev.filter((_, idx) => idx !== i));
                    setUploadedMaterialIds(prev => prev.filter((_, idx) => idx !== i));
                  }}>
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          )}

          {confirmations.length > 0 ? (
            <div className="arbitration-card" style={{ maxHeight: 250, overflowY: 'auto' }}>
              <div className="arb-title">⚠️ 待确认的画布修改提案</div>
              <div className="arb-question" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>AI 生成了如下变更包，这包含需要产品经理决策的卡片操作：</div>
              <div className="arb-options" style={{ display: 'flex', flexDirection: 'column', gap: 8, margin: '8px 0' }}>
                {confirmations.map((proposal) => (
                  <div key={proposal.proposal_id} style={{ border: '1px solid var(--clr-border)', borderRadius: 6, padding: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 'bold', marginBottom: 4 }}>提案 {proposal.proposal_id.substring(0, 10)}:</div>
                    {proposal.mutations.map((m, idx) => {
                      const mType = m.metadata?.mutation_type || m.mutation_type;
                      return (
                        <div key={idx} style={{ fontSize: 11, color: 'var(--text-secondary)', paddingLeft: 6 }}>
                          • <strong>{mType === 'add_card' ? '新增' : mType}</strong>: {m.payload?.card?.title || m.target_id}
                        </div>
                      );
                    })}
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      <button className="arb-option-btn" style={{ background: 'var(--clr-red-soft)', color: 'var(--clr-red)' }} onClick={async () => {
                        await apiPost(`/api/canvas/workspaces/${taskId}/confirmations/${proposal.proposal_id}/reject`, {});
                        loadCanvasData(taskId);
                      }}>
                        拒绝提案
                      </button>
                      <button className="arb-option-btn" onClick={async () => {
                        await apiPost(`/api/canvas/workspaces/${taskId}/confirmations/${proposal.proposal_id}/approve`, {});
                        loadCanvasData(taskId);
                      }}>
                        同意应用
                      </button>
                    </div>
                  </div>
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
                  <button className="tool-btn" onClick={() => fileInputRef.current?.click()} data-tooltip="上传参考材料">
                    <Paperclip size={13} />
                  </button>
                  <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }}
                    onChange={async e => {
                      const files = Array.from(e.target.files);
                      for (const f of files) {
                        const res = await apiUpload('/api/materials', f, null);
                        if (res && res.material_id) {
                          setUploadedMaterialIds(prev => [...prev, res.material_id]);
                          setUploadedFiles(prev => [...prev, f.name]);
                        }
                      }
                      e.target.value = '';
                    }}
                  />
                </div>

                <div className="bottom-bar-right">
                  <div className="model-selector-wrap">
                    <button className="model-selector-btn" onClick={() => setShowModelMenu(!showModelMenu)} title="选择模型">
                      <span>{model === 'Gemini 3.5 Flash' ? '3.5 Flash' : (model === 'DeepSeek V4 Flash' ? 'DS Flash' : '3.1 Pro')}</span>
                      <ChevronDown size={10} style={{ marginLeft: 2 }} />
                    </button>
                    {showModelMenu && (
                      <div className="model-dropdown-menu">
                        <div className="model-dropdown-item" onClick={() => { setModel('Gemini 3.5 Flash'); setShowModelMenu(false); }}>Gemini 3.5 Flash</div>
                        <div className="model-dropdown-item" onClick={() => { setModel('Gemini 3.1 Pro'); setShowModelMenu(false); }}>Gemini 3.1 Pro</div>
                        <div className="model-dropdown-item" onClick={() => { setModel('DeepSeek V4 Flash'); setShowModelMenu(false); }}>DeepSeek V4 Flash</div>
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
