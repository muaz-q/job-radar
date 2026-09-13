// Shared code for the Vercel functions. Files starting with "_" are not deployed as routes.
//
// Environment variables (set in the Vercel project):
//   GITHUB_TOKEN    fine-grained token for ONE repo: Contents read/write + Actions read/write
//   GITHUB_REPO     "owner/repo"
//   ADMIN_PASSWORD  at least 12 characters; required to save settings or start a scan
import { createHash, timingSafeEqual } from "node:crypto";
import { OPTIONS } from "./_options.js";

export const MIN_PASSWORD_LENGTH = 12;
const KEYWORD_ALLOWED = /^[\p{L}\p{N}_\s+#./-]+$/u;
const SETTINGS_KEYS = ["locations", "job_types", "categories", "keywords", "max_age_days", "browser_notifications"];

export class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

const digest = (text) => createHash("sha256").update(String(text)).digest();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function requireAdmin(req, env = process.env, delayMs = 1000) {
  const expected = env.ADMIN_PASSWORD ?? "";
  if (expected.length < MIN_PASSWORD_LENGTH) {
    throw new HttpError(500, `ADMIN_PASSWORD is not set (or shorter than ${MIN_PASSWORD_LENGTH} characters) in Vercel.`);
  }
  const given = req.headers["x-admin-password"] ?? "";
  // Compare fixed-length digests so timing does not reveal the password.
  if (!timingSafeEqual(digest(given), digest(expected))) {
    await sleep(delayMs); // slows down guessing
    throw new HttpError(401, "Wrong password.");
  }
}

export function requireRepoConfig(env = process.env) {
  const { GITHUB_TOKEN: token, GITHUB_REPO: repo } = env;
  if (!token || !repo || !/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    throw new HttpError(500, "GITHUB_TOKEN and GITHUB_REPO (owner/repo) must be set in Vercel.");
  }
  return { token, repo };
}

export async function github(path, { token, method = "GET", body, fetchImpl = fetch } = {}) {
  const response = await fetchImpl(`https://api.github.com${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "job-radar-dashboard",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.json().then((d) => d.message).catch(() => "");
    throw new HttpError(502, `GitHub API ${method} ${path.split("?")[0]} failed: HTTP ${response.status} ${detail}`.trim());
  }
  return response.status === 204 ? null : response.json();
}

function pickOptions(value, allowed, field) {
  if (!Array.isArray(value)) throw new HttpError(422, `${field} must be a list`);
  for (const item of value) {
    if (!allowed.includes(item)) throw new HttpError(422, `${field}: "${String(item).slice(0, 40)}" is not an allowed value`);
  }
  return [...new Set(value)];
}

// Mirrors backend/app/schemas.py SettingsIn. The Python scanner validates again before using it.
export function validateSettings(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new HttpError(422, "settings must be an object");
  const unknown = Object.keys(input).filter((k) => !SETTINGS_KEYS.includes(k));
  if (unknown.length) throw new HttpError(422, `unknown field(s): ${unknown.join(", ")}`);

  const keywords = [];
  if (!Array.isArray(input.keywords ?? [])) throw new HttpError(422, "keywords must be a list");
  for (const raw of input.keywords ?? []) {
    if (typeof raw !== "string") throw new HttpError(422, "keywords must be text");
    const keyword = raw.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
    if (!keyword) continue;
    if (keyword.length > 50) throw new HttpError(422, `keyword longer than 50 characters: ${keyword.slice(0, 20)}...`);
    if (!KEYWORD_ALLOWED.test(keyword)) throw new HttpError(422, `keyword contains unsupported characters: ${keyword}`);
    if (!keywords.includes(keyword)) keywords.push(keyword);
  }
  if (keywords.length > 50) throw new HttpError(422, "at most 50 keywords");

  const age = input.max_age_days ?? null;
  if (age !== null && !(Number.isInteger(age) && age >= 1 && age <= 365)) {
    throw new HttpError(422, "max_age_days must be empty or a whole number from 1 to 365");
  }
  if (typeof (input.browser_notifications ?? true) !== "boolean") {
    throw new HttpError(422, "browser_notifications must be true or false");
  }
  return {
    locations: pickOptions(input.locations ?? [], OPTIONS.locations, "locations"),
    job_types: pickOptions(input.job_types ?? [], OPTIONS.job_types, "job_types"),
    categories: pickOptions(input.categories ?? [], OPTIONS.categories, "categories"),
    keywords,
    max_age_days: age,
    browser_notifications: input.browser_notifications ?? true,
  };
}

export function handler(work) {
  return async (req, res) => {
    try {
      if (req.method !== "POST") throw new HttpError(405, "Use POST.");
      const body = await work(req);
      sendJson(res, 200, body);
    } catch (error) {
      const status = error instanceof HttpError ? error.status : 500;
      if (status >= 500) console.error(error);
      sendJson(res, status, { detail: error instanceof HttpError ? error.message : "Unexpected server error." });
    }
  };
}
