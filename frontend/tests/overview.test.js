// Tests for the dashboard summary numbers (src/services/overview.js).
import assert from "node:assert/strict";
import { test } from "node:test";
import { buildOverview } from "../src/services/overview.js";

const NOW = new Date(2026, 8, 14, 15, 0).getTime();
const at = (daysAgo, hour = 10) => new Date(2026, 8, 14 - daysAgo, hour).toISOString();
const job = (company, category, daysAgo, extra = {}) =>
  ({ company, category, job_type: "Internship", first_seen_at: at(daysAgo), logo_url: null, ...extra });

test("counts matches per day for the last 14 days, ignoring older jobs", () => {
  const matches = [job("A", "AI/ML", 0), job("B", "AI/ML", 0), job("A", "Backend", 3), job("C", "AI/ML", 20)];
  const o = buildOverview({ matches, all: matches, now: NOW });
  assert.equal(o.activity.length, 14);
  assert.equal(o.activity[13].count, 2); // today
  assert.equal(o.activity[10].count, 1); // three days ago
  assert.equal(o.activity.reduce((n, a) => n + a.count, 0), 3);
});

test("categories are sorted largest first and companies are counted across all jobs", () => {
  const matches = [job("A", "AI/ML", 0), job("B", "AI/ML", 1), job("A", "Backend", 2, { job_type: "Full-time" })];
  const all = [...matches, job("Z", "Backend", 1, { logo_url: "z.png" }), job("Z", "Backend", 2), job("Z", "AI/ML", 2)];
  const o = buildOverview({ matches, all, now: NOW });
  assert.deepEqual(o.categories, [{ label: "AI/ML", count: 2 }, { label: "Backend", count: 1 }]);
  assert.equal(o.matchCount, 3);
  assert.equal(o.internshipCount, 2);
  assert.equal(o.matchCompanies, 2);
  assert.deepEqual(o.topCompanies[0], { company: "Z", logo_url: "z.png", count: 3 });
});
