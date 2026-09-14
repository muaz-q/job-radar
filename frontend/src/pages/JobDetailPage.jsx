import { useEffect, useState } from "react";
import CompanyLogo from "../components/CompanyLogo";
import { ChevronLeft } from "../components/Icons";
import { postedText, sourceLabel, ViewJobButton } from "../components/JobCard";
import { ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";
import { timeAgo } from "../services/format";

function Fact({ label, children }) {
  return (
    <div className="row plain">
      <dl className="kv" style={{ flex: 1, margin: 0 }}>
        <dt>{label}</dt>
        <dd>{children}</dd>
      </dl>
    </div>
  );
}

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
      <a className="back" href="#/"><ChevronLeft />Jobs</a>
      <ErrorBox error={error} />
      {!job && !error && <Loading />}
      {job && (
        <article>
          <header className="detail-head">
            <CompanyLogo company={job.company} url={job.logo_url} size={72} />
            <div>
              <h1 className="detail-title">{job.title}</h1>
              <p className="detail-company">{job.company}</p>
              <p className="page-sub">{job.location ?? "Location not listed"} · {postedText(job)}</p>
            </div>
            <ViewJobButton url={job.url} size="lg" label="View job posting" />
          </header>

          <div className="group">
            <Fact label="Type">{job.job_type}</Fact>
            <Fact label="Category">{job.category}</Fact>
            {job.compensation && <Fact label="Pay">{job.compensation}</Fact>}
            <Fact label="Found on">{sourceLabel(job.source)}</Fact>
            <Fact label="First seen">{timeAgo(job.first_seen_at)}</Fact>
            <Fact label="Your filters">{job.matches_filters ? "Matches" : "Doesn't match"}</Fact>
          </div>

          {job.description && (
            <>
              <h2 className="section-label">About the role</h2>
              <div className="group"><div className="prose">{job.description}</div></div>
            </>
          )}
        </article>
      )}
    </section>
  );
}
