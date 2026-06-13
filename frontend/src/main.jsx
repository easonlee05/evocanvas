/**
 * @file main.jsx
 * @description 前端 React 应用的入口文件。负责创建 React 根节点，并将全局 <App /> 组件挂载到 HTML 的 root 节点上。
 * 启用了 StrictMode（严格模式）以进行额外的运行时检测和警告。
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

