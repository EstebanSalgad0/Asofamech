/**
 * Simple localStorage-based activity & metrics tracker for ASOFAMECH.
 *
 * Keys used:
 *   asofamech_metrics   – { consultations, studyMs, testsTotal, testsPassed }
 *   asofamech_activity   – [ { type, title, timestamp } , … ]  (max 30 entries)
 *   asofamech_session    – session start timestamp for study-time tracking
 *   asofamech_streak     – { count, lastDate, weekActivity: { "YYYY-MM-DD": true } }
 */

import { API_BASE, getAuthToken, userStorageKey } from "./authClient";

const METRICS_KEY = "asofamech_metrics";
const ACTIVITY_KEY = "asofamech_activity";
const SESSION_KEY = "asofamech_session";
const STREAK_KEY = "asofamech_streak";
const MAX_ACTIVITY = 30;

// ── Metrics ──────────────────────────────────────────────

function loadMetrics() {
  try {
    const raw = localStorage.getItem(userStorageKey(METRICS_KEY));
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { consultations: 0, studyMs: 0, testsTotal: 0, testsPassed: 0 };
}

function saveMetrics(m) {
  localStorage.setItem(userStorageKey(METRICS_KEY), JSON.stringify(m));
}

/** Increment the chat-consultation counter by `n` (default 1). */
export function trackConsultation(n = 1) {
  const m = loadMetrics();
  m.consultations += n;
  saveMetrics(m);
}

/** Record one completed SCT test.  `passed` = true if score >= 60 %. */
export function trackTestCompleted(passed = false) {
  const m = loadMetrics();
  m.testsTotal += 1;
  if (passed) m.testsPassed += 1;
  saveMetrics(m);
}

/** Return current metrics snapshot. */
export function getMetrics() {
  return loadMetrics();
}

// ── Study-time session ───────────────────────────────────

/** Call on every page mount to start / resume a session. */
export function startSession() {
  const key = userStorageKey(SESSION_KEY);
  if (!localStorage.getItem(key)) {
    localStorage.setItem(key, Date.now().toString());
  }
}

/** Call on page unload / unmount to flush elapsed time. */
export function flushSession() {
  const key = userStorageKey(SESSION_KEY);
  const start = parseInt(localStorage.getItem(key), 10);
  if (!start) return;
  const elapsed = Date.now() - start;
  if (elapsed > 500) {
    const m = loadMetrics();
    m.studyMs += elapsed;
    saveMetrics(m);
    const token = getAuthToken();
    if (token) {
      fetch(`${API_BASE}/api/dashboard/study-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ duration_ms: elapsed }),
        keepalive: true,
      }).catch(() => {});
    }
  }
  localStorage.removeItem(key);
}

/**
 * Format accumulated study milliseconds as a human-friendly string.
 * e.g. "0 min", "45 min", "3.5h"
 */
export function formatStudyTime(ms) {
  if (ms < 60_000) return "0 min";
  const mins = Math.floor(ms / 60_000);
  if (mins < 60) return `${mins} min`;
  return (ms / 3_600_000).toFixed(1) + "h";
}

// ── Activity feed ────────────────────────────────────────

function loadActivity() {
  try {
    const raw = localStorage.getItem(userStorageKey(ACTIVITY_KEY));
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return [];
}

function saveActivity(list) {
  localStorage.setItem(userStorageKey(ACTIVITY_KEY), JSON.stringify(list));
}

// ── Streak ───────────────────────────────────────────────

/** "YYYY-MM-DD" in local time (not UTC) for today or offsetDays ago/ahead. */
function localDateStr(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function loadStreak() {
  try {
    const raw = localStorage.getItem(userStorageKey(STREAK_KEY));
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { count: 0, lastDate: null, weekActivity: {} };
}

function saveStreak(s) {
  localStorage.setItem(userStorageKey(STREAK_KEY), JSON.stringify(s));
}

function recordStreakActivity() {
  const s = loadStreak();
  const today = localDateStr(0);
  const yesterday = localDateStr(-1);

  if (s.lastDate === today) {
    // Already recorded today — just ensure weekActivity is marked
    if (!s.weekActivity[today]) {
      s.weekActivity[today] = true;
      saveStreak(s);
    }
    return;
  }

  if (s.lastDate === yesterday) {
    s.count += 1;
  } else {
    // Gap > 1 day: reset streak
    s.count = 1;
  }

  s.lastDate = today;
  s.weekActivity[today] = true;

  // Prune weekActivity to keep only the last 14 days to avoid unbounded growth
  const cutoff = localDateStr(-14);
  for (const key of Object.keys(s.weekActivity)) {
    if (key < cutoff) delete s.weekActivity[key];
  }

  saveStreak(s);
}

/**
 * Returns streak count and a 7-item array for Mon–Sun of the current local week.
 * Each item: { day: "L"|"M"|…, active: bool, isToday: bool }
 */
export function getStreakDisplay() {
  const s = loadStreak();

  // Find Monday of the current local week
  const now = new Date();
  const dow = now.getDay(); // 0=Sun … 6=Sat
  const distToMonday = (dow === 0) ? -6 : 1 - dow;
  const dayLabels = ["L", "M", "M", "J", "V", "S", "D"];
  const today = localDateStr(0);

  const weekBars = dayLabels.map((label, i) => {
    const d = new Date(now);
    d.setDate(now.getDate() + distToMonday + i);
    const y = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, "0");
    const da = String(d.getDate()).padStart(2, "0");
    const dateStr = `${y}-${mo}-${da}`;
    return {
      day: label,
      active: Boolean(s.weekActivity[dateStr]),
      isToday: dateStr === today,
    };
  });

  return { count: s.count, weekBars };
}

/**
 * Push a new activity entry.
 *  type: "chat" | "sct" | "images"
 *  title: short description
 */
export function pushActivity(type, title) {
  recordStreakActivity();
  const list = loadActivity();
  list.unshift({ type, title, timestamp: new Date().toISOString() });
  // keep the list bounded
  if (list.length > MAX_ACTIVITY) list.length = MAX_ACTIVITY;
  saveActivity(list);
}

/** Return the most recent `n` entries (default 10). */
export function getRecentActivity(n = 10) {
  return loadActivity().slice(0, n);
}

/**
 * Return a relative-time string for an ISO timestamp.
 */
export function timeAgo(isoStr) {
  const now = new Date();
  const date = new Date(isoStr);
  const diffMs = now - date;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `Hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `Hace ${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Ayer";
  return `Hace ${days} días`;
}
