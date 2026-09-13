// Local mode: the FastAPI backend on this machine, reached through the Vite proxy at /api.
import { ApiError, describeDetail } from "./errors";

const BASE = "/api";
const UNREACHABLE = "Cannot reach the Job Radar backend. Is it running on port 8010?";

async function request(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(UNREACHABLE, 0);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok && data === null && response.status >= 500) {
    // The Vite proxy answers with a bare 5xx when the backend is down.
    throw new ApiError(UNREACHABLE, response.status);
  }
  if (!response.ok) {
    throw new ApiError(describeDetail(data?.detail) ?? `Request failed (HTTP ${response.status})`, response.status);
  }
  return data;
}

function query(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? "?" + new URLSearchParams(entries).toString() : "";
}

export const localApi = {
  mode: "local",
  health: () => request("/health"),
  listJobs: (params = {}) => request("/jobs" + query(params)),
  getJob: (id) => request(`/jobs/${encodeURIComponent(id)}`),
  listSources: () => request("/sources"),
  scan: () => request("/scan", { method: "POST" }),
  getSettings: () => request("/settings"),
  getSettingsOptions: () => request("/settings/options"),
  saveSettings: (settings) => request("/settings", { method: "PUT", body: settings }),
  listNotifications: (params = {}) => request("/notifications" + query(params)),
  markDelivered: (ids) => request("/notifications/mark-delivered", { method: "POST", body: { ids } }),
};
