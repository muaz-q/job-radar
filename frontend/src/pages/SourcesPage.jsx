import { useCallback, useEffect, useState } from "react";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api, GITHUB_REPO, HOSTED } from "../services/api";
import { timeAgo, timeUntil } from "../services/format";

function StatusLine({ source }) {
  const retry = HOSTED
    ? "Retrying at the next hourly scan"
    : source.next_scan_at ? `Retrying in ${timeUntil(source.next_scan_at)}` : "Retry with Scan now";
  switch (source.status) {
    case "ok":
      return <div className="status ok">● Active</div>;
    case "running":
      return <div className="status running">● Scanning…</div>;
    case "warning":
      return <div className="status warning">● Active, with problems</div>;
    case "error":
      return <div className="status error">⚠ Last scan failed · {retry}</div>;
    default:
      return <div className="status idle">○ Not scanned yet</div>;
  }
}

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
      <h2 className="page-title">Sources</h2>
      <ErrorBox error={error} onRetry={load} />
      {!sources && !error && <Loading />}
      {sources?.length === 0 && <Empty>No sources configured. Set ENABLED_SOURCES in backend/.env.</Empty>}
      {sources?.map((s) => (
        <article key={s.name} className="source-card">
          <div className="source-head">
            <h3>{s.display_name}</h3>
            {!s.enabled && <span className="tag subtle">disabled</span>}
          </div>
          <StatusLine source={s} />
          <dl className="facts">
            <dt>Last checked</dt><dd>{s.last_checked_at ? timeAgo(s.last_checked_at) : "never"}</dd>
            <dt>Jobs found</dt><dd>{s.total_jobs}</dd>
            <dt>Last scan</dt><dd>{s.last_fetched_count} fetched, {s.last_new_count} new</dd>
            {s.next_scan_at && <><dt>Next scan</dt><dd>{HOSTED ? "about " : ""}in {timeUntil(s.next_scan_at)}</dd></>}
            {s.consecutive_failures > 0 && <><dt>Failures in a row</dt><dd>{s.consecutive_failures}</dd></>}
          </dl>
          {s.last_error && <pre className="source-error">{s.last_error}</pre>}
        </article>
      ))}
      {HOSTED && (
        <p className="hint">
          Scans run hourly on GitHub Actions, which can start them up to ~30 minutes late.{" "}
          <a href={`https://github.com/${GITHUB_REPO}/actions/workflows/scan.yml`} target="_blank" rel="noopener noreferrer">
            See scan runs and logs →
          </a>
        </p>
      )}
    </section>
  );
}
