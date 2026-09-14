// Inline icons drawn on a 24pt grid in the spirit of SF Symbols (no icon library). All use currentColor.

export function RadarMark() {
  return (
    <svg viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect width="28" height="28" rx="6.3" fill="currentColor" />
      <circle cx="14" cy="14" r="8.5" stroke="#fff" strokeWidth="1.6" opacity=".45" />
      <circle cx="14" cy="14" r="4.6" stroke="#fff" strokeWidth="1.6" opacity=".75" />
      <path d="M14 14l6.2-6.2" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
      <circle cx="14" cy="14" r="1.9" fill="#fff" />
    </svg>
  );
}

export function SearchIcon() {
  return (
    <svg viewBox="0 0 17 17" fill="none" aria-hidden="true">
      <circle cx="7.25" cy="7.25" r="5.75" stroke="currentColor" strokeWidth="1.9" />
      <path d="M11.5 11.5l4 4" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}

export function ChevronLeft() {
  return (
    <svg viewBox="0 0 12 20" fill="none" aria-hidden="true">
      <path d="M10 2L2 10l8 8" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3.5a5.8 5.8 0 0 0-5.8 5.8v3.4L4.6 15.6h14.8l-1.6-2.9V9.3A5.8 5.8 0 0 0 12 3.5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M9.7 18.8a2.4 2.4 0 0 0 4.6 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

/* Tab bar symbols: outline when inactive, filled when active (iOS convention). */

export function TabJobs({ active }) {
  return active ? (
    <svg viewBox="0 0 26 26" aria-hidden="true">
      <path fill="currentColor" d="M10 3.5h6A2.5 2.5 0 0 1 18.5 6v1.5h3A2.5 2.5 0 0 1 24 10v10a2.5 2.5 0 0 1-2.5 2.5h-17A2.5 2.5 0 0 1 2 20V10a2.5 2.5 0 0 1 2.5-2.5h3V6A2.5 2.5 0 0 1 10 3.5zm0 2a.5.5 0 0 0-.5.5v1.5h7V6a.5.5 0 0 0-.5-.5h-6z" />
    </svg>
  ) : (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <rect x="2.9" y="8.4" width="20.2" height="13.2" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8.5 8.4V6.2c0-.9.7-1.7 1.7-1.7h5.6c.9 0 1.7.8 1.7 1.7v2.2M3 13.6h20" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

export function TabSources({ active }) {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="13" cy="13" r="10" stroke="currentColor" strokeWidth="1.8" opacity={active ? 1 : 0.9} />
      <circle cx="13" cy="13" r="5.4" stroke="currentColor" strokeWidth="1.8" />
      {active && <circle cx="13" cy="13" r="10" fill="currentColor" opacity=".18" />}
      <path d="M13 13l6.4-6.4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="13" cy="13" r="1.9" fill="currentColor" />
    </svg>
  );
}

export function TabHistory({ active }) {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="13" cy="13" r="10" stroke="currentColor" strokeWidth="1.8" fill={active ? "currentColor" : "none"} />
      <path d="M13 7.5V13l3.6 2.2" style={{ stroke: active ? "var(--bar)" : "currentColor" }} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function TabSettings({ active }) {
  return (
    <svg viewBox="0 0 26 26" aria-hidden="true">
      <path fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"
            d="M11.2 3h3.6l.6 2.6 1.9.8 2.3-1.4 2.5 2.5-1.4 2.3.8 1.9 2.6.6v3.6l-2.6.6-.8 1.9 1.4 2.3-2.5 2.5-2.3-1.4-1.9.8-.6 2.6h-3.6l-.6-2.6-1.9-.8-2.3 1.4-2.5-2.5 1.4-2.3-.8-1.9L3 14.8v-3.6l2.6-.6.8-1.9L5 6.4l2.5-2.5 2.3 1.4 1.9-.8z" />
      <circle cx="13" cy="13" r="3.2" style={{ fill: active ? "var(--bar)" : "none", stroke: active ? "var(--bar)" : "currentColor" }} strokeWidth="1.8" />
    </svg>
  );
}
