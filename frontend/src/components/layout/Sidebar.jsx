import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { MessageSquarePlus, LayoutDashboard, Clock, BookOpen, Settings, X, Eye, EyeOff, CheckCircle2, AlertCircle, Plus, Trash2 } from 'lucide-react';
import { apiPostWithStatus } from '../../api';
import { getSelectedModel, PROVIDER_OPTIONS, readModelList, saveModelList, selectModel } from '../../modelConfig';
import './sidebar.css';

function ModelSettingsModal({ onClose }) {
  const initialModels = readModelList();
  const initialSelectedId = getSelectedModel();
  const [models, setModels] = useState(initialModels);
  const [editingId, setEditingId] = useState(initialSelectedId);
  const [form, setForm] = useState(() => initialModels.find(item => item.id === initialSelectedId) || {});
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const update = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const blankModel = () => ({
    id: '',
    name: '',
    providerId: 'custom',
    providerName: '自定义 Provider',
    baseUrl: '',
    apiKey: '',
  });

  const chooseModel = (model) => {
    setEditingId(model.id);
    setForm({ ...model });
    selectModel(model.id);
    window.dispatchEvent(new CustomEvent('evocanvas:model-config-changed'));
    setShowKey(false);
    setFeedback(null);
  };

  const handleNewModel = () => {
    setEditingId(null);
    setForm(blankModel());
    setShowKey(false);
    setFeedback(null);
  };

  const handleProviderChange = (providerId) => {
    const provider = PROVIDER_OPTIONS.find(item => item.id === providerId);
    setForm(prev => ({
      ...prev,
      providerId,
      providerName: provider?.name || providerId,
      baseUrl: providerId === 'custom' ? prev.baseUrl : (provider?.baseUrl || prev.baseUrl),
    }));
    setFeedback(null);
  };

  const handleTest = async () => {
    if (!form.id?.trim() || !form.baseUrl?.trim() || !form.apiKey?.trim()) {
      setFeedback({ type: 'error', text: '请先填写模型标识、Base URL 和 API Key。' });
      return;
    }
    setTesting(true);
    setFeedback(null);
    const response = await apiPostWithStatus('/api/model-config/test', {
      provider_id: form.providerId,
      base_url: form.baseUrl.trim(),
      api_key: form.apiKey.trim(),
      model_id: form.id.trim(),
    });
    setTesting(false);
    const result = response.data;
    setFeedback(response.ok && result?.ok
      ? { type: 'success', text: `连接成功：${result.model_id || form.id.trim()}` }
      : { type: 'error', text: result?.message || (response.status === 0 ? '连接失败：无法连接后端 API。' : `连接失败（HTTP ${response.status}）。`) });
  };

  const handleSave = () => {
    const id = form.id?.trim();
    const name = form.name?.trim();
    if (!id || !name) {
      setFeedback({ type: 'error', text: '请填写模型标识（Slug）和显示名称。' });
      return;
    }
    const duplicate = models.some(model => model.id === id && model.id !== editingId);
    if (duplicate) {
      setFeedback({ type: 'error', text: '模型标识已存在，请换一个唯一的 Slug。' });
      return;
    }
    const nextModel = {
      ...form,
      id,
      name,
      baseUrl: form.baseUrl?.trim() || '',
      apiKey: form.apiKey?.trim() || '',
    };
    const nextModels = editingId
      ? models.map(model => model.id === editingId ? nextModel : model)
      : [...models, nextModel];
    const saved = saveModelList(nextModels);
    setModels(saved);
    setEditingId(id);
    setForm(nextModel);
    selectModel(id);
    window.dispatchEvent(new CustomEvent('evocanvas:model-config-changed'));
    setFeedback({ type: 'success', text: '模型信息已保存到本机浏览器。' });
  };

  const handleDelete = () => {
    if (!editingId || models.length <= 1) {
      setFeedback({ type: 'error', text: '至少保留一个模型。' });
      return;
    }
    const nextModels = models.filter(model => model.id !== editingId);
    const saved = saveModelList(nextModels);
    setModels(saved);
    const nextSelected = saved[0];
    setEditingId(nextSelected.id);
    setForm({ ...nextSelected });
    selectModel(nextSelected.id);
    window.dispatchEvent(new CustomEvent('evocanvas:model-config-changed'));
    setFeedback({ type: 'success', text: '模型已删除。' });
  };

  return (
    <div className="settings-overlay" role="presentation" onMouseDown={event => event.target === event.currentTarget && onClose()}>
      <section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="model-settings-title">
        <div className="settings-modal-header">
          <div>
            <h2 id="model-settings-title">模型设置</h2>
            <p>配置 OpenAI 兼容协议的大模型提供商</p>
          </div>
          <button className="settings-close" onClick={onClose} aria-label="关闭设置"><X size={20} /></button>
        </div>

        <div className="settings-form">
          <div className="settings-section-heading">
            <div>
              <strong>模型目录</strong>
              <small>模型名称和标识由你维护，首页会实时读取这里的配置。</small>
            </div>
            <button type="button" className="settings-add-model" onClick={handleNewModel}><Plus size={14} />新增模型</button>
          </div>

          <div className="model-list" role="list" aria-label="已配置模型">
            {models.map(model => (
              <div key={model.id} className={`model-list-item${model.id === editingId ? ' active' : ''}`} role="listitem">
                <button type="button" className="model-list-main" onClick={() => chooseModel(model)}>
                  <span className="model-list-name">{model.name}</span>
                  <span className="model-list-meta">{model.id} · {model.providerName}</span>
                </button>
                <button type="button" className="model-list-edit" onClick={() => chooseModel(model)}>编辑</button>
              </div>
            ))}
          </div>

          <div className="settings-section-heading editor-heading">
            <div>
              <strong>{editingId ? '编辑模型' : '新增模型'}</strong>
              <small>只需填写基础连接信息即可使用。</small>
            </div>
            {editingId && <button type="button" className="settings-delete-model" onClick={handleDelete}><Trash2 size={14} />删除</button>}
          </div>

          <div className="settings-editor-grid">
            <label className="settings-field">
              <span>模型标识（Slug）</span>
              <input value={form.id || ''} onChange={event => { update('id', event.target.value); setFeedback(null); }} placeholder="例如 deepseek-v4-flash" spellCheck="false" />
            </label>

            <label className="settings-field">
              <span>显示名称</span>
              <input value={form.name || ''} onChange={event => { update('name', event.target.value); setFeedback(null); }} placeholder="例如 DeepSeek V4 Flash" />
            </label>
          </div>

          <label className="settings-field">
            <span>模型提供商</span>
            <select value={form.providerId || 'custom'} onChange={event => handleProviderChange(event.target.value)}>
              {PROVIDER_OPTIONS.map(provider => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
            </select>
          </label>

          {form.providerId === 'custom' && (
            <label className="settings-field">
              <span>提供商名称</span>
              <input value={form.providerName || ''} onChange={event => update('providerName', event.target.value)} placeholder="例如 SiliconFlow" />
            </label>
          )}

          <label className="settings-field">
            <span>Base URL</span>
            <input
              value={form.baseUrl || ''}
              onChange={event => { update('baseUrl', event.target.value); setFeedback(null); }}
              placeholder="https://api.example.com/v1"
              spellCheck="false"
              autoComplete="url"
            />
            <small>可填服务根地址，也可填 OpenAI 兼容的 /v1 地址。</small>
          </label>

          <label className="settings-field">
            <span>API Key</span>
            <div className="settings-secret-wrap">
              <input
                type={showKey ? 'text' : 'password'}
                value={form.apiKey || ''}
                onChange={event => { update('apiKey', event.target.value); setFeedback(null); }}
                placeholder="sk-..."
                spellCheck="false"
                autoComplete="new-password"
              />
              <button type="button" className="settings-secret-toggle" onClick={() => setShowKey(value => !value)} aria-label={showKey ? '隐藏 API Key' : '显示 API Key'}>
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          <div className="settings-security-note">API Key 仅保存在本机浏览器，不会写入代码仓库。</div>

          {feedback && (
            <div className={`settings-feedback ${feedback.type}`}>
              {feedback.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
              <span>{feedback.text}</span>
            </div>
          )}

          <div className="settings-actions">
            <button className="settings-test" onClick={handleTest} disabled={testing}>
              {testing ? '测试中…' : '测试连接'}
            </button>
            <button className="settings-save" onClick={handleSave}>保存模型</button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function Sidebar() {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <>
      <aside className="sidebar-dock">
        <div className="dock-top">
          <div className="dock-logo" title="EvoCanvas">
            <div className="logo-sq">E</div>
          </div>

          <NavLink to="/" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} end title="New Chat">
            <MessageSquarePlus size={20} strokeWidth={2} />
          </NavLink>

          <NavLink to="/workspace/demo" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Demo Workspace">
            <LayoutDashboard size={20} strokeWidth={2} />
          </NavLink>

          <NavLink to="/recent" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Recent History">
            <Clock size={20} strokeWidth={2} />
          </NavLink>

          <NavLink to="/knowledge" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Knowledge Base">
            <BookOpen size={20} strokeWidth={2} />
          </NavLink>
        </div>

        <div className="dock-bottom">
          <button className={`dock-item${showSettings ? ' active' : ''}`} title="Settings" onClick={() => setShowSettings(true)}>
            <Settings size={20} strokeWidth={2} />
          </button>
          <button className="dock-item user-avatar" title="Profile">
            <img src="/avatars/ui-kit-nine/avatar-chen-jiamu.png" alt="" className="user-avatar-image" />
          </button>
        </div>
      </aside>
      {showSettings && <ModelSettingsModal onClose={() => setShowSettings(false)} />}
    </>
  );
}
