export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <span>{error.message ?? String(error)}</span>
      {onRetry && <button className="button small" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return <p className="muted">{label}</p>;
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}
