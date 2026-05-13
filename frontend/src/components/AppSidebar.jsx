import React from "react";
import { Link } from "react-router-dom";

const HomeIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
);

const ChatIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
  </svg>
);

const ClipboardIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
    <rect x="9" y="3" width="6" height="4" rx="1" ry="1"/>
  </svg>
);

const ImageIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
    <circle cx="8.5" cy="8.5" r="1.5"/>
    <polyline points="21 15 16 10 5 21"/>
  </svg>
);

const ReviewIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>
);

const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
  </svg>
);

const LogoutIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

export function AppSidebar({ user, role, activeRoute, onRoleChange, onLogout }) {
  if (!user) return null;

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-top">
        <div className="app-sidebar-logo">
          <div className="app-sidebar-logo-mark">A</div>
          <span className="app-sidebar-logo-text">ASOFAMECH</span>
        </div>
      </div>

      <nav className="app-sidebar-nav">
        <Link to="/dashboard" className={`app-nav-item ${activeRoute === "dashboard" ? "active" : ""}`}>
          <HomeIcon />
          <span>Inicio</span>
        </Link>
        <Link to="/dashboard/chat" className={`app-nav-item ${activeRoute === "chat" ? "active" : ""}`}>
          <ChatIcon />
          <span>Asistente IA</span>
        </Link>
        <Link to="/dashboard/sct" className={`app-nav-item ${activeRoute === "sct" ? "active" : ""}`}>
          <ClipboardIcon />
          <span>Test SCT</span>
        </Link>
        <Link to="/dashboard/images" className={`app-nav-item ${activeRoute === "images" ? "active" : ""}`}>
          <ImageIcon />
          <span>Imágenes IA</span>
        </Link>
        {(role === "Administrador" || role === "Profesor") && (
          <Link to="/dashboard/review" className={`app-nav-item ${activeRoute === "review" ? "active" : ""}`}>
            <ReviewIcon />
            <span>Revisión</span>
          </Link>
        )}
        {(role === "Administrador" || role === "Profesor") && (
          <Link to="/dashboard/config" className={`app-nav-item ${activeRoute === "config" ? "active" : ""}`}>
            <SettingsIcon />
            <span>Configuración</span>
          </Link>
        )}
      </nav>

      <div className="app-sidebar-footer">
        <div className="app-user-card">
          <div className="app-user-avatar">{user.name.charAt(0)}</div>
          <div>
            <div className="app-user-name">{user.name}</div>
            <div className="app-user-role-label">{role}</div>
          </div>
        </div>
        <div className="app-role-select app-role-display">{role}</div>
        <button onClick={onLogout} className="app-logout-btn">
          <LogoutIcon />
          Cerrar Sesión
        </button>
      </div>
    </aside>
  );
}
