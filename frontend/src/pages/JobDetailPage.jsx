import { useEffect, useState } from "react";
import { PostedLine, ViewJobButton } from "../components/JobCard";
import { ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";
import { timeAgo } from "../services/format";

export default function JobDetailPage({ id }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setJob(null);
    setError(null);
    api.getJob(id).then(setJob).catch(setError);
  }, [id]);

  return (
    <section>
      <a className="back" href="#/">← Back to jobs</a>
      <ErrorBox error={error} />
      {!job && !error && <Loading />}
      {job && (
        <article className="detail">
          <h2>{job.title}</h2>
          <div className="job-company">{job.company}</div>
          <div className="job-meta">
            <span>{job.location ?? "Location not listed"}</span>
            <span className="dot">·</span>
            <span><PostedLine job={job} /></span>
          </div>
          <ViewJobButton url={job.url} className="big" />

          <dl className="facts">
            <dt>Type</dt><dd>{job.job_type}</dd>
            <dt>Category</dt><dd>{job.category}</dd>
            {job.compensation && <><dt>Pay</dt><dd>{job.compensation}</dd></>}
            <dt>Source</dt><dd>{job.source}</dd>
            <dt>First seen</dt><dd>{timeAgo(job.first_seen_at)}</dd>
            <dt>Your filters</dt><dd>{job.matches_filters ? "Matches" : "Does not match"}</dd>
          </dl>

          {job.description && <div className="description">{job.description}</div>}
        </article>
      )}
    </section>
  );
}
