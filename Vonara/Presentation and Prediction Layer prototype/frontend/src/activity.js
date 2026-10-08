// Questions asked in this browser, for the Dashboard and Activity pages. Kept
// in memory and mirrored to localStorage when it is available; the API itself
// keeps no history, so nothing here is shared between users or devices.

import { useSyncExternalStore } from "react";

const KEY = "c4-activity";
const LIMIT = 100;
const listeners = new Set();
let entries = load();

function load() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // storage unavailable: the log lasts for this page only
  }
  listeners.forEach((fn) => fn());
}

/** One answered question, summarised from its envelope (nothing recomputed). */
export function record(question, dataset, envelope) {
  const response = envelope.response || {};
  const notice = response.forecast_notice;
  entries = [{
    at: new Date().toISOString(),
    question,
    source: dataset ? dataset.title : "",
    sourceId: dataset ? dataset.id : "",
    shape: response.response_intent?.intent || "",
    headline: response.answer?.display_value || "",
    forecast: notice ? notice.status : "",
    ms: Math.round(envelope.profiling?.total_execution_ms ?? 0),
    cached: Boolean(envelope.cache?.hit),
  }, ...entries].slice(0, LIMIT);
  save();
}

export function clearActivity() {
  entries = [];
  save();
}

function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useActivity() {
  return useSyncExternalStore(subscribe, () => entries, () => entries);
}

export function timeAgo(iso, now = Date.now()) {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}
