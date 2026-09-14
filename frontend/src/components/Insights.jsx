import { memo, useState } from "react";
import CompanyLogo from "./CompanyLogo";
import { CountUp } from "./Motion";

const dayName = (time) => new Date(time).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });

/** A headline number with a short label (not a chart: the number is the point). */
export function StatTile({ label, value, detail, accent }) {
  return (
    <div className={accent ? "stat accent" : "stat"}>
      <div className="stat-value">{typeof value === "number" ? <CountUp value={value} /> : value}</div>
      <div className="stat-label">{label}</div>
      {detail && <div className="stat-detail">{detail}</div>}
    </div>
  );
}

/**
 * New matching jobs per day, last 14 days. One series, so one colour and no legend (the card title
 * names it). Bars are anchored to the baseline with rounded tops; hovering or focusing a day shows
 * its exact count. A visually hidden table carries the same data for screen readers.
 */
export const ActivityChart = memo(function ActivityChart({ activity }) {
  const [active, setActive] = useState(null);
  const max = Math.max(1, ...activity.map((a) => a.count));
  const peak = activity.reduce((best, a) => (a.count > best.count ? a : best), activity[0]);
  const total = activity.reduce((n, a) => n + a.count, 0);
  const shown = active ?? activity[activity.length - 1];

  return (
    <section className="card insight" aria-labelledby="activity-title">
      <div className="insight-head">
        <h2 id="activity-title">Activity</h2>
        <span className="insight-sub">last 14 days</span>
      </div>
      <p className="insight-figure">
        <span className="insight-number">{total.toLocaleString()}</span> matches found
      </p>
      <div className="bars" onMouseLeave={() => setActive(null)}>
        {activity.map((a) => (
          <button key={a.day} type="button" className={a === shown ? "bar-slot on" : "bar-slot"}
                  onMouseEnter={() => setActive(a)} onFocus={() => setActive(a)} onBlur={() => setActive(null)}
                  aria-label={`${dayName(a.day)}: ${a.count} new ${a.count === 1 ? "match" : "matches"}`}>
            <span className="bar" style={{ height: `${Math.max(a.count ? 8 : 2, (a.count / max) * 100)}%` }} />
          </button>
        ))}
      </div>
      <div className="bars-foot" aria-live="polite">
        <span>{dayName(shown.day)}</span>
        <span className="bars-value">{shown.count} {shown.count === 1 ? "match" : "matches"}</span>
      </div>
      {peak.count > 0 && <p className="insight-note">Busiest day: {dayName(peak.day)} with {peak.count}</p>}
      <table className="visually-hidden">
        <caption>New matching jobs per day</caption>
        <tbody>{activity.map((a) => <tr key={a.day}><th scope="row">{dayName(a.day)}</th><td>{a.count}</td></tr>)}</tbody>
      </table>
    </section>
  );
});

/** Matches by category: single-hue horizontal bars, values in text colours, sorted largest first. */
export const CategoryBars = memo(function CategoryBars({ categories, total }) {
  const max = Math.max(1, ...categories.map((c) => c.count));
  return (
    <section className="card insight" aria-labelledby="category-title">
      <div className="insight-head">
        <h2 id="category-title">By category</h2>
        <span className="insight-sub">{total.toLocaleString()} matches</span>
      </div>
      {categories.length === 0 && <p className="insight-note">No matches yet.</p>}
      <ul className="hbars">
        {categories.slice(0, 6).map((c) => (
          <li key={c.label} title={`${c.label}: ${c.count}`}>
            <div className="hbar-labels"><span>{c.label}</span><span className="hbar-value">{c.count}</span></div>
            <div className="hbar-track"><span className="hbar" style={{ width: `${(c.count / max) * 100}%` }} /></div>
          </li>
        ))}
      </ul>
    </section>
  );
});

export const TopCompanies = memo(function TopCompanies({ companies, title = "Hiring now", limit = 6 }) {
  return (
    <section className="card insight" aria-labelledby="companies-title">
      <div className="insight-head">
        <h2 id="companies-title">{title}</h2>
        <span className="insight-sub">by open roles</span>
      </div>
      <ul className="company-list">
        {companies.slice(0, limit).map((c) => (
          <li key={c.company}>
            <CompanyLogo company={c.company} url={c.logo_url} size={32} />
            <span className="company-name">{c.company}</span>
            <span className="company-count">{c.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
});

export function greeting(now = new Date()) {
  const hour = now.getHours();
  return hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}
