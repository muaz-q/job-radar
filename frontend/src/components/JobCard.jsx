import CompanyLogo from "./CompanyLogo";
import { isFresh, safeUrl, timeAgo } from "../services/format";

export function postedText(job) {
  return job.posted_at ? `Posted ${timeAgo(job.posted_at)}` : `Found ${timeAgo(job.first_seen_at)}`;
}

const SOURCE_LABELS = { companies: "Careers site", unstop: "Unstop", wellfound: "Wellfound", mock: "Mock" };
export const sourceLabel = (source) => SOURCE_LABELS[source] ?? source;

export function ViewJobButton({ url, size = "sm", label = "View" }) {
  const href = safeUrl(url);
  if (!href) return null;
  const cls = size === "lg" ? "btn btn-primary btn-lg" : "btn btn-tinted btn-sm";
  return (
    <a className={cls} href={href} target="_blank" rel="noopener noreferrer" aria-label={size === "lg" ? undefined : "View job posting"}>
      {label}
    </a>
  );
}

export default function JobRow({ job }) {
  const fresh = isFresh(job.first_seen_at);
  return (
    <div className="row link">
      {/* Like Mail's unread dot: in the margin, so titles stay aligned */}
      {fresh && <span className="new-dot" title="Found in the last 24 hours" />}
      <CompanyLogo company={job.company} url={job.logo_url} />
      <div className="job-text">
        <a className="job-title" href={`#/jobs/${job.id}`}>
          {fresh && <span className="visually-hidden">New: </span>}
          {job.title}
        </a>
        <div className="job-company">{job.company}</div>
        <div className="job-meta">
          {[job.location ?? "Location not listed", postedText(job), job.job_type, sourceLabel(job.source)].join(" · ")}
        </div>
      </div>
      <ViewJobButton url={job.url} />
    </div>
  );
}
