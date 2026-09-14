import { useCallback, useEffect, useState } from "react";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";
import { clockTime, dayLabel, safeUrl } from "../services/format";

function StatusPill({ notification: n }) {
  const telegram = n.channel === "telegram";
  const delivered = n.status === "delivered";
  const label = telegram ? (delivered ? "Sent" : "Not sent") : (delivered ? "Shown" : "Pending");
  const title = delivered
    ? `${telegram ? "Sent to Telegram" : "Shown"} at ${clockTime(n.delivered_at)}`
    : telegram
      ? "Telegram delivery failed or isn't set up; the next scan retries. Check the scan logs."
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
      <div className="page-head">
        <div>
          <h1 className="large-title">History</h1>
          <p className="page-sub">{items ? `${items.length.toLocaleString()} alerts` : "Every alert Job Radar has sent"}</p>
        </div>
      </div>

      <ErrorBox error={error} onRetry={load} />
      {!items && !error && <Loading />}
      {items?.length === 0 && (
        <div className="group"><Empty title="No alerts yet">They appear here when a scan finds a new job that matches your filters.</Empty></div>
      )}

      {items && groupByDay(items).map((group, index) => (
        <div key={group.label}>
          <h2 className="section-label" style={index === 0 ? { marginTop: 0 } : undefined}>{group.label}</h2>
          <div className="group">
            {group.items.map((n) => {
              const [title, company] = n.body.split("\n");
              const url = safeUrl(n.url);
              return (
                <div key={n.id} className="row plain">
                  <time className="time">{clockTime(n.created_at)}</time>
                  <div className="job-text">
                    {url
                      ? <a className="job-company history-title" href={url} target="_blank" rel="noopener noreferrer">{title}</a>
                      : <span className="job-company history-title">{title}</span>}
                    <span className="job-meta">{company}</span>
                  </div>
                  <StatusPill notification={n} />
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}
