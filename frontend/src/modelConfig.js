const SELECTED_MODEL_STORAGE_KEY = 'evocanvas_selected_model';

export const DEFAULT_MODEL_ID = 'deepseek-v4-flash';
export const MODEL_CONFIG_STORAGE_KEY = 'evocanvas_model_config';
export const MODEL_LIST_STORAGE_KEY = 'evocanvas_model_list';

export const PROVIDER_OPTIONS = [
  { id: 'deepseek', name: 'DeepSeek', baseUrl: 'https://api.deepseek.com' },
  { id: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1' },
  { id: 'custom', name: '自定义（OpenAI 兼容）', baseUrl: '' },
];

/**
 * 首次打开时提供一组可直接编辑的示例模型。
 * 它们只是本机模型目录的初始值，保存后模型标识和显示名称均由用户配置。
 */
export const DEFAULT_MODELS = [
  {
    id: 'deepseek-v4-flash',
    name: 'DeepSeek V4 Flash',
    providerId: 'deepseek',
    providerName: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com',
    apiKey: '',
  },
  {
    id: 'deepseek-v4-pro',
    name: 'DeepSeek V4 Pro',
    providerId: 'deepseek',
    providerName: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com',
    apiKey: '',
  },
  {
    id: 'gpt-5.6-sol',
    name: 'GPT-5.6 Sol',
    providerId: 'openai',
    providerName: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    apiKey: '',
  },
  {
    id: 'gpt-5.6-terra',
    name: 'GPT-5.6 Terra',
    providerId: 'openai',
    providerName: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    apiKey: '',
  },
  {
    id: 'gpt-5.6-luna',
    name: 'GPT-5.6 Luna',
    providerId: 'openai',
    providerName: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    apiKey: '',
  },
];

// 兼容仍引用历史常量的页面或插件；新代码应通过 readModelList() 读取本机目录。
export const AVAILABLE_MODELS = DEFAULT_MODELS.map(({ id, name }) => ({ id, name }));

export const DEFAULT_MODEL_CONFIG = {
  providerId: 'deepseek',
  providerName: 'DeepSeek',
  baseUrl: 'https://api.deepseek.com',
  apiKey: '',
};

function normalizeModel(model) {
  if (!model || typeof model !== 'object') return null;
  const id = String(model.id || '').trim();
  const name = String(model.name || '').trim();
  if (!id || !name) return null;

  const providerId = String(model.providerId || 'custom').trim() || 'custom';
  const provider = PROVIDER_OPTIONS.find(item => item.id === providerId);
  const providerName = String(model.providerName || provider?.name || providerId).trim();
  const baseUrl = String(model.baseUrl || '').trim().replace(/\/+$/, '');

  return {
    id,
    name,
    providerId,
    providerName,
    baseUrl,
    apiKey: String(model.apiKey || '').trim(),
  };
}

function normalizeModelList(models) {
  const seen = new Set();
  return (Array.isArray(models) ? models : [])
    .map(normalizeModel)
    .filter(model => {
      if (!model || seen.has(model.id)) return false;
      seen.add(model.id);
      return true;
    });
}

function readStoredModelConfig() {
  try {
    const stored = JSON.parse(localStorage.getItem(MODEL_CONFIG_STORAGE_KEY) || 'null');
    if (!stored || typeof stored !== 'object') return { ...DEFAULT_MODEL_CONFIG };
    return {
      ...DEFAULT_MODEL_CONFIG,
      ...stored,
      baseUrl: String(stored.baseUrl || DEFAULT_MODEL_CONFIG.baseUrl).trim().replace(/\/+$/, ''),
      apiKey: String(stored.apiKey || '').trim(),
    };
  } catch {
    return { ...DEFAULT_MODEL_CONFIG };
  }
}

/** 读取本机可编辑的模型目录。 */
export function readModelList() {
  try {
    const stored = JSON.parse(localStorage.getItem(MODEL_LIST_STORAGE_KEY) || 'null');
    const normalized = normalizeModelList(stored);
    if (normalized.length > 0) return normalized;
  } catch {
    // 使用默认目录继续启动，避免损坏的本地 JSON 阻塞首页。
  }

  const storedConfig = readStoredModelConfig();
  const selectedId = localStorage.getItem(SELECTED_MODEL_STORAGE_KEY) || DEFAULT_MODEL_ID;
  return DEFAULT_MODELS.map(model => model.id === selectedId
    ? { ...model, ...storedConfig, id: model.id, name: model.name }
    : { ...model });
}

/** 保存本机模型目录；API Key 只写入当前浏览器 localStorage。 */
export function saveModelList(models) {
  const normalized = normalizeModelList(models);
  localStorage.setItem(MODEL_LIST_STORAGE_KEY, JSON.stringify(normalized));
  return normalized;
}

export function getSelectedModel() {
  const models = readModelList();
  const stored = localStorage.getItem(SELECTED_MODEL_STORAGE_KEY);
  if (stored && models.some(item => item.id === stored)) return stored;
  return models.find(item => item.id === DEFAULT_MODEL_ID)?.id || models[0]?.id || DEFAULT_MODEL_ID;
}

export function selectModel(modelId) {
  const models = readModelList();
  const next = models.some(item => item.id === modelId) ? modelId : getSelectedModel();
  localStorage.setItem(SELECTED_MODEL_STORAGE_KEY, next);
  return next;
}

// 保留单模型配置接口，避免其他页面切换时出现断裂。
export function readModelConfig() {
  return readModelList().find(item => item.id === getSelectedModel()) || { ...DEFAULT_MODEL_CONFIG };
}

export function saveModelConfig(config) {
  const selectedId = getSelectedModel();
  const models = readModelList();
  const next = models.map(model => model.id === selectedId ? normalizeModel({
    ...model,
    ...config,
    id: selectedId,
    name: model.name,
  }) : model).filter(Boolean);
  saveModelList(next);
  return next.find(model => model.id === selectedId);
}

/** 只有该模型明确保存了 Key 和 Base URL，才覆盖 Runtime 的环境配置。 */
export function readConfiguredModel(modelId) {
  const model = readModelList().find(item => item.id === (modelId || getSelectedModel()));
  if (!model?.apiKey || !model?.baseUrl) return undefined;
  return {
    provider_id: model.providerId || 'custom',
    provider_name: model.providerName || '自定义 Provider',
    base_url: model.baseUrl,
    api_key: model.apiKey,
    model_id: model.id,
  };
}
