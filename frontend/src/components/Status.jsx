export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-card" role="alert">
      <span>{error.message ?? String(error)}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return <p className="loading">{label}</p>;
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      {title && <h3>{title}</h3>}
      <p>{children}</p>
    </div>
  );
}
