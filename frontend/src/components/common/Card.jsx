/**
 * @file Card.jsx
 * @description EvoCanvas 通用卡片组件。默认用于承接清晰、轻量、带纸感的内容对象或系统容器。
 */

import './card.css';

/**
 * Card 卡片组件
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - 卡片内部渲染的内容
 * @param {string} [props.className=''] - 额外的自定义样式类名
 * @param {'solid'|'glass'} [props.variant='solid'] - 卡片样式变体，solid 为默认纸面卡片，glass 为辅助纸面变体
 * @param {boolean} [props.hoverable=false] - 是否启用轻量悬停反馈
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
