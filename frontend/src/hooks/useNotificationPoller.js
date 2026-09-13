import { useCallback, useEffect, useRef, useState } from "react";
import { api, HOSTED } from "../services/api";
import { safeUrl } from "../services/format";

// Local mode: the backend stores alerts as "pending". While the dashboard is open, this
// hook polls for them, shows browser notifications, and marks them delivered.
//
// Hosted mode: Telegram is the real alert channel. This hook only adds a browser popup for
// alerts newer than the last one this browser has seen (the first visit just records a
// starting point, so opening the dashboard never dumps old alerts).
//
// A burst (e.g. the very first scan, or reopening the tab after hours) becomes ONE
// summary notification instead of dozens of popups. Every alert is still in the history.

const POLL_MS = HOSTED ? 5 * 60_000 : 30_000;
const MAX_INDIVIDUAL = 3;
const LAST_SEEN_KEY = "job-radar-last-notification-id";

function readLastSeen() {
  try {
    const value = window.localStorage.getItem(LAST_SEEN_KEY);
    return value === null ? null : Number(value);
  } catch {
    return null;
  }
}

function writeLastSeen(id) {
  try {
    window.localStorage.setItem(LAST_SEEN_KEY, String(id));
  } catch {
    // private window etc.: popups may repeat after a reload, nothing worse
  }
}

async function fetchUnshown() {
  if (!HOSTED) return api.listNotifications({ status: "pending", limit: 200 });
  const recent = await api.listNotifications({ limit: 200 });
  const newestId = Math.max(0, ...recent.map((n) => n.id));
  const lastSeen = readLastSeen();
  if (lastSeen === null) {
    writeLastSeen(newestId);
    return [];
  }
  return recent.filter((n) => n.id > lastSeen);
}

async function markShown(shown) {
  if (HOSTED) writeLastSeen(Math.max(...shown.map((n) => n.id)));
  else await api.markDelivered(shown.map((n) => n.id));
}

const supported = typeof window !== "undefined" && "Notification" in window;

function showJobNotification(n) {
  const notification = new Notification(n.heading, { body: n.body, tag: `job-radar-${n.id}` });
  notification.onclick = () => {
    const url = safeUrl(n.url);
    if (url) window.open(url, "_blank", "noopener,noreferrer");
    notification.close();
  };
}

function showSummaryNotification(pending) {
  const titles = pending.slice(0, 3).map((n) => n.body.split("\n")[0]);
  const more = pending.length > 3 ? `\n+${pending.length - 3} more` : "";
  const notification = new Notification(`${pending.length} new jobs`, {
    body: titles.join("\n") + more,
    tag: `job-radar-summary-${pending[0].id}`,
  });
  notification.onclick = () => {
    window.focus();
    window.location.hash = "#/";
    notification.close();
  };
}

export function useNotificationPoller({ onNewAlerts } = {}) {
  const [permission, setPermission] = useState(supported ? Notification.permission : "unsupported");
  const busy = useRef(false);
  const onNewAlertsRef = useRef(onNewAlerts);
  onNewAlertsRef.current = onNewAlerts;

  const poll = useCallback(async () => {
    if (!supported || Notification.permission !== "granted" || busy.current) return;
    busy.current = true;
    try {
      const pending = await fetchUnshown();
      if (pending.length === 0) return;
      if (pending.length <= MAX_INDIVIDUAL) pending.forEach(showJobNotification);
      else showSummaryNotification(pending);
      await markShown(pending);
      onNewAlertsRef.current?.(pending);
    } catch (error) {
      console.warn("Notification poll failed; will retry.", error);
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    poll();
    const timer = setInterval(poll, POLL_MS);
    return () => clearInterval(timer);
  }, [poll, permission]);

  const requestPermission = useCallback(async () => {
    if (!supported) return "unsupported";
    const result = await Notification.requestPermission();
    setPermission(result);
    return result;
  }, []);

  const sendTest = useCallback(() => {
    if (permission !== "granted") return false;
    const n = new Notification("Job Radar test", { body: "Browser notifications are working.", tag: "job-radar-test" });
    n.onclick = () => { window.focus(); n.close(); };
    return true;
  }, [permission]);

  return { permission, requestPermission, poll, sendTest };
}
