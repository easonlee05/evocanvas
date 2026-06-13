/**
 * @file Card.jsx
 * @description 通用卡片组件。支持“solid”（实底色）与“glass”（玻璃磨砂质感）两种样式变体，并可通过属性设置悬浮放大微动特效。
 */

import React from 'react';
import './card.css';

/**
 * Card 卡片组件
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 卡片内部渲染的内容
 * @param {string} [props.className=''] - 额外的自定义样式类名
 * @param {'solid'|'glass'} [props.variant='solid'] - 卡片样式变体，solid 为默认硬卡片，glass 为毛玻璃磨砂质感卡片
 * @param {boolean} [props.hoverable=false] - 是否启用悬浮交互动效（微升悬停阴影）
 * @param {React.HTMLAttributes<HTMLDivElement>} props.[...props] - 透传给外层容器 <div> 的其他 HTML 属性，如 onClick 等
 */
export function Card({ children, className = '', variant = 'solid', hoverable = false, ...props }) {
  const variantClass = variant === 'glass' ? 'card-glass' : 'card-solid';
  const hoverClass = hoverable ? 'card-hoverable' : '';
  
  return (
    <div className={`card ${variantClass} ${hoverClass} ${className}`} {...props}>
      {children}
    </div>
  );
}

