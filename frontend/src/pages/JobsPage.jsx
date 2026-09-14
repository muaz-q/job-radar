import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FilterIcon, SearchIcon, XIcon } from "../components/Icons";
import { ActivityChart, CategoryBars, greeting, StatTile, TopCompanies } from "../components/Insights";
import JobRow from "../components/JobCard";
import { RevealTitle, Segmented } from "../components/Motion";
import { Empty, ErrorBox, SkeletonList } from "../components/Status";
import { api } from "../services/api";
import { timeAgo } from "../services/format";

const PAGE_SIZE = 50;
const WEEK = 7 * 24 * 3600 * 1000;
const FILTER_KEYS = [
  { key: "source", label: "Any source", optionsKey: "sources" },
  { key: "location", label: "Any location", optionsKey: "locations" },
  { key: "category", label: "Any category", optionsKey: "categories" },
];

function useDebounced(value, ms = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

// Break the list into "new since your last visit", "this week" and "earlier": rhythm instead of one long slab.
function groupJobs(items, newSince, now = Date.now()) {
  const groups = [
    { key: "new", label: "New since your last visit", items: [] },
    { key: "week", label: "This week", items: [] },
    { key: "earlier", label: "Earlier", items: [] },
  ];
  for (const job of items) {
    const seen = new Date(job.first_seen_at).getTime();
    groups[seen > newSince ? 0 : now - seen < WEEK ? 1 : 2].items.push(job);
  }
  return groups.filter((g) => g.items.length > 0);
}

export default function JobsPage({ refreshKey, newSince }) {
  const [view, setView] = useState("matching");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ source: "", location: "", category: "" });
  const [showFilters, setShowFilters] = useState(false);
  const [options, setOptions] = useState({ sources: [], locations: [], categories: [] });
  const [jobs, setJobs] = useState({ items: [], total: 0 });
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastScan, setLastScan] = useState(null);
  const q = useDebounced(search);

  useEffect(() => {
    api.health().then((h) => setLastScan(h.generated_at ?? null)).catch(() => {});
    api.overview().then(setOverview).catch(() => {}); // the list shows any connection error
  }, [refreshKey]);

  useEffect(() => {
    Promise.all([api.listSources(), api.getSettingsOptions()])
      .then(([sources, opts]) => setOptions({
        sources: sources.map((s) => ({ value: s.name, label: s.display_name })),
        locations: opts.locations.map((l) => ({ value: l, label: l })),
        categories: opts.categories.map((c) => ({ value: c, label: c })),
      }))
      .catch(() => {});
  }, [refreshKey]);

  const params = { ...filters, q, matching: view === "matching" ? "true" : undefined };
  const paramsKey = JSON.stringify(params);

  const latestRequest = useRef(0);
  const load = useCallback(async (offset = 0) => {
    const requestId = ++latestRequest.current;
    const isStale = () => requestId !== latestRequest.current; // typing fast: ignore older responses
    setLoading(true);
    setError(null);
    try {
      const page = await api.listJobs({ ...JSON.parse(paramsKey), limit: PAGE_SIZE, offset });
      if (isStale()) return;
      setJobs((prev) => (offset === 0 ? page : { total: page.total, items: [...prev.items, ...page.items] }));
    } catch (err) {
      if (!isStale()) setError(err);
    } finally {
      if (!isStale()) setLoading(false);
    }
  }, [paramsKey]);

  useEffect(() => { load(0); }, [load, refreshKey]);

  const setFilter = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  const active = FILTER_KEYS.filter(({ key }) => filters[key]);
  const labelFor = (key, optionsKey) => options[optionsKey].find((o) => o.value === filters[key])?.label ?? filters[key];
  const anyFilter = q || active.length > 0;
  const groups = useMemo(() => groupJobs(jobs.items, newSince), [jobs.items, newSince]);
  const newMatches = useMemo(
    () => overview?.matchesList.filter((j) => new Date(j.first_seen_at).getTime() > newSince).length ?? 0,
    [overview, newSince],
  );

  const headline = overview
    ? newMatches > 0
      ? `${newMatches} new ${newMatches === 1 ? "match" : "matches"} since your last visit.`
      : "Nothing new since your last visit. You're all caught up."
    : "Loading your matches…";

  let rowIndex = 0;

  return (
    <section>
      <header className="hero">
        <p className="eyebrow">{greeting()}</p>
        <RevealTitle>Jobs</RevealTitle>
        <p className="hero-line">{headline}</p>
      </header>

      <div className="stats">
        <StatTile label="New since last visit" value={overview ? newMatches : "–"} accent detail="Marked with a dot below" />
        <StatTile label="Matching your filters" value={overview ? overview.matchCount : "–"}
                  detail={overview ? `${overview.internshipCount} ${overview.internshipCount === 1 ? "internship" : "internships"}` : undefined} />
        <StatTile label="Companies hiring" value={overview ? overview.matchCompanies : "–"} detail="With roles that match" />
        <StatTile label="Last scan" value={lastScan ? timeAgo(lastScan) : "–"} detail={lastScan ? "Scans every hour" : undefined} />
      </div>

      <div className="columns">
        <div className="main-col">
          <div className="list-head">
            <Segmented label="Which jobs" value={view} onChange={setView} options={[["matching", "Matches"], ["all", "All jobs"]]} />
            <span className="list-count">{jobs.total.toLocaleString()} {jobs.total === 1 ? "job" : "jobs"}</span>
          </div>

          <div className="toolbar">
            <label className="search">
              <SearchIcon />
              <input id="job-search" className="field" type="search" placeholder="Search title or company"
                     value={search} maxLength={100} onChange={(e) => setSearch(e.target.value)} aria-label="Search title or company" />
            </label>
            <button className="btn filter-toggle" onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters} aria-controls="filter-panel">
              <FilterIcon />
              <span>Filters</span>
              {active.length > 0 && <span className="count">{active.length}</span>}
            </button>
          </div>

          {/* Always rendered so it can expand and collapse smoothly; inert while closed */}
          <div className={showFilters ? "collapse open" : "collapse"} inert={showFilters ? undefined : ""}>
            <div id="filter-panel" className="panel">
              {FILTER_KEYS.map(({ key, label, optionsKey }) => (
                <select key={key} id={`filter-${key}`} className="menu" value={filters[key]} aria-label={label}
                        onChange={(e) => setFilter(key, e.target.value)}>
                  <option value="">{label}</option>
                  {options[optionsKey].map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ))}
            </div>
          </div>
          {!showFilters && active.length > 0 && (
            <div className="chips">
              {active.map(({ key, optionsKey }) => (
                <button key={key} className="chip" onClick={() => setFilter(key, "")} aria-label={`Remove filter ${labelFor(key, optionsKey)}`}>
                  {labelFor(key, optionsKey)} <XIcon />
                </button>
              ))}
            </div>
          )}

          <ErrorBox error={error} onRetry={() => load(0)} />

          {groups.map((group, i) => (
            <div key={group.key} className="list-group">
              <h2 className="section-label">{group.label} {(i < groups.length - 1 || jobs.items.length >= jobs.total) && <span className="section-count">{group.items.length}</span>}</h2>
              <div className="group">
                {group.items.map((job) => {
                  const index = rowIndex++;
                  return <JobRow key={job.id} job={job} isNew={group.key === "new"} index={index} />;
                })}
              </div>
            </div>
          ))}

          {loading && jobs.items.length === 0 && <SkeletonList />}
          {!loading && !error && jobs.items.length === 0 && (
            <div className="group">
              {anyFilter
                ? <Empty title="No results">Try a different search or remove a filter.</Empty>
                : view === "matching"
                  ? <Empty title="No matches yet">Nothing fits your filters. Adjust them in <a href="#/settings">Settings</a>, or browse All jobs.</Empty>
                  : <Empty title="No jobs yet">They'll appear here after the next scan.</Empty>}
            </div>
          )}
          {jobs.items.length > 0 && jobs.items.length < jobs.total && (
            <div className="center">
              <button className="btn" onClick={() => load(jobs.items.length)} disabled={loading}>
                {loading ? "Loading…" : "Show More"}
              </button>
            </div>
          )}
        </div>

        <aside className="side-col" aria-label="Insights">
          {overview ? (
            <>
              <ActivityChart activity={overview.activity} />
              <CategoryBars categories={overview.categories} total={overview.matchCount} />
              <TopCompanies companies={overview.topCompanies} />
            </>
          ) : (
            <div className="card insight skeleton-card" aria-busy="true" />
          )}
        </aside>
      </div>
    </section>
  );
}
