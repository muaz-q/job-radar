import { useCallback, useEffect, useState } from "react";
import { RevealTitle } from "../components/Motion";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";
import { clockTime, dayLabel, safeUrl } from "../services/format";

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

  const unsent = items?.filter((n) => n.status !== "delivered").length ?? 0;

  return (
    <section>
      <div className="page-head">
        <div>
          <RevealTitle>History</RevealTitle>
          <p className="page-sub">
            {items ? `${items.length.toLocaleString()} alerts sent` : "Every alert Job Radar has sent"}
            {unsent > 0 && ` · ${unsent} waiting to send`}
          </p>
        </div>
      </div>

      <ErrorBox error={error} onRetry={load} />
      {!items && !error && <Loading />}
      {items?.length === 0 && (
        <div className="group"><Empty title="No alerts yet">They appear here when a scan finds a new job that fits your filters.</Empty></div>
      )}

      {items && groupByDay(items).map((group, index) => (
        <div key={group.label}>
          <h2 className="section-label" style={index === 0 ? { marginTop: 0 } : undefined}>{group.label}</h2>
          <div className="group">
            {group.items.map((n) => {
              const [title, company] = n.body.split("\n");
              const url = safeUrl(n.url);
              const waiting = n.status !== "delivered";
              return (
                <div key={n.id} className="row plain">
                  <time className="time" dateTime={n.created_at}>{clockTime(n.created_at)}</time>
                  <div className="job-text">
                    {url
                      ? <a className="history-title" href={url} target="_blank" rel="noopener noreferrer">{title}</a>
                      : <span className="history-title">{title}</span>}
                    <span className="job-sub">{company}</span>
                  </div>
                  {/* Only exceptions are flagged: a normal, delivered alert needs no label. */}
                  {waiting && (
                    <span className="flag" title={n.channel === "telegram"
                      ? "Telegram delivery failed or isn't set up; the next scan retries."
                      : "Not shown yet: open the dashboard with notifications allowed."}>Not sent</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}
