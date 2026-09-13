// Tests for the Vercel functions in api/. Run with: npm test (Node built-in runner, no dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { HttpError, requireAdmin, validateSettings } from "../api/_lib.js";
import { startScan } from "../api/scan.js";
import { saveSettings } from "../api/settings.js";

const ENV = { ADMIN_PASSWORD: "correct horse battery", GITHUB_TOKEN: "ghp_test", GITHUB_REPO: "muaz/job-radar" };
const req = (password, body) => ({ headers: password === undefined ? {} : { "x-admin-password": password }, body });
const VALID = {
  locations: ["Bengaluru", "Remote India", "Bengaluru"], job_types: ["Internship"], categories: ["AI/ML"],
  keywords: ["  Python ", "PYTHON", "c++", ""], max_age_days: 30, browser_notifications: true,
};

function fakeGitHub(responses = {}) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, method: init.method, headers: init.headers, body: init.body && JSON.parse(init.body) });
    const key = `${init.method} ${new URL(url).pathname}`;
    const { status = 200, json = {} } = responses[key] ?? {};
    return { ok: status < 400, status, json: async () => json };
  };
  return { calls, fetchImpl };
}

async function rejects(promise, status) {
  await assert.rejects(promise, (e) => e instanceof HttpError && e.status === status);
}

test("password: wrong, missing and unconfigured are refused", async () => {
  await rejects(requireAdmin(req("nope"), ENV, 0), 401);
  await rejects(requireAdmin(req(undefined), ENV, 0), 401);
  await rejects(requireAdmin(req("short"), { ADMIN_PASSWORD: "short" }, 0), 500);
  await requireAdmin(req(ENV.ADMIN_PASSWORD), ENV, 0);
});

test("settings are sanitized like the backend does", () => {
  assert.deepEqual(validateSettings(VALID), {
    locations: ["Bengaluru", "Remote India"], job_types: ["Internship"], categories: ["AI/ML"],
    keywords: ["python", "c++"], max_age_days: 30, browser_notifications: true,
  });
});

test("invalid settings are rejected", () => {
  for (const bad of [
    null, [], { ...VALID, locations: ["Mars"] }, { ...VALID, keywords: ["<script>"] },
    { ...VALID, keywords: ["x".repeat(51)] }, { ...VALID, max_age_days: 0 }, { ...VALID, max_age_days: 1.5 },
    { ...VALID, extra: 1 }, { ...VALID, browser_notifications: "yes" }, { ...VALID, keywords: "python" },
  ]) {
    assert.throws(() => validateSettings(bad), (e) => e.status === 422, JSON.stringify(bad));
  }
});

test("saving settings commits config/settings.json with the current sha", async () => {
  const gh = fakeGitHub({ "GET /repos/muaz/job-radar/contents/config/settings.json": { json: { sha: "abc123" } } });
  const result = await saveSettings(req(ENV.ADMIN_PASSWORD, { settings: VALID }), ENV, gh.fetchImpl);
  assert.equal(result.settings.keywords.length, 2);
  const put = gh.calls.find((c) => c.method === "PUT");
  assert.equal(put.body.sha, "abc123");
  assert.equal(put.body.branch, "main");
  assert.deepEqual(JSON.parse(Buffer.from(put.body.content, "base64").toString("utf8")), result.settings);
  assert.equal(put.headers.Authorization, "Bearer ghp_test");
});

test("nothing is written when the password is wrong or settings are invalid", async () => {
  const gh = fakeGitHub();
  await rejects(saveSettings(req("wrong", { settings: VALID }), ENV, gh.fetchImpl), 401);
  await rejects(saveSettings(req(ENV.ADMIN_PASSWORD, { settings: { locations: ["Mars"] } }), ENV, gh.fetchImpl), 422);
  assert.equal(gh.calls.length, 0);
});

test("scan dispatches the workflow on main", async () => {
  const gh = fakeGitHub({ "POST /repos/muaz/job-radar/actions/workflows/scan.yml/dispatches": { status: 204 } });
  const result = await startScan(req(ENV.ADMIN_PASSWORD), ENV, gh.fetchImpl);
  assert.equal(result.queued, true);
  assert.deepEqual(gh.calls[0].body, { ref: "main" });
});

test("GitHub failures surface as 502 with GitHub's message", async () => {
  const gh = fakeGitHub({
    "POST /repos/muaz/job-radar/actions/workflows/scan.yml/dispatches": { status: 403, json: { message: "Resource not accessible by personal access token" } },
  });
  await assert.rejects(startScan(req(ENV.ADMIN_PASSWORD), ENV, gh.fetchImpl),
    (e) => e.status === 502 && /Resource not accessible/.test(e.message));
});

test("missing GitHub configuration is a clear 500", async () => {
  await rejects(startScan(req(ENV.ADMIN_PASSWORD), { ADMIN_PASSWORD: ENV.ADMIN_PASSWORD }, fakeGitHub().fetchImpl), 500);
});
