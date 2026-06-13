/**
 * @file SearchInput.jsx
 * @description 通用搜索输入框组件。集成了 Lucide 的搜索图标，并支持可选的键盘快捷键提示（如 ⌘K）。
 */

import React from 'react';
import { Search } from 'lucide-react';
import './search-input.css';

/**
 * SearchInput 搜索输入框组件
 * @component
 * @param {Object} props
 * @param {string} [props.className=''] - 附加的容器自定义类名。
 * @param {string} [props.placeholder='搜索'] - 输入框占位文本。
 * @param {string} [props.shortcut='⌘K'] - 键盘快捷键提示文本。如果不传或传空，则不渲染右侧快捷键提示。
 * @param {React.InputHTMLAttributes<HTMLInputElement>} props.[...props] - 其余透传给原生 <input> 的属性，例如 value, onChange 等。
 */
export function SearchInput({ className = '', placeholder = '搜索', shortcut = '⌘K', ...props }) {
  return (
    <div className={`search-container ${className}`}>
      <Search size={16} className="search-icon" />
      <input type="text" className="search-input" placeholder={placeholder} {...props} />
      {shortcut && <div className="search-shortcut">{shortcut}</div>}
    </div>
  );
}

