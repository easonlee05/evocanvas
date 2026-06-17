import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiGet, apiPost, apiPut, apiUrl, apiUpload } from '../../api';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import {
  getCanvasViewStateStorageKey,
  readStoredCanvasViewState,
  shouldAutoRunTaskOnOpen,
} from './workspaceSession';
import { sanitizeWorkspaceContent } from './workspaceContent';
import {
  Zap, Settings2, Send, Mic, Paperclip,
  Square, CheckCircle2, ChevronRight, ChevronDown, ChevronUp, X,
  BookOpen, AlertCircle, Clock, Loader2, Terminal, Bot,
  Bold, Italic, Underline, List, Code, RotateCcw, PanelRight,
  CheckSquare, FileText, ArrowUp, Database, Link2, Plus, Layers,
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

// 文件卡片组件 (极简展示)
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

// 协作模型选项列表
const MODELS = [
  { id: 'gpt-5.4', name: 'GPT-5.4' },
  { id: 'gpt-5.5', name: 'GPT-5.5' },
  { id: 'claude-sonnet-4-6', name: 'Claude Sonnet 4.6' },
  { id: 'claude-opus-4-7', name: 'Claude Opus 4.7' },
  { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash' },
  { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro' },
];

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
  const [model, setModel] = useState(() => {
    return localStorage.getItem('evocanvas_selected_model') || 'gpt-5.4';
  });
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
  const [uploadedMaterials, setUploadedMaterials] = useState([]);
  const [knowledgeItems, setKnowledgeItems] = useState([]);
  const [sourceConnectors, setSourceConnectors] = useState([]);
  const [attachedSourceRefs, setAttachedSourceRefs] = useState([]);
  const [showKnowledgeMenu, setShowKnowledgeMenu] = useState(false);
  const [showSourceMenu, setShowSourceMenu] = useState(false);
  const [hasHydratedWorkspaceView, setHasHydratedWorkspaceView] = useState(false);

  const streamRef = useRef(null);
  const savedRef = useRef(true);
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  const writerMsgIdRef = useRef(null);

  useEffect(() => { savedRef.current = saved; }, [saved]);

  useEffect(() => {
    apiGet('/api/knowledge', { items: [] }).then(res => {
      setKnowledgeItems(res?.items || []);
    });
    apiGet('/api/source-connectors', { items: [] }).then(res => {
      setSourceConnectors(res?.items || []);
    });
  }, []);

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
    const savedMaterials = taskId ? localStorage.getItem(`evocanvas_materials_${taskId}`) : null;
    if (savedMaterials) {
      try {
        setUploadedMaterials(JSON.parse(savedMaterials));
      } catch (e) {
        setUploadedMaterials([]);
      }
    } else {
      setUploadedMaterials([]);
    }
    setAttachedSourceRefs([]);

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
    setHasHydratedWorkspaceView(false);
    const storageKey = getCanvasViewStateStorageKey(taskId);
    const storedState = readStoredCanvasViewState(storageKey);
    setSelectedCardId(storedState?.selectedCardId || null);
    setHasHydratedWorkspaceView(true);
  }, [taskId]);

  useEffect(() => {
    if (!hasHydratedWorkspaceView) return;

    const storageKey = getCanvasViewStateStorageKey(taskId);
    if (!storageKey) return;

    const currentState = readStoredCanvasViewState(storageKey) || {};
    const nextState = {
      ...currentState,
      selectedCardId,
    };
    localStorage.setItem(storageKey, JSON.stringify(nextState));
  }, [hasHydratedWorkspaceView, selectedCardId, taskId]);

  // 实时同步材料状态到 LocalStorage
  useEffect(() => {
    if (taskId && taskId !== 'demo' && taskId !== 'new') {
      localStorage.setItem(`evocanvas_materials_${taskId}`, JSON.stringify(uploadedMaterials));
    }
  }, [uploadedMaterials, taskId]);

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
      'canvas.card.updated', 'canvas.relation.created', 'canvas.relation.deleted', 'canvas.card.moved'
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
    else if (evType === 'canvas.card.updated' || evType === 'canvas.relation.created' || evType === 'canvas.relation.deleted' || evType === 'canvas.card.moved' || evType === 'canvas.handoff.refreshed') {
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

  async function handleAttachSource(connector) {
    const displayName = window.prompt('输入这次要引用的数据名称或场景', connector.label);
    if (!displayName) return;
    const queryText = window.prompt('输入查询说明、指标口径或引用目的', `用于分析 ${displayName}`);
    const created = await apiPost('/api/source-refs', {
      connector_type: connector.id,
      display_name: displayName,
      query_text: queryText || '',
      workspace_id: taskId && taskId !== 'demo' ? taskId : null,
    }, null);
    if (created?.source_ref_id) {
      setAttachedSourceRefs(prev => [...prev, created]);
      setShowSourceMenu(false);
    }
  }

  function insertKnowledgeReference(item) {
    const snippet = `参考知识：${item.title} - ${item.desc}`;
    setInput(prev => prev ? `${prev}\n${snippet}` : snippet);
    setShowKnowledgeMenu(false);
  }

  function handleSend() {
    const text = input.trim();
    if (!text) return;
    setChatMessages(prev => [...prev, { id: 'usr_' + Date.now(), role: 'user', text }]);
    setInput('');

    if (taskId && taskId !== 'demo') {
      const selectedIds = selectedCardId ? [selectedCardId] : [];
      const materialIds = uploadedMaterials
        .filter(m => m.status === 'success' && m.material_id)
        .map(m => m.material_id);

      apiPost(`/api/canvas/workspaces/${taskId}/messages`, {
        message: text,
        selected_card_ids: selectedIds,
        material_ids: materialIds,
        source_ref_ids: attachedSourceRefs.map(item => item.source_ref_id),
        mode: 'default',
        model: model
      }, null);
      
      setUploadedMaterials([]);
      setAttachedSourceRefs([]);
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
        uploadedMaterials={uploadedMaterials}
      />

      {/* 展开按钮 */}
      {!isChatOpen && (
        <button 
          className="chat-toggle-btn"
          onClick={() => setIsChatOpen(true)}
          style={{
            color: 'var(--text-secondary)',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
        >
          <Bot size={14} color="currentColor" /> Canvas AI
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
            <div className="ws-input-box" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
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

              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
                {attachedSourceRefs.length > 0 && (
                  <div className="input-attachments-preview" style={{ padding: '0 12px 8px', display: 'flex', flexWrap: 'wrap', gap: 6, width: '100%', boxSizing: 'border-box' }}>
                    {attachedSourceRefs.map((item) => (
                      <span key={item.source_ref_id} className="attachment-preview-chip" style={{ background: 'rgba(55, 65, 81, 0.1)', fontSize: 11, padding: '2px 8px', borderRadius: 12, display: 'inline-flex', alignItems: 'center' }}>
                        <Database size={10} style={{ marginRight: 4 }} />
                        {item.display_name}
                        <button style={{ background: 'none', border: 'none', marginLeft: 4, cursor: 'pointer', padding: 0 }} onClick={() => {
                          setAttachedSourceRefs(prev => prev.filter(entry => entry.source_ref_id !== item.source_ref_id));
                        }}>
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <textarea className="ws-input"
                  placeholder={isLive ? 'AI 正在思考...' : '输入您的想法，与助手探讨... (如未生效请强刷新 Cmd+Shift+R)'}
                  value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  rows={1}
                />
              </div>
              <div className="ws-input-bottom-bar">
                <div className="bottom-bar-left" style={{ position: 'relative' }}>
                  <button className="tool-btn" onClick={() => fileInputRef.current?.click()} data-tooltip="添加当前资料">
                    <Paperclip size={13} />
                  </button>
                  <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }}
                    onChange={async e => {
                      const files = Array.from(e.target.files);
                      for (const f of files) {
                        const tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                        setUploadedMaterials(prev => [...prev, {
                          id: tempId,
                          name: f.name,
                          status: 'uploading'
                        }]);

                        try {
                          const res = await apiUpload('/api/materials', f, null);
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
                      e.target.value = '';
                    }}
                  />
                  <button
                    className="tool-btn"
                    onClick={() => {
                      setShowKnowledgeMenu(prev => !prev);
                      setShowSourceMenu(false);
                    }}
                    data-tooltip="引用知识库条目"
                  >
                    <BookOpen size={13} />
                  </button>
                  <button
                    className="tool-btn"
                    onClick={() => {
                      setShowSourceMenu(prev => !prev);
                      setShowKnowledgeMenu(false);
                    }}
                    data-tooltip="连接数据源引用"
                  >
                    <Database size={13} />
                  </button>

                  {showKnowledgeMenu && (
                    <div className="model-dropdown-menu" style={{ left: 0, right: 'auto', minWidth: 260 }}>
                      {knowledgeItems.length === 0 && <div className="model-dropdown-item">暂无可引用知识</div>}
                      {knowledgeItems.slice(0, 6).map(item => (
                        <div key={item.id} className="model-dropdown-item" onClick={() => insertKnowledgeReference(item)}>
                          <div style={{ fontWeight: 600, fontSize: 12 }}>{item.title}</div>
                          <div style={{ fontSize: 11, opacity: 0.72 }}>{item.desc}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {showSourceMenu && (
                    <div className="model-dropdown-menu" style={{ left: 32, right: 'auto', minWidth: 280 }}>
                      {sourceConnectors.length === 0 && <div className="model-dropdown-item">暂无可用数据连接器</div>}
                      {sourceConnectors.map(item => (
                        <div key={item.id} className="model-dropdown-item" onClick={() => handleAttachSource(item)}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: 12 }}>
                            <Link2 size={12} />
                            {item.label}
                          </div>
                          <div style={{ fontSize: 11, opacity: 0.72 }}>{item.description}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bottom-bar-right">
                  <div className="model-selector-wrap">
                    <button className="model-selector-btn" onClick={() => setShowModelMenu(!showModelMenu)} title="选择模型">
                      <span>{(MODELS.find(m => m.id === model)?.name || model).replace('Claude ', '').replace('DeepSeek ', 'DS ')}</span>
                      <ChevronDown size={10} style={{ marginLeft: 2 }} />
                    </button>
                    {showModelMenu && (
                      <div className="model-dropdown-menu">
                        {MODELS.map(m => (
                          <div 
                            key={m.id}
                            className={`model-dropdown-item${m.id === model ? ' selected' : ''}`}
                            onClick={() => { 
                              setModel(m.id); 
                              localStorage.setItem('evocanvas_selected_model', m.id);
                              setShowModelMenu(false); 
                            }}
                          >
                            {m.name}
                          </div>
                        ))}
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
