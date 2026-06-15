/**
 * @file main.jsx
 * @description 前端 React 应用的入口文件。负责创建 React 根节点，并将全局 <App /> 组件挂载到 HTML 的 root 节点上。
 * 启用了 StrictMode（严格模式）以进行额外的运行时检测和警告。
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';

// 全局捕获 JS 运行期异常与未捕获的 Promise 错误，防范并直观呈现白屏故障
window.addEventListener('error', (event) => {
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = `
      <div style="padding: 32px; color: #d32f2f; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fff; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; overflow: auto; box-sizing: border-box;">
        <h2 style="margin-top: 0; font-size: 22px; border-bottom: 2px solid #ffcdd2; padding-bottom: 12px;">🚨 前端运行时崩溃 (JS Runtime Error)</h2>
        <p style="font-size: 15px; color: #333;"><strong>错误信息:</strong> ${event.message}</p>
        <p style="font-size: 13px; color: #666;"><strong>出错文件:</strong> ${event.filename} (第 ${event.lineno} 行, 第 ${event.colno} 列)</p>
        <h3 style="font-size: 16px; margin-top: 24px; margin-bottom: 8px; color: #555;">堆栈回溯 (Stack Trace):</h3>
        <pre style="background: #f5f5f5; padding: 16px; border-radius: 6px; border: 1px solid #e0e0e0; font-family: monospace; font-size: 12px; line-height: 1.6; overflow-x: auto; color: #212121;">${event.error ? event.error.stack : '暂无详细堆栈'}</pre>
        <button onclick="window.location.reload()" style="margin-top: 16px; padding: 8px 16px; background: #1976d2; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">刷新页面</button>
      </div>
    `;
  }
});

window.addEventListener('unhandledrejection', (event) => {
  const root = document.getElementById('root');
  if (root) {
    const reason = event.reason;
    root.innerHTML = `
      <div style="padding: 32px; color: #d32f2f; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fff; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; overflow: auto; box-sizing: border-box;">
        <h2 style="margin-top: 0; font-size: 22px; border-bottom: 2px solid #ffcdd2; padding-bottom: 12px;">🚨 未捕获的异步 Promise 异常 (Unhandled Rejection)</h2>
        <p style="font-size: 15px; color: #333;"><strong>原因/信息:</strong> ${reason ? (reason.message || String(reason)) : '未知原因'}</p>
        <h3 style="font-size: 16px; margin-top: 24px; margin-bottom: 8px; color: #555;">堆栈回溯 (Stack Trace):</h3>
        <pre style="background: #f5f5f5; padding: 16px; border-radius: 6px; border: 1px solid #e0e0e0; font-family: monospace; font-size: 12px; line-height: 1.6; overflow-x: auto; color: #212121;">${reason && reason.stack ? reason.stack : '暂无详细堆栈'}</pre>
        <button onclick="window.location.reload()" style="margin-top: 16px; padding: 8px 16px; background: #1976d2; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">刷新页面</button>
      </div>
    `;
  }
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

