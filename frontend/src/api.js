/**
 * @file api.js
 * @description 前端与后端进行 API 通信的基础请求封装库，集成了超时机制及常用的 HTTP 方法（GET、POST、PUT、DELETE、文件上传）。
 */

const API_BASE = import.meta.env.VITE_API_BASE || '';
const DEFAULT_TIMEOUT_MS = 12000;

/**
 * 带有超时机制的 fetch 封装函数
 * @param {string} url - 请求的目标 URL
 * @param {RequestInit} [options={}] - 传给 fetch 的配置项
 * @param {number} [timeoutMs=DEFAULT_TIMEOUT_MS] - 超时时间（毫秒），默认 12000ms
 * @returns {Promise<Response>} 响应的 Promise 对象
 */
async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  // 创建 AbortController 以便在超时后中断请求
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    // 无论成功还是失败，均清除定时器以释放资源
    clearTimeout(timer);
  }
}

/**
 * 构建完整的 API 请求 URL
 * @param {string} path - 相对路径（以 / 开头）
 * @returns {string} 完整的 API 接口 URL
 */
export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

/**
 * 发起 GET 请求
 * @param {string} path - API 相对路径
 * @param {*} fallback - 请求失败或异常时的退回默认值
 * @returns {Promise<*>} 解析后的 JSON 数据，若失败则返回 fallback
 */
export async function apiGet(path, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path));
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

/**
 * 发起 Multipart 文件上传请求 (POST)
 * @param {string} path - API 相对路径
 * @param {File} file - 要上传的文件对象
 * @param {*} fallback - 失败时的退回默认值
 * @returns {Promise<*>} 解析后的 JSON 响应，若失败则返回 fallback
 */
export async function apiUpload(path, file, fallback) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(`UPLOAD ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

/**
 * 发起 POST 请求
 * @param {string} path - API 相对路径
 * @param {Object} body - 请求体对象
 * @param {*} fallback - 失败时的退回默认值
 * @returns {Promise<*>} 解析后的 JSON 响应，若失败则返回 fallback
 */
export async function apiPost(path, body, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

/** 发起 POST 并保留 HTTP 状态，供 Canvas 主链处理运行时错误。 */
export async function apiPostWithStatus(path, body) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    return { ok: res.ok, status: res.status, data };
  } catch (error) {
    console.warn(error);
    return { ok: false, status: 0, data: null };
  }
}

/**
 * 发起 PUT 请求
 * @param {string} path - API 相对路径
 * @param {Object} body - 修改后的请求体对象
 * @param {*} fallback - 失败时的退回默认值
 * @returns {Promise<*>} 解析后的 JSON 响应，若失败则返回 fallback
 */
export async function apiPut(path, body, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

/**
 * 发起 DELETE 请求
 * @param {string} path - API 相对路径
 * @param {*} fallback - 失败时的退回默认值
 * @returns {Promise<*>} 解析后的 JSON 响应，若失败则返回 fallback
 */
export async function apiDelete(path, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

/**
 * 发起 PATCH 请求
 * @param {string} path - API 相对路径
 * @param {Object} body - 修改后的请求体对象
 * @param {*} fallback - 失败时的退回默认值
 * @returns {Promise<*>} 解析后的 JSON 响应，若失败则返回 fallback
 */
export async function apiPatch(path, body, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

/**
 * 发起 PATCH 请求并返回完整状态信息，不吞业务错误状态码。
 * 用于需要按 HTTP 状态码做差异化处理的场景（如 409 chat_confirmation_required）。
 * @param {string} path - API 相对路径
 * @param {Object} body - 修改后的请求体对象
 * @returns {Promise<{ok: boolean, status: number, data: *|null}>} 响应结果，status 为 0 表示网络/超时错误
 */
export async function apiPatchWithStatus(path, body) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    return { ok: res.ok, status: res.status, data };
  } catch (error) {
    console.warn(error);
    return { ok: false, status: 0, data: null };
  }
}

export { API_BASE };
