const THEME_STORAGE_KEY = "asofamech-theme";

export const LIGHT_THEME = "light";
export const DARK_THEME = "dark";

export function getStoredTheme() {
  if (typeof window === "undefined") return LIGHT_THEME;

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return storedTheme === DARK_THEME ? DARK_THEME : LIGHT_THEME;
}

export function applyTheme(theme) {
  const nextTheme = theme === DARK_THEME ? DARK_THEME : LIGHT_THEME;

  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.style.colorScheme = nextTheme;
  }

  return nextTheme;
}

export function saveTheme(theme) {
  const nextTheme = applyTheme(theme);

  if (typeof window !== "undefined") {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    window.dispatchEvent(new CustomEvent("asofamech-theme-change", { detail: { theme: nextTheme } }));
  }

  return nextTheme;
}

export function initTheme() {
  return applyTheme(getStoredTheme());
}
