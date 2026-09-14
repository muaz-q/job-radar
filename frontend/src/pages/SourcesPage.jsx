import { useCallback, useEffect, useState } from "react";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api, GITHUB_REPO, HOSTED } from "../services/api";
import { timeAgo, timeUntil } from "../services/format";

const STATUS_TEXT = {
  ok: "Active",
  running: "Scanning",
  warning: "Active, with problems",
  error: "Last scan failed",
  idle: "Not scanned yet",
};

export default function SourcesPage({ refreshKey }) {
  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api.listSources().then((data) => { setSources(data); setError(null); }).catch(setError);
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15_000);
    return () => clearInterval(timer);
  }, [load, refreshKey]);

  return (
    <section>
      <div className="page-head">
        <div>
          <h1 className="large-title">Sources</h1>
          <p className="page-sub">{HOSTED ? "Checked every hour on GitHub" : "Checked by this computer"}</p>
        </div>
      </div>

      <ErrorBox error={error} onRetry={load} />
      {!sources && !error && <Loading />}
      {sources?.length === 0 && <div className="group"><Empty title="No sources">Enable a source in config/sources.json.</Empty></div>}

      <div className="tiles">
        {sources?.map((s) => {
          const status = s.status in STATUS_TEXT ? s.status : "idle";
          const retry = status === "error"
            ? (HOSTED ? " · retrying next hour" : s.next_scan_at ? ` · retrying in ${timeUntil(s.next_scan_at)}` : "")
            : "";
          return (
            <article key={s.name} className="tile">
              <div>
                <h3>{s.display_name}</h3>
                <span className={`status ${status}`}>{STATUS_TEXT[status]}{retry}</span>
              </div>
              <div className="big-number">
                {s.total_jobs.toLocaleString()}
                <small>jobs tracked</small>
              </div>
              <div className="tile-meta">
                Checked {s.last_checked_at ? timeAgo(s.last_checked_at) : "never"}
                <br />
                Last scan: {s.last_fetched_count.toLocaleString()} fetched, {s.last_new_count.toLocaleString()} new
                {s.next_scan_at && <><br />Next scan {HOSTED ? "about " : ""}in {timeUntil(s.next_scan_at)}</>}
                {s.consecutive_failures > 0 && <><br />{s.consecutive_failures} failed scans in a row</>}
              </div>
              {s.last_error && <div className="tile-error">{s.last_error}</div>}
            </article>
          );
        })}
      </div>

      {HOSTED && (
        <p className="footnote">
          GitHub can start hourly scans up to ~30 minutes late.{" "}
          <a href={`https://github.com/${GITHUB_REPO}/actions/workflows/scan.yml`} target="_blank" rel="noopener noreferrer">
            Scan runs and logs
          </a>
        </p>
      )}
    </section>
  );
}
