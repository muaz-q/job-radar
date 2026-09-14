import { useState } from "react";

// "New" means new since your previous visit, not "found in the last 24 hours":
// after a big scan nearly every job is under a day old, and a dot on every row means nothing.
// A visit is a session: reloading within 30 minutes keeps the same "new" jobs marked.
const KEY = "job-radar-visits";
const SESSION_GAP = 30 * 60 * 1000;
const DAY = 24 * 3600 * 1000;

function newSince() {
  const now = Date.now();
  try {
    const stored = JSON.parse(window.localStorage.getItem(KEY) || "null");
    const continuing = stored && now - stored.lastSeen < SESSION_GAP;
    const since = continuing ? stored.since : (stored?.lastSeen ?? now - DAY);
    window.localStorage.setItem(KEY, JSON.stringify({ since, lastSeen: now }));
    return since;
  } catch {
    return now - DAY; // no storage: fall back to the last day
  }
}

export function useNewSince() {
  const [since] = useState(newSince);
  return since;
}
