/**
 * @file Header.jsx
 * @description 通用头部组件。包含动态面包屑导航（或纯标题显示）以及右侧快速操作按钮。
 */

import React from 'react';
import { ChevronRight, Home } from 'lucide-react';
import './header.css';

/**
 * Header 头部导航组件
 * @component
 * @param {Object} props
 * @param {string} [props.title] - 当未提供 breadcrumbs 时显示的纯文本页面标题
 * @param {Array<{label: string, path?: string}>} [props.breadcrumbs] - 面包屑导航配置数组。若传入，则依此循环生成级联面包屑，并插入分隔符
 */
export function Header({ title, breadcrumbs }) {
  return (
    <header className="header">
      <div className="breadcrumbs">
        {breadcrumbs ? (
          breadcrumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {/* 非第一项时，渲染右向箭头分隔符 */}
              {i > 0 && <ChevronRight size={12} className="bc-sep" />}
              <span className={i === breadcrumbs.length - 1 ? 'bc-current' : 'bc-link'}>
                {crumb.label}
              </span>
            </React.Fragment>
          ))
        ) : (
          <span className="bc-current">{title}</span>
        )}
      </div>

      <div className="header-right">
        <button className="header-btn">Invite</button>
        <button className="header-btn">Help</button>
      </div>
    </header>
  );
}

