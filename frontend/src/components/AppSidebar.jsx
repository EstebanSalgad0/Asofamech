import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getStreakDisplay } from "../tracker";
import { ThemeToggle, ThemeToggleHeader } from "./ThemeToggle";
import { FontSizeControlSidebar } from "./FontSizeControl";
import { getChatGenerationState, subscribeChatGeneration } from "../chatBackground";

const navItems = [
  { id: "dashboard", label: "Inicio", path: "/dashboard", icon: "home", group: "Navegación" },
  { id: "chat", label: "Asistente IA", path: "/dashboard/chat", icon: "chat", group: "Navegación" },
  { id: "sct", label: "Test SCT", path: "/dashboard/sct", icon: "clipboard", group: "Navegación" },
  { id: "images", label: "Imágenes IA", path: "/dashboard/images", icon: "image", group: "Navegación" },
  { id: "cases", label: "Casos Clínicos", path: "/dashboard/cases", icon: "cases", group: "Navegación" },
  { id: "feedback", label: "Evaluación", path: "/dashboard/feedback", icon: "feedback", group: "Navegación" },
  { id: "config", label: "Configuración", path: "/dashboard/config", icon: "settings", group: "Admin", privileged: true },
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

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10 21h4" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}

export function AppSidebar({ user, role, activeRoute, onLogout }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [chatGeneration, setChatGeneration] = useState(() => getChatGenerationState());

  const privileged = role === "Administrador" || role === "Profesor";
  const chatPending = chatGeneration.status === "pending";
  const chatReady =
    activeRoute !== "chat" &&
    (chatGeneration.status === "complete" || chatGeneration.status === "error") &&
    chatGeneration.task?.saved;
  const { count: streakCount, weekBars } = getStreakDisplay();
  const [streakVisible, setStreakVisible] = useState(
    () => localStorage.getItem("asofamech_streak_visible") !== "false"
  );
  const toggleStreak = () => {
    const next = !streakVisible;
    setStreakVisible(next);
    localStorage.setItem("asofamech_streak_visible", String(next));
  };
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

  useEffect(() => {
    return subscribeChatGeneration(setChatGeneration);
  }, []);

  if (!user) return null;

  return (
    <aside className="app-sidebar" data-testid="app-sidebar">
      <div className="app-sidebar-top">
        <div className="app-sidebar-logo">
          <div className="app-sidebar-logo-mark">A</div>
          <div className="app-sidebar-logo-info">
            <span className="app-sidebar-logo-text">ASOFAMECH</span>
            <span className="app-sidebar-version">v2.6 - 2026</span>
          </div>
          <ThemeToggleHeader />
        </div>
      </div>

      <form className="app-sidebar-search" onSubmit={handleSearchSubmit} data-testid="sidebar-search">
        <SearchIcon />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar..."
          aria-label="Buscar módulo"
          data-testid="sidebar-search-input"
        />
        <kbd>⌘K</kbd>
      </form>

      <nav className="app-sidebar-nav" aria-label="Navegación principal" data-testid="app-sidebar-nav">
        {Object.entries(navGroups).map(([group, items]) => (
          <div className="app-nav-group" key={group}>
            <div className="app-nav-heading">{group}</div>
            {items.map((item) => (
              <Link
                key={item.id}
                to={item.path}
                className={`app-nav-item ${activeRoute === item.id ? "active" : ""}`}
                aria-current={activeRoute === item.id ? "page" : undefined}
                data-testid={`nav-${item.id}`}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
                {item.id === "chat" && chatPending && (
                  <b
                    className="app-nav-chat-pulse"
                    title="MediChat generando respuesta"
                    aria-label="MediChat generando respuesta"
                  >
                    ...
                  </b>
                )}
                {item.id === "chat" && chatReady && (
                  <b
                    className={`app-nav-chat-ready ${chatGeneration.status === "error" ? "error" : ""}`}
                    title={
                      chatGeneration.status === "error"
                        ? "MediChat termino con un aviso"
                        : "Respuesta de MediChat lista"
                    }
                    aria-label={
                      chatGeneration.status === "error"
                        ? "MediChat termino con un aviso"
                        : "Respuesta de MediChat lista"
                    }
                  >
                    <BellIcon />
                  </b>
                )}
              </Link>
            ))}
          </div>
        ))}
      </nav>

      <div className="app-sidebar-footer">
        {streakVisible ? (
          <div className="app-streak-card">
            <div className="app-streak-top">
              <span>Tu Racha</span>
              <div className="app-streak-top-right">
                <span className="app-streak-fire">🔥</span>
                <button
                  className="app-streak-toggle"
                  onClick={toggleStreak}
                  title="Ocultar racha"
                  aria-label="Ocultar racha"
                >
                  ✕
                </button>
              </div>
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
        ) : (
          <button className="app-streak-show" onClick={toggleStreak} title="Mostrar racha">
            🔥 Mostrar racha
          </button>
        )}

        <FontSizeControlSidebar />

        <div className="app-user-card" data-testid="app-user-card">
          <div className="app-user-avatar">{initials}</div>
          <div>
            <div className="app-user-name">{user.name}</div>
            <div className="app-user-role-label">{role}</div>
          </div>
          <button onClick={onLogout} className="app-user-logout-icon" aria-label="Cerrar sesión">
            <LogoutIcon />
          </button>
        </div>
      </div>
    </aside>
  );
}
