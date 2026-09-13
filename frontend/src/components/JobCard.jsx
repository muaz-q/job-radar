import { isFresh, safeUrl, timeAgo } from "../services/format";

export function PostedLine({ job }) {
  return job.posted_at
    ? <>Posted {timeAgo(job.posted_at)}</>
    : <>Found {timeAgo(job.first_seen_at)}</>;
}

export function ViewJobButton({ url, className = "" }) {
  const href = safeUrl(url);
  if (!href) return <span className="muted">No valid link</span>;
  return (
    <a className={`button primary ${className}`} href={href} target="_blank" rel="noopener noreferrer">
      View Job →
    </a>
  );
}

export default function JobCard({ job }) {
  return (
    <article className="job-card">
      <div className="job-main">
        <h3 className="job-title">
          <a href={`#/jobs/${job.id}`}>{job.title}</a>
          {isFresh(job.first_seen_at) && <span className="badge new">New</span>}
        </h3>
        <div className="job-company">{job.company}</div>
        <div className="job-meta">
          <span>{job.location ?? "Location not listed"}</span>
          <span className="dot">·</span>
          <span><PostedLine job={job} /></span>
        </div>
        <div className="job-tags">
          <span className="tag">{job.job_type}</span>
          <span className="tag">{job.category}</span>
          <span className="tag subtle">{job.source}</span>
        </div>
      </div>
      <ViewJobButton url={job.url} />
    </article>
  );
}
