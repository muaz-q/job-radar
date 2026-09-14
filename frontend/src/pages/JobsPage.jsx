import { useCallback, useEffect, useRef, useState } from "react";
import { FilterIcon, SearchIcon, XIcon } from "../components/Icons";
import JobRow from "../components/JobCard";
import { RevealTitle, Segmented } from "../components/Motion";
import { Empty, ErrorBox, SkeletonList } from "../components/Status";
import { api } from "../services/api";
import { timeAgo } from "../services/format";

const PAGE_SIZE = 50;
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

export default function JobsPage({ refreshKey, newSince }) {
  const [view, setView] = useState("matching");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ source: "", location: "", category: "" });
  const [showFilters, setShowFilters] = useState(false);
  const [options, setOptions] = useState({ sources: [], locations: [], categories: [] });
  const [jobs, setJobs] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastScan, setLastScan] = useState(null);
  const q = useDebounced(search);

  useEffect(() => {
    api.health().then((h) => setLastScan(h.generated_at ?? null)).catch(() => {});
  }, [refreshKey]);

  useEffect(() => {
    Promise.all([api.listSources(), api.getSettingsOptions()])
      .then(([sources, opts]) => setOptions({
        sources: sources.map((s) => ({ value: s.name, label: s.display_name })),
        locations: opts.locations.map((l) => ({ value: l, label: l })),
        categories: opts.categories.map((c) => ({ value: c, label: c })),
      }))
      .catch(() => {}); // the job list shows the connection error
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
  const isNew = (job) => new Date(job.first_seen_at).getTime() > newSince;
  const newCount = jobs.items.filter(isNew).length;

  const summary = loading && jobs.items.length === 0
    ? "Loading…"
    : [
        `${jobs.total.toLocaleString()} ${view === "matching" ? (jobs.total === 1 ? "match" : "matches") : (jobs.total === 1 ? "job" : "jobs")}`,
        newCount > 0 && `${newCount} new`,
        lastScan && `updated ${timeAgo(lastScan)}`,
      ].filter(Boolean).join(" · ");

  return (
    <section>
      <div className="page-head">
        <div>
          <RevealTitle>Jobs</RevealTitle>
          <p className="page-sub">{summary}</p>
        </div>
        <Segmented label="Which jobs" value={view} onChange={setView} options={[["matching", "Matches"], ["all", "All"]]} />
      </div>

      <div className="toolbar">
        <label className="search">
          <SearchIcon />
          <input id="job-search" className="field" type="search" placeholder="Search"
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

      {jobs.items.length > 0 && (
        <div className="group">
          {jobs.items.map((job, index) => <JobRow key={job.id} job={job} isNew={isNew(job)} index={index} />)}
        </div>
      )}

      {loading && jobs.items.length === 0 && <SkeletonList />}
      {!loading && !error && jobs.items.length === 0 && (
        <div className="group">
          {anyFilter
            ? <Empty title="No results">Try a different search or remove a filter.</Empty>
            : view === "matching"
              ? <Empty title="No matches yet">Nothing new fits your filters. Adjust them in <a href="#/settings">Settings</a>, or browse All.</Empty>
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
    </section>
  );
}
