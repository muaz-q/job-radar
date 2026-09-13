import { useCallback, useEffect, useState } from "react";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";
import { clockTime, dayLabel, safeUrl } from "../services/format";

function StatusPill({ notification: n }) {
  const telegram = n.channel === "telegram";
  const delivered = n.status === "delivered";
  const label = telegram ? (delivered ? "sent to Telegram" : "not sent yet") : (delivered ? "shown" : "pending");
  const title = delivered
    ? `${telegram ? "Sent" : "Shown"} at ${clockTime(n.delivered_at)}`
    : telegram
      ? "Telegram delivery failed or is not configured; the next scan retries. Check the scan logs."
      : "Not shown yet: open the dashboard with notifications allowed";
  return <span className={`pill ${n.status}`} title={title}>{label}</span>;
}

function groupByDay(notifications) {
  const groups = [];
  for (const n of notifications) {
    const label = dayLabel(n.created_at);
    if (groups.at(-1)?.label !== label) groups.push({ label, items: [] });
    groups.at(-1).items.push(n);
  }
  return groups;
}

export default function NotificationsPage({ refreshKey }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api.listNotifications({ limit: 500 }).then((d) => { setItems(d); setError(null); }).catch(setError);
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  return (
    <section>
      <h2 className="page-title">Notification history</h2>
      <ErrorBox error={error} onRetry={load} />
      {!items && !error && <Loading />}
      {items?.length === 0 && <Empty>No notifications yet. They appear here when a scan finds a new matching job.</Empty>}
      {items && groupByDay(items).map((group) => (
        <div key={group.label} className="day-group">
          <h3 className="day-label">{group.label}</h3>
          {group.items.map((n) => {
            const [title, company] = n.body.split("\n");
            const url = safeUrl(n.url);
            return (
              <div key={n.id} className="history-row">
                <time className="history-time">{clockTime(n.created_at)}</time>
                <span className="history-text">
                  {url ? <a href={url} target="_blank" rel="noopener noreferrer">{title}</a> : title}
                  <span className="muted"> — {company}</span>
                </span>
                <StatusPill notification={n} />
              </div>
            );
          })}
        </div>
      ))}
    </section>
  );
}
