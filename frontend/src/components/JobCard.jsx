import { memo } from "react";
import CompanyLogo from "./CompanyLogo";
import { ArrowUpRight } from "./Icons";
import { safeUrl, timeAgo } from "../services/format";

export function postedText(job) {
  return job.posted_at ? `Posted ${timeAgo(job.posted_at)}` : `Found ${timeAgo(job.first_seen_at)}`;
}

// Compact relative time for list rows: "2h", "3d", "5w".
export function shortAge(iso, now = Date.now()) {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return minutes < 1 ? "now" : `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  return days < 7 ? `${days}d` : `${Math.round(days / 7)}w`;
}

const SOURCE_LABELS = { companies: "Company careers site", unstop: "Unstop", wellfound: "Wellfound", mock: "Mock" };
export const sourceLabel = (source) => SOURCE_LABELS[source] ?? source;

export function ViewJobButton({ url }) {
  const href = safeUrl(url);
  if (!href) return null;
  return (
    <a className="btn btn-accent btn-lg" href={href} target="_blank" rel="noopener noreferrer">View Job Posting</a>
  );
}

function JobRow({ job, isNew, index }) {
  const href = safeUrl(job.url);
  const when = job.posted_at || job.first_seen_at;
  return (
    <div className={index != null && index < 14 ? "row link enter" : "row link"} style={index != null ? { "--i": Math.min(index, 13) } : undefined}>
      {isNew && <span className="new-dot" title="New since your last visit" />}
      <CompanyLogo company={job.company} url={job.logo_url} />
      <div className="job-text">
        <div className="job-line">
          <a className="job-title" href={`#/jobs/${job.id}`}>
            {isNew && <span className="visually-hidden">New: </span>}
            {job.title}
          </a>
          <time className="job-time" dateTime={when} title={postedText(job)}>{shortAge(when)}</time>
        </div>
        <div className="job-sub">{job.company} · {job.location ?? "Location not listed"}</div>
      </div>
      {href && (
        <a className="icon-btn" href={href} target="_blank" rel="noopener noreferrer"
           aria-label={`Open the ${job.company} posting`} title="Open Posting">
          <ArrowUpRight />
        </a>
      )}
    </div>
  );
}

export default memo(JobRow);
