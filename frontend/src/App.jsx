/**
 * @file App.jsx
 * @description EvoCanvas 前端根组件。只保留新产品方向需要的入口路由：
 * 对话驱动的 Landing 和核心 Workspace，保持入口聚焦 EvoCanvas 1.0 主链。
 */

import { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import { ErrorBoundary } from './components/common/ErrorBoundary';

const LandingPage = lazy(() => import('./pages/LandingPage/LandingPage'));
const Workspace = lazy(() => import('./pages/Workspace/index'));
const RecentProjects = lazy(() => import('./pages/RecentProjects/RecentProjects'));
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase/index'));

function PageFallback() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '240px', color: '#64748b', fontSize: '13px' }}>
      正在加载工作面...
    </div>
  );
}

/**
 * 页面嵌套包裹辅助组件。
 * 将具体页面用 `MainLayout` 包裹起来，并统一注入页面标题。
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 需要包裹的子页面组件
 * @param {string} props.title - 页面标题
 * @param {Array<string>} [props.crumbs] - 面包屑导航项数组
 */
function W({ children, title, crumbs }) {
  return (
    <MainLayout title={title} breadcrumbs={crumbs}>
      <ErrorBoundary fallbackTitle={`${title || 'EvoCanvas'} 加载异常`}>
        <Suspense fallback={<PageFallback />}>{children}</Suspense>
      </ErrorBoundary>
    </MainLayout>
  );
}

/**
 * EvoCanvas 客户端路由控制中心。
 * @component
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<W title="EvoCanvas"><LandingPage /></W>} />
        <Route
          path="/workspace/:id"
          element={
            <MainLayout noHeader>
              <ErrorBoundary fallbackTitle="收敛工作区发生渲染异常">
                <Suspense fallback={<PageFallback />}><Workspace /></Suspense>
              </ErrorBoundary>
            </MainLayout>
          }
        />
        <Route path="/recent" element={<W title="Recent Projects"><RecentProjects /></W>} />
        <Route path="/knowledge" element={<W title="Knowledge Base"><KnowledgeBase /></W>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
