const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

const UNITS = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return null;
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  if (Math.abs(seconds) < 60) return "just now";
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function timeUntil(iso, now = Date.now()) {
  if (!iso) return null;
  const minutes = Math.max(0, Math.round((new Date(iso).getTime() - now) / 60000));
  return minutes < 1 ? "under a minute" : `${minutes} min`;
}

export function clockTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function dayLabel(iso, now = new Date()) {
  const day = new Date(iso);
  const startOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(day)) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return day.toLocaleDateString([], { weekday: "long", day: "numeric", month: "short" });
}

// Job URLs come from third-party sites. Only ever open plain web links.
export function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export function isFresh(iso, hours = 24) {
  return iso && Date.now() - new Date(iso).getTime() < hours * 3600 * 1000;
}
