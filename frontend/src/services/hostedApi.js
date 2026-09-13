// Hosted mode (Vercel): no backend server.
//   Reads:  JSON files the GitHub Actions scanner publishes on the repo's `data` branch.
//   Writes: the password-protected Vercel functions in /api (save settings, start a scan).
// Filter matching is precomputed by the Python scanner, so no filter rules are duplicated here.
import { ApiError, describeDetail } from "./errors";

export const REPO = import.meta.env.VITE_GITHUB_REPO;
const DATA_BASE = (import.meta.env.VITE_DATA_BASE_URL || `https://raw.githubusercontent.com/${REPO}/data/public`)
  .replace(/\/$/, "");
const CACHE_MS = 60_000;
const PASSWORD_KEY = "job-radar-admin-password";

const cache = new Map();

async function loadJson(name) {
  const hit = cache.get(name);
  if (hit && Date.now() - hit.at < CACHE_MS) return hit.data;
  let response;
  try {
    response = await fetch(`${DATA_BASE}/${name}`, { cache: "no-store" });
  } catch {
    throw new ApiError("Cannot load job data from GitHub. Check your internet connection.", 0);
  }
  if (response.status === 404) {
    throw new ApiError("No scan results published yet. The first GitHub scan may still be running.", 404);
  }
  if (!response.ok) throw new ApiError(`Loading ${name} failed (HTTP ${response.status}).`, response.status);
  const data = await response.json();
  cache.set(name, { at: Date.now(), data });
  return data;
}

function storage() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

async function adminPost(path, body) {
  let password = storage()?.getItem(PASSWORD_KEY);
  if (!password) {
    password = window.prompt("Admin password (set as ADMIN_PASSWORD in Vercel):");
    if (!password) throw new ApiError("Cancelled: the admin password is needed for this.", 0);
  }
  let response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-admin-password": password },
      body: JSON.stringify(body ?? {}),
    });
  } catch {
    throw new ApiError("Cannot reach the dashboard server.", 0);
  }
  const data = await response.json().catch(() => null);
  if (response.status === 401) {
    storage()?.removeItem(PASSWORD_KEY);
  } else if (response.ok) {
    storage()?.setItem(PASSWORD_KEY, password); // remembered for this browser tab only
  }
  if (!response.ok) {
    throw new ApiError(describeDetail(data?.detail) ?? `Request failed (HTTP ${response.status})`, response.status);
  }
  return data;
}

const text = (value) => (value ?? "").toLowerCase();

export const hostedApi = {
  mode: "hosted",

  async health() {
    const meta = await loadJson("meta.json");
    return { status: "ok", generated_at: meta.generated_at };
  },

  async listJobs(params = {}) {
    const { jobs } = await loadJson("jobs.json");
    const q = text(params.q).trim();
    const matching = jobs.filter((job) =>
      (!params.source || job.source === params.source)
      && (!params.category || job.category === params.category)
      && (!params.job_type || job.job_type === params.job_type)
      && (!params.location || job.location_tags.includes(params.location))
      && (!q || text(job.title).includes(q) || text(job.company).includes(q))
      && (params.matching !== "true" || job.matches_filters));
    const offset = Number(params.offset ?? 0);
    const limit = Number(params.limit ?? 50);
    return { total: matching.length, items: matching.slice(offset, offset + limit) };
  },

  async getJob(id) {
    const { jobs } = await loadJson("jobs.json");
    const job = jobs.find((j) => String(j.id) === String(id));
    if (!job) throw new ApiError("This job is no longer in the dashboard data (older than 60 days).", 404);
    return job;
  },

  listSources: () => loadJson("sources.json"),

  async getSettingsOptions() {
    return (await loadJson("meta.json")).options;
  },

  async getSettings() {
    // The committed file on main is the source of truth (it may be newer than the last scan).
    try {
      const response = await fetch(`https://api.github.com/repos/${REPO}/contents/config/settings.json?ref=main`, {
        headers: { Accept: "application/vnd.github.raw+json" },
        cache: "no-store",
      });
      if (response.ok) return await response.json();
    } catch {
      // fall through to the settings the last scan used
    }
    return (await loadJson("meta.json")).settings;
  },

  async saveSettings(settings) {
    const result = await adminPost("/api/settings", { settings });
    cache.clear();
    return { ...result.settings, detail: result.detail };
  },

  async scan() {
    return adminPost("/api/scan");
  },

  async listNotifications({ status, limit = 200 } = {}) {
    const all = await loadJson("notifications.json");
    return all.filter((n) => !status || n.status === status).slice(0, Number(limit));
  },

  // Delivery state belongs to the GitHub scanner; the dashboard never writes it.
  markDelivered: async () => ({ updated: 0 }),
};
