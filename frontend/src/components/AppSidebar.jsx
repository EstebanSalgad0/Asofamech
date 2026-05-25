import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getStreakDisplay } from "../tracker";

const navItems = [
  { id: "dashboard", label: "Inicio", path: "/dashboard", icon: "home", group: "Navegacion" },
  { id: "chat", label: "Asistente IA", path: "/dashboard/chat", icon: "chat", group: "Navegacion" },
  { id: "sct", label: "Test SCT", path: "/dashboard/sct", icon: "clipboard", group: "Navegacion" },
  { id: "images", label: "Imagenes IA", path: "/dashboard/images", icon: "image", group: "Navegacion" },
  { id: "cases", label: "Casos Clinicos", path: "/dashboard/cases", icon: "cases", group: "Navegacion" },
  { id: "feedback", label: "Evaluacion", path: "/dashboard/feedback", icon: "feedback", group: "Navegacion" },
  { id: "review", label: "Revision", path: "/dashboard/review", icon: "review", group: "Admin", privileged: true },
  { id: "config", label: "Configuracion", path: "/dashboard/config", icon: "settings", group: "Admin", privileged: true },
];

function Icon({ name }) {
  if (name === "home") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1V10Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "chat") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M21 14a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v7Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "clipboard") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M9 4h6M9 3h6a1 1 0 0 1 1 1v2H8V4a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M8 6H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-2M8 12h8M8 16h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "image") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 5h16v14H4V5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M8 14h8M10 10v8M14 10v8M12 7v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "settings") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" stroke="currentColor" strokeWidth="1.8" />
        <path d="M19 13.5v-3l-2.1-.4a7.5 7.5 0 0 0-.8-1.8l1.2-1.8-2.1-2.1-1.8 1.2a7.5 7.5 0 0 0-1.9-.8L11.1 2H8.2l-.4 2.1c-.7.2-1.3.5-1.9.8L4.2 3.8 2.1 5.9l1.2 1.8c-.4.6-.7 1.2-.9 1.9L.4 10v3l2.1.4c.2.7.5 1.3.9 1.9l-1.2 1.8 2.1 2.1 1.8-1.2c.6.4 1.2.7 1.9.9l.4 2.1h2.9l.4-2.1c.7-.2 1.3-.5 1.9-.9l1.8 1.2 2.1-2.1-1.2-1.8c.4-.6.7-1.2.8-1.9l2-.4Z" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "cases") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M14 2v6h6M9 13h6M9 17h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "review") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    );
  }
  if (name === "feedback") {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M8 14s1.5 2 4 2 4-2 4-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M9 9h.01M15 9h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  return null;
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m21 21-4.3-4.3M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="m16 17 5-5-5-5M21 12H9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AppSidebar({ user, role, activeRoute, onLogout }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const privileged = role === "Administrador" || role === "Profesor";
  const { count: streakCount, weekBars } = getStreakDisplay();
  const visibleItems = navItems.filter((item) => !item.privileged || privileged);
  const filteredItems = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return visibleItems;
    return visibleItems.filter((item) => item.label.toLowerCase().includes(normalized));
  }, [query, visibleItems]);
  const navGroups = filteredItems.reduce((groups, item) => {
    groups[item.group] = [...(groups[item.group] || []), item];
    return groups;
  }, {});
  const initials = (user?.name || "U").split(/\s+/).slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("") || "U";

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    if (filteredItems.length > 0) navigate(filteredItems[0].path);
  };

  if (!user) return null;

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-top">
        <div className="app-sidebar-logo">
          <div className="app-sidebar-logo-mark">A</div>
          <div>
            <span className="app-sidebar-logo-text">ASOFAMECH</span>
            <span className="app-sidebar-version">v2.6 - 2026</span>
          </div>
        </div>
      </div>

      <form className="app-sidebar-search" onSubmit={handleSearchSubmit}>
        <SearchIcon />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar..."
          aria-label="Buscar modulo"
        />
        <kbd>⌘K</kbd>
      </form>

      <nav className="app-sidebar-nav">
        {Object.entries(navGroups).map(([group, items]) => (
          <div className="app-nav-group" key={group}>
            <div className="app-nav-heading">{group}</div>
            {items.map((item) => (
              <Link
                key={item.id}
                to={item.path}
                className={`app-nav-item ${activeRoute === item.id ? "active" : ""}`}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </Link>
            ))}
          </div>
        ))}
      </nav>

      <div className="app-sidebar-footer">
        <div className="app-streak-card">
          <div className="app-streak-top">
            <span>Tu Racha</span>
            <span className="app-streak-fire">🔥</span>
          </div>
          <div className="app-streak-days">
            <b>{streakCount}</b>
            <span>días</span>
          </div>
          <div className="app-streak-bars">
            {weekBars.map((bar, index) => (
              <i
                key={index}
                className={[bar.active ? "active" : "", bar.isToday ? "today" : ""].filter(Boolean).join(" ")}
                title={bar.day}
              />
            ))}
          </div>
          <div className="app-streak-labels">
            {weekBars.map((bar, index) => (
              <span key={index}>{bar.day}</span>
            ))}
          </div>
        </div>

        <div className="app-user-card">
          <div className="app-user-avatar">{initials}</div>
          <div>
            <div className="app-user-name">{user.name}</div>
            <div className="app-user-role-label">{role}</div>
          </div>
          <button onClick={onLogout} className="app-user-logout-icon" aria-label="Cerrar sesion">
            <LogoutIcon />
          </button>
        </div>
      </div>
    </aside>
  );
}
