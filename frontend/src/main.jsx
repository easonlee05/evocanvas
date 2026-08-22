/**
 * @file main.jsx
 * @description 前端 React 应用的入口文件。负责创建 React 根节点，并将全局 <App /> 组件挂载到 HTML 的 root 节点上。
 * 启用了 StrictMode（严格模式）以进行额外的运行时检测和警告。
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';

function renderErrorOverlay(titleText, details, stackText) {
  const root = document.getElementById('root');
  if (!root) return;

  root.replaceChildren();

  const container = document.createElement('div');
  container.style.cssText = 'padding: 32px; color: #d32f2f; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #fff; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; overflow: auto; box-sizing: border-box;';

  const title = document.createElement('h2');
  title.style.cssText = 'margin-top: 0; font-size: 22px; border-bottom: 2px solid #ffcdd2; padding-bottom: 12px;';
  title.textContent = titleText;
  container.appendChild(title);

  details.forEach(({ label, text }) => {
    const p = document.createElement('p');
    p.style.cssText = 'font-size: 14px; color: #333; margin: 8px 0;';
    const strong = document.createElement('strong');
    strong.textContent = label + ': ';
    p.appendChild(strong);
    p.appendChild(document.createTextNode(text));
    container.appendChild(p);
  });

  const stackHeader = document.createElement('h3');
  stackHeader.style.cssText = 'font-size: 16px; margin-top: 24px; margin-bottom: 8px; color: #555;';
  stackHeader.textContent = '堆栈回溯 (Stack Trace):';
  container.appendChild(stackHeader);

  const pre = document.createElement('pre');
  pre.style.cssText = 'background: #f5f5f5; padding: 16px; border-radius: 6px; border: 1px solid #e0e0e0; font-family: monospace; font-size: 12px; line-height: 1.6; overflow-x: auto; color: #212121; white-space: pre-wrap; word-break: break-all;';
  pre.textContent = stackText || '暂无详细堆栈';
  container.appendChild(pre);

  const btn = document.createElement('button');
  btn.style.cssText = 'margin-top: 16px; padding: 8px 16px; background: #1976d2; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;';
  btn.textContent = '刷新页面';
  btn.addEventListener('click', () => window.location.reload());
  container.appendChild(btn);

  root.appendChild(container);
}

// 全局捕获 JS 运行期异常与未捕获的 Promise 错误，防范并直观呈现白屏故障（使用安全 DOM API 避免 XSS）
window.addEventListener('error', (event) => {
  renderErrorOverlay(
    '🚨 前端运行时崩溃 (JS Runtime Error)',
    [
      { label: '错误信息', text: event.message || '未知错误' },
      { label: '出错文件', text: `${event.filename || 'unknown'} (第 ${event.lineno} 行, 第 ${event.colno} 列)` },
    ],
    event.error ? event.error.stack : '暂无详细堆栈'
  );
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason;
  const message = reason ? (reason.message || String(reason)) : '未知原因';
  const stack = reason && reason.stack ? reason.stack : '暂无详细堆栈';
  renderErrorOverlay(
    '🚨 未捕获的异步 Promise 异常 (Unhandled Rejection)',
    [{ label: '原因/信息', text: message }],
    stack
  );
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

