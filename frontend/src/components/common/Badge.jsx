/**
 * @file Badge.jsx
 * @description 通用徽章/标签组件。通常用于状态展示、计数标记或高亮标签。
 */

import React from 'react';
import './badge.css';

/**
 * Badge 徽章组件
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 徽章中显示的内容（文本或数字）
 * @param {'danger'|'success'|'warning'|'info'|'primary'|'secondary'} [props.variant='danger'] - 徽章的色彩变体类名，如 badge-danger 等
 * @param {string} [props.className=''] - 额外的自定义样式类名
 */
export function Badge({ children, variant = 'danger', className = '' }) {
  return (
    <span className={`badge badge-${variant} ${className}`}>
      {children}
    </span>
  );
}

