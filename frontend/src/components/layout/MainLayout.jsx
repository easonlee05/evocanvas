/**
 * @file MainLayout.jsx
 * @description 应用的全局通用主体布局组件。包含固定的左侧边栏 (Sidebar)，以及居右填充的页面主内容渲染区 (main)。
 */

import React from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import './main-layout.css';

/**
 * MainLayout 核心主体布局组件
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 页面主体内容元素
 * @param {string} [props.title] - 页面标题参数（留作备用或由子页面自己消费）
 * @param {Array<Object>} [props.breadcrumbs] - 面包屑配置数据（留作备用或由子页面自己消费）
 * @param {boolean} [props.noHeader] - 是否隐藏头部导航栏标志（留作备用或由子页面自己消费）
 */
export function MainLayout({ children, title, breadcrumbs, noHeader }) {
  return (
    <div className="main-layout">
      <Sidebar />
      <div className="layout-content">
        <main className="main-area">
          {children}
        </main>
      </div>
    </div>
  );
}

