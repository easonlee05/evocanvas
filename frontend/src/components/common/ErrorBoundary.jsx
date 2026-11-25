/**
 * @file ErrorBoundary.jsx
 * @description React 错误边界组件，防止画布或页面局部渲染异常导致整个应用白屏。
 */

import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[EvoCanvas ErrorBoundary]', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (typeof this.props.onReset === 'function') {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      const title = this.props.fallbackTitle || '当前工作面发生渲染异常';
      return (
        <div
          style={{
            padding: '32px',
            margin: '24px auto',
            maxWidth: '560px',
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '14px',
            boxShadow: '0 8px 24px rgba(15, 23, 42, 0.06)',
            color: '#1e293b',
          }}
        >
          <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 600 }}>{title}</h3>
          <p style={{ margin: '0 0 16px', fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
            {this.state.error?.message || '页面遇到未预期错误，你的工作区数据仍安全保存在服务端。'}
          </p>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              type="button"
              onClick={this.handleReset}
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                border: 'none',
                background: '#111827',
                color: '#fff',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              重试渲染
            </button>
            <button
              type="button"
              onClick={() => {
                window.location.href = '/';
              }}
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                border: '1px solid #d1d5db',
                background: '#fff',
                color: '#374151',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              返回首页
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
