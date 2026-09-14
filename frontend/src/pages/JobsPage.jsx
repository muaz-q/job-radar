import { useCallback, useEffect, useRef, useState } from "react";
import { SearchIcon } from "../components/Icons";
import JobRow from "../components/JobCard";
import { Empty, ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";
import { timeAgo } from "../services/format";

const PAGE_SIZE = 50;

function useDebounced(value, ms = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

function Menu({ id, label, value, onChange, options }) {
  return (
    <select id={id} className={value ? "menu set" : "menu"} value={value} onChange={onChange} aria-label={label}>
      <option value="">{label}</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export default function JobsPage({ refreshKey }) {
  const [view, setView] = useState("matching");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ source: "", location: "", category: "" });
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

  const setFilter = (key) => (event) => setFilters((f) => ({ ...f, [key]: event.target.value }));
  const anyFilter = q || filters.source || filters.location || filters.category;
  const noun = view === "matching" ? (jobs.total === 1 ? "match" : "matches") : (jobs.total === 1 ? "job" : "jobs");

  return (
    <section>
      <div className="page-head">
        <div>
          <h1 className="large-title">Jobs</h1>
          <p className="page-sub">
            {loading && jobs.items.length === 0 ? "Loading…" : `${jobs.total.toLocaleString()} ${noun}`}
            {lastScan && ` · last scan ${timeAgo(lastScan)}`}
          </p>
        </div>
        <div className="seg" role="tablist" aria-label="Which jobs">
          <button role="tab" aria-selected={view === "matching"} className={view === "matching" ? "active" : ""}
                  onClick={() => setView("matching")}>Matches</button>
          <button role="tab" aria-selected={view === "all"} className={view === "all" ? "active" : ""}
                  onClick={() => setView("all")}>All</button>
        </div>
      </div>

      <div className="toolbar">
        <label className="search">
          <SearchIcon />
          <input id="job-search" className="field" type="search" placeholder="Search title or company"
                 value={search} maxLength={100} onChange={(e) => setSearch(e.target.value)} aria-label="Search" />
        </label>
        <div className="filters">
          <Menu id="filter-source" label="Any source" value={filters.source} onChange={setFilter("source")} options={options.sources} />
          <Menu id="filter-location" label="Any location" value={filters.location} onChange={setFilter("location")} options={options.locations} />
          <Menu id="filter-category" label="Any category" value={filters.category} onChange={setFilter("category")} options={options.categories} />
        </div>
      </div>

      <ErrorBox error={error} onRetry={() => load(0)} />

      {jobs.items.length > 0 && (
        <div className="group">
          {jobs.items.map((job) => <JobRow key={job.id} job={job} />)}
        </div>
      )}

      {loading && <Loading />}
      {!loading && !error && jobs.items.length === 0 && (
        <div className="group">
          {anyFilter
            ? <Empty title="No results">Try a different search or clear a filter.</Empty>
            : view === "matching"
              ? <Empty title="No matches yet">Nothing new fits your filters. Widen them in <a href="#/settings">Settings</a>, or look through All.</Empty>
              : <Empty title="No jobs yet">Press Scan now to check every source.</Empty>}
        </div>
      )}
      {!loading && jobs.items.length < jobs.total && (
        <div className="center">
          <button className="btn" onClick={() => load(jobs.items.length)}>Show more</button>
        </div>
      )}
    </section>
  );
}
