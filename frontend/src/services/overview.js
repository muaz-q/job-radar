// Summary numbers for the dashboard, derived from job lists (works for both data modes).

const DAY = 24 * 3600 * 1000;

const startOfDay = (time) => {
  const d = new Date(time);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
};

export function buildOverview({ matches, all, generatedAt = null, now = Date.now(), days = 14 }) {
  const today = startOfDay(now);
  const activity = Array.from({ length: days }, (_, i) => ({ day: today - (days - 1 - i) * DAY, count: 0 }));
  const categoryCounts = new Map();
  const companyCounts = new Map();

  for (const job of matches) {
    const seen = startOfDay(new Date(job.first_seen_at).getTime());
    const bucket = activity.find((a) => a.day === seen);
    if (bucket) bucket.count += 1;
    categoryCounts.set(job.category, (categoryCounts.get(job.category) ?? 0) + 1);
  }
  for (const job of all) {
    const entry = companyCounts.get(job.company) ?? { company: job.company, logo_url: job.logo_url, count: 0 };
    entry.count += 1;
    entry.logo_url ||= job.logo_url;
    companyCounts.set(job.company, entry);
  }

  const byCount = (a, b) => b.count - a.count || a.label?.localeCompare?.(b.label);
  return {
    generatedAt,
    matchCount: matches.length,
    internshipCount: matches.filter((j) => j.job_type === "Internship").length,
    matchCompanies: new Set(matches.map((j) => j.company)).size,
    activity,
    categories: [...categoryCounts].map(([label, count]) => ({ label, count })).sort(byCount),
    topCompanies: [...companyCounts.values()].sort((a, b) => b.count - a.count || a.company.localeCompare(b.company)).slice(0, 24),
    matchesList: matches,
  };
}
