/**
 * Simple localStorage-based activity & metrics tracker for ASOFAMECH.
 *
 * Keys used:
 *   asofamech_metrics   – { consultations, studyMs, testsTotal, testsPassed }
 *   asofamech_activity   – [ { type, title, timestamp } , … ]  (max 30 entries)
 *   asofamech_session    – session start timestamp for study-time tracking
 */

import { userStorageKey } from "./authClient";

const METRICS_KEY = "asofamech_metrics";
const ACTIVITY_KEY = "asofamech_activity";
const SESSION_KEY = "asofamech_session";
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
  if (elapsed > 500) {                       // ignore trivial durations
    const m = loadMetrics();
    m.studyMs += elapsed;
    saveMetrics(m);
  }
  localStorage.removeItem(key);
}

/**
 * Format accumulated study milliseconds as a human-friendly string.
 * e.g. "0.2h", "3.5h", "12.1h"
 */
export function formatStudyTime(ms) {
  const hours = ms / 3_600_000;
  if (hours < 0.1) return "0h";
  return hours.toFixed(1) + "h";
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

/**
 * Push a new activity entry.
 *  type: "chat" | "sct" | "images"
 *  title: short description
 */
export function pushActivity(type, title) {
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
