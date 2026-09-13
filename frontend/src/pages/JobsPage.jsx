import { useCallback, useEffect, useRef, useState } from "react";
import JobCard from "../components/JobCard";
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

export default function JobsPage({ refreshKey }) {
  const [view, setView] = useState("matching");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ source: "", location: "", category: "" });
  const [options, setOptions] = useState({ sources: [], locations: [], categories: [] });
  const [jobs, setJobs] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const q = useDebounced(search);
  const [lastScan, setLastScan] = useState(null);

  useEffect(() => {
    api.health().then((h) => setLastScan(h.generated_at ?? null)).catch(() => {});
  }, [refreshKey]);

  useEffect(() => {
    Promise.all([api.listSources(), api.getSettingsOptions()])
      .then(([sources, opts]) => setOptions({
        sources: sources.map((s) => ({ name: s.name, label: s.display_name })),
        locations: opts.locations,
        categories: opts.categories,
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

  return (
    <section>
      <div className="page-head">
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={view === "matching"} className={view === "matching" ? "active" : ""}
                  onClick={() => setView("matching")}>New Jobs</button>
          <button role="tab" aria-selected={view === "all"} className={view === "all" ? "active" : ""}
                  onClick={() => setView("all")}>All seen</button>
        </div>
        <span className="muted">
          {jobs.total} {jobs.total === 1 ? "job" : "jobs"}
          {lastScan && <> · last scan {timeAgo(lastScan)}</>}
        </span>
      </div>

      <div className="filter-bar">
        <input type="search" placeholder="Search title or company" value={search} maxLength={100}
               onChange={(e) => setSearch(e.target.value)} aria-label="Search" />
        <select value={filters.source} onChange={setFilter("source")} aria-label="Source">
          <option value="">All sources</option>
          {options.sources.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
        </select>
        <select value={filters.location} onChange={setFilter("location")} aria-label="Location">
          <option value="">All locations</option>
          {options.locations.map((l) => <option key={l}>{l}</option>)}
        </select>
        <select value={filters.category} onChange={setFilter("category")} aria-label="Category">
          <option value="">All categories</option>
          {options.categories.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>

      <ErrorBox error={error} onRetry={() => load(0)} />

      {jobs.items.map((job) => <JobCard key={job.id} job={job} />)}

      {loading && <Loading />}
      {!loading && !error && jobs.items.length === 0 && (
        <Empty>
          {anyFilter
            ? "No jobs match these filters."
            : view === "matching"
              ? <>No jobs match your settings yet. Run a scan, widen your <a href="#/settings">settings</a>, or check <b>All seen</b>.</>
              : "No jobs yet. Press Scan now."}
        </Empty>
      )}
      {!loading && jobs.items.length < jobs.total && (
        <button className="button load-more" onClick={() => load(jobs.items.length)}>Load more</button>
      )}
    </section>
  );
}
