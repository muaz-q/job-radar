export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-card" role="alert">
      <span>{error.message ?? String(error)}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Try Again</button>}
    </div>
  );
}

// Placeholder rows shaped like the real list, so nothing jumps when data arrives.
export function SkeletonList({ rows = 6 }) {
  return (
    <div className="group" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-row">
          <span className="skeleton-logo" />
          <span className="skeleton-lines">
            <span className="skeleton-bar" style={{ width: `${62 - (i % 3) * 12}%` }} />
            <span className="skeleton-bar" style={{ width: "34%" }} />
            <span className="skeleton-bar" style={{ width: `${48 + (i % 2) * 14}%`, height: 9 }} />
          </span>
        </div>
      ))}
    </div>
  );
}

export function Loading() {
  return <SkeletonList rows={3} />;
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      {title && <h3>{title}</h3>}
      <p>{children}</p>
    </div>
  );
}
