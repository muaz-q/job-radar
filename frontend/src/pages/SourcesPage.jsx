import { useCallback, useEffect, useState } from "react";
import CompanyLogo from "../components/CompanyLogo";
import { CountUp, RevealTitle } from "../components/Motion";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api, GITHUB_REPO, HOSTED } from "../services/api";
import { timeAgo } from "../services/format";

const STATUS_TEXT = { ok: "Working", running: "Scanning", warning: "Partly working", error: "Not working", idle: "Waiting for first scan" };

export default function SourcesPage({ refreshKey }) {
  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [companies, setCompanies] = useState([]);
  useEffect(() => { api.overview().then((o) => setCompanies(o.topCompanies)).catch(() => {}); }, [refreshKey]);

  const load = useCallback(() => {
    api.listSources().then((data) => { setSources(data); setError(null); }).catch(setError);
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15_000);
    return () => clearInterval(timer);
  }, [load, refreshKey]);

  const lastChecked = sources?.map((s) => s.last_checked_at).filter(Boolean).sort().at(-1);

  return (
    <section>
      <div className="page-head">
        <div>
          <RevealTitle>Sources</RevealTitle>
          <p className="page-sub">
            {lastChecked ? `Checked ${timeAgo(lastChecked)}` : "Not checked yet"}
            {HOSTED && " · every hour"}
          </p>
        </div>
      </div>

      <ErrorBox error={error} onRetry={load} />
      {!sources && !error && <Loading />}
      {sources?.length === 0 && <div className="group"><Empty title="No sources">Enable one in config/sources.json.</Empty></div>}

      <div className="tiles">
        {sources?.map((s, index) => {
          const status = s.status in STATUS_TEXT ? s.status : "idle";
          return (
            <article key={s.name} className="tile enter" style={{ "--i": index }}>
              <div className="tile-head">
                <h3>{s.display_name}</h3>
                <span className={`status-dot ${status}`} title={STATUS_TEXT[status]} />
              </div>
              <div>
                <div className="big-number"><CountUp value={s.total_jobs} /></div>
                <div className="tile-meta">jobs tracked</div>
              </div>
              {/* Healthy sources say nothing more; problems say exactly what is wrong. */}
              {status === "ok" && <div className="tile-meta">{s.last_new_count > 0 ? `${s.last_new_count} new in the last scan` : "Nothing new in the last scan"}</div>}
              {status === "idle" && <div className="tile-meta">{STATUS_TEXT.idle}</div>}
              {status === "running" && <div className="tile-meta">{STATUS_TEXT.running}…</div>}
              {(status === "warning" || status === "error") && (
                <div className={status === "error" ? "tile-meta bad" : "tile-meta warn"}>
                  {STATUS_TEXT[status]}{s.consecutive_failures > 1 ? ` · ${s.consecutive_failures} scans in a row` : ""}
                  {s.last_error && <><br /><span className="muted">{s.last_error}</span></>}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {companies.length > 0 && (
        <>
          <h2 className="section-label">Companies in your feed</h2>
          <ul className="logo-wall">
            {companies.map((c, index) => (
              <li key={c.company} className="logo-cell enter" style={{ "--i": Math.min(index, 13) }} title={`${c.company}: ${c.count} open roles`}>
                <CompanyLogo company={c.company} url={c.logo_url} size={40} />
                <span className="logo-name">{c.company}</span>
                <span className="logo-count">{c.count} roles</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {HOSTED && (
        <p className="footnote">
          Scans run on GitHub and can start a little late.{" "}
          <a href={`https://github.com/${GITHUB_REPO}/actions/workflows/scan.yml`} target="_blank" rel="noopener noreferrer">View scan logs</a>
        </p>
      )}
    </section>
  );
}
