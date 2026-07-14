import React from 'react';
import { NavLink } from 'react-router-dom';
import { MessageSquarePlus, LayoutDashboard, Clock, BookOpen, Settings } from 'lucide-react';
import './sidebar.css';

export function Sidebar() {
  return (
    <aside className="sidebar-dock">
      {/* Top Icons */}
      <div className="dock-top">
        <div className="dock-logo" title="EvoCanvas">
          <div className="logo-sq">E</div>
        </div>
        
        <NavLink to="/" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} end title="New Chat">
          <MessageSquarePlus size={20} strokeWidth={2} />
        </NavLink>
        
        <NavLink to="/workspace/demo" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Demo Workspace">
          <LayoutDashboard size={20} strokeWidth={2} />
        </NavLink>
        
        <NavLink to="/recent" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Recent History">
          <Clock size={20} strokeWidth={2} />
        </NavLink>

        <NavLink to="/knowledge" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Knowledge Base">
          <BookOpen size={20} strokeWidth={2} />
        </NavLink>
      </div>

      {/* Bottom Icons */}
      <div className="dock-bottom">
        <button className="dock-item" title="Settings">
          <Settings size={20} strokeWidth={2} />
        </button>
        <button className="dock-item user-avatar" title="Profile">
          <img src="/avatars/ui-kit-nine/avatar-chen-jiamu.png" alt="" className="user-avatar-image" />
        </button>
      </div>
    </aside>
  );
}
