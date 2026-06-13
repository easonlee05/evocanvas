/**
 * @file Avatar.jsx
 * @description 通用头像组件。支持自定义大小，当没有传入头像图片链接时，显示后备 fallback（用户名首字母的大写形式）。
 */

import React from 'react';
import './avatar.css';

/**
 * Avatar 头像组件
 * @component
 * @param {Object} props
 * @param {string} [props.src] - 头像图片的 URL 地址。若不传，则显示 alt 的首字母作为后备。
 * @param {string} [props.alt=''] - 图片的替代文本（通常为用户名）。用于在无图时生成后备文字。
 * @param {'sm'|'md'|'lg'} [props.size='md'] - 头像尺寸大小，对应 CSS 中的样式类，如 avatar-sm, avatar-md, avatar-lg。
 * @param {string} [props.className=''] - 附加的自定义类名。
 */
export function Avatar({ src, alt = '', size = 'md', className = '' }) {
  return (
    <div className={`avatar avatar-${size} ${className}`}>
      {src ? (
        <img src={src} alt={alt} />
      ) : (
        <div className="avatar-fallback">{alt.charAt(0).toUpperCase()}</div>
      )}
    </div>
  );
}

