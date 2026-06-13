/**
 * @file Button.jsx
 * @description 通用按钮组件。支持多种样式变体（主按钮、次按钮、幽灵按钮、图标按钮）以及尺寸定制，并可在文字两侧渲染图标。
 */

import React from 'react';
import './button.css';

/**
 * Button 按钮组件
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 按钮内的文本或子元素
 * @param {'primary'|'secondary'|'ghost'|'icon'} [props.variant='primary'] - 按钮样式变体
 * @param {'sm'|'md'|'lg'} [props.size='md'] - 按钮尺寸
 * @param {React.ReactNode} [props.icon] - 左侧图标组件
 * @param {React.ReactNode} [props.rightIcon] - 右侧图标组件
 * @param {string} [props.className=''] - 自定义类名
 * @param {React.ButtonHTMLAttributes<HTMLButtonElement>} props.[...props] - 透传给原生 <button> 的其他属性，如 onClick, disabled 等
 */
export function Button({ 
  children, 
  variant = 'primary', // primary, secondary, ghost, icon
  size = 'md', // sm, md, lg
  icon, 
  rightIcon,
  className = '', 
  ...props 
}) {
  const baseClass = variant === 'icon' ? 'btn-icon' : `btn btn-${variant} btn-${size}`;
  
  return (
    <button className={`${baseClass} ${className}`} {...props}>
      {icon && <span className="btn-icon-left">{icon}</span>}
      <span className="btn-text">{children}</span>
      {rightIcon && <span className="btn-icon-right">{rightIcon}</span>}
    </button>
  );
}

