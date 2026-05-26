import React, { useEffect, useState } from "react";
import { DARK_THEME, LIGHT_THEME, getStoredTheme, saveTheme } from "../theme";

function ThemeIcon({ theme }) {
  if (theme === DARK_THEME) {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M20.2 14.4A7.7 7.7 0 0 1 9.6 3.8 8.3 8.3 0 1 0 20.2 14.4Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function ThemeToggle({ variant = "floating" }) {
  const [theme, setTheme] = useState(() => getStoredTheme());
  const isDark = theme === DARK_THEME;
  const nextLabel = isDark ? "Activar modo claro" : "Activar modo oscuro";

  useEffect(() => {
    const syncTheme = (event) => {
      setTheme(event?.detail?.theme || getStoredTheme());
    };

    const syncStorageTheme = (event) => {
      if (!event.key || event.key === "asofamech-theme") {
        setTheme(getStoredTheme());
      }
    };

    window.addEventListener("asofamech-theme-change", syncTheme);
    window.addEventListener("storage", syncStorageTheme);

    return () => {
      window.removeEventListener("asofamech-theme-change", syncTheme);
      window.removeEventListener("storage", syncStorageTheme);
    };
  }, []);

  const handleToggle = () => {
    setTheme(saveTheme(isDark ? LIGHT_THEME : DARK_THEME));
  };

  return (
    <button
      type="button"
      className={`theme-toggle theme-toggle-${variant} ${isDark ? "is-dark" : ""}`}
      onClick={handleToggle}
      aria-label={nextLabel}
      aria-pressed={isDark}
      title={nextLabel}
    >
      <span className="theme-toggle-track" aria-hidden="true">
        <ThemeIcon theme={theme} />
      </span>
      {variant === "sidebar" && (
        <span className="theme-toggle-copy">
          <span>{isDark ? "Modo oscuro" : "Modo claro"}</span>
          <small>{isDark ? "Activo" : "Disponible"}</small>
        </span>
      )}
    </button>
  );
}

export function ThemeToggleHeader() {
  const [theme, setTheme] = useState(() => getStoredTheme());
  const isDark = theme === DARK_THEME;
  const nextLabel = isDark ? "Activar modo claro" : "Activar modo oscuro";

  useEffect(() => {
    const syncTheme = (event) => {
      setTheme(event?.detail?.theme || getStoredTheme());
    };
    const syncStorageTheme = (event) => {
      if (!event.key || event.key === "asofamech-theme") setTheme(getStoredTheme());
    };
    window.addEventListener("asofamech-theme-change", syncTheme);
    window.addEventListener("storage", syncStorageTheme);
    return () => {
      window.removeEventListener("asofamech-theme-change", syncTheme);
      window.removeEventListener("storage", syncStorageTheme);
    };
  }, []);

  const handleToggle = () => {
    setTheme(saveTheme(isDark ? LIGHT_THEME : DARK_THEME));
  };

  return (
    <button
      type="button"
      className={`theme-toggle-header-btn ${isDark ? "is-dark" : ""}`}
      onClick={handleToggle}
      aria-label={nextLabel}
      aria-pressed={isDark}
      title={nextLabel}
    >
      <ThemeIcon theme={theme} />
    </button>
  );
}
