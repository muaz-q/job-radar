import { useEffect, useState } from "react";
import CompanyLogo from "../components/CompanyLogo";
import { ChevronLeft } from "../components/Icons";
import { postedText, sourceLabel, ViewJobButton } from "../components/JobCard";
import { ErrorBox, Loading } from "../components/Status";
import { api } from "../services/api";

function Fact({ label, children }) {
  return (
    <div className="row plain">
      <dl className="kv">
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
    <section className="narrow">
      <a className="back" href="#/"><ChevronLeft />Jobs</a>
      <ErrorBox error={error} />
      {!job && !error && <Loading />}
      {job && (
        <article>
          <header className="detail-head stagger">
            <CompanyLogo company={job.company} url={job.logo_url} size={64} />
            <div>
              <h1 className="detail-title">{job.title}</h1>
              <p className="detail-company">{job.company}</p>
            </div>
            <ViewJobButton url={job.url} />
          </header>

          <div className="group">
            <Fact label="Location">{job.location ?? "Not listed"}</Fact>
            <Fact label="Type">{job.job_type}</Fact>
            {job.compensation && <Fact label="Pay">{job.compensation}</Fact>}
            <Fact label="Posted">{postedText(job).replace(/^(Posted|Found) /, "")}</Fact>
            <Fact label="Source">{sourceLabel(job.source)}</Fact>
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
