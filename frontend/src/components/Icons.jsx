// Inline icons in the spirit of SF Symbols (no icon library). Colours come from CSS via currentColor
// or style (SVG presentation attributes cannot read CSS variables).

const ink = { stroke: "var(--bg)" };

export function RadarMark() {
  return (
    <svg viewBox="0 0 28 28" fill="none" aria-hidden="true" style={{ color: "var(--text)" }}>
      <rect width="28" height="28" rx="6.5" fill="currentColor" />
      <circle cx="14" cy="14" r="8.4" strokeWidth="1.6" style={{ ...ink, opacity: 0.4 }} />
      <circle cx="14" cy="14" r="4.5" strokeWidth="1.6" style={{ ...ink, opacity: 0.7 }} />
      <path className="radar-needle" d="M14 14l6.1-6.1" strokeWidth="2" strokeLinecap="round" style={ink} />
      <circle cx="14" cy="14" r="1.9" style={{ fill: "var(--bg)" }} />
    </svg>
  );
}

export function SearchIcon() {
  return (
    <svg viewBox="0 0 17 17" fill="none" aria-hidden="true">
      <circle cx="7.25" cy="7.25" r="5.75" stroke="currentColor" strokeWidth="1.8" />
      <path d="M11.5 11.5l4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function FilterIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 4h12M4.5 8h7M7 12h2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export function ChevronLeft() {
  return (
    <svg viewBox="0 0 11 18" fill="none" aria-hidden="true">
      <path d="M9.5 1.5L2 9l7.5 7.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ArrowUpRight() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M6.5 13.5l7-7M8 6.5h5.5V12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function RefreshIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M16 10a6 6 0 1 1-1.76-4.24" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M14.5 2.5v3.5H11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SunIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="3.6" stroke="currentColor" strokeWidth="1.8" />
      <path d="M10 1.8v1.8M10 16.4v1.8M1.8 10h1.8M16.4 10h1.8M4.2 4.2l1.3 1.3M14.5 14.5l1.3 1.3M4.2 15.8l1.3-1.3M14.5 5.5l1.3-1.3"
            stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function MoonIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M16.5 12.4A7 7 0 0 1 7.6 3.5a7 7 0 1 0 8.9 8.9z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

export function XIcon() {
  return (
    <svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M3 3l6 6M9 3L3 9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path className="check-draw" pathLength="1" d="M2.5 6.3l2.3 2.3 4.7-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
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
      <rect x="2.9" y="8.4" width="20.2" height="13.2" rx="2.2" stroke="currentColor" strokeWidth="1.7" />
      <path d="M8.5 8.4V6.2c0-.9.7-1.7 1.7-1.7h5.6c.9 0 1.7.8 1.7 1.7v2.2M3 13.6h20" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

export function TabSources({ active }) {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true">
      {active && <circle cx="13" cy="13" r="10" fill="currentColor" opacity=".16" />}
      <circle cx="13" cy="13" r="10" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="13" cy="13" r="5.4" stroke="currentColor" strokeWidth="1.7" />
      <path d="M13 13l6.4-6.4" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
      <circle cx="13" cy="13" r="1.9" fill="currentColor" />
    </svg>
  );
}

export function TabHistory({ active }) {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="13" cy="13" r="10" stroke="currentColor" strokeWidth="1.7" fill={active ? "currentColor" : "none"} />
      <path d="M13 7.5V13l3.6 2.2" style={{ stroke: active ? "var(--bar)" : "currentColor" }} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function TabSettings({ active }) {
  return (
    <svg viewBox="0 0 26 26" aria-hidden="true">
      <path fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"
            d="M11.2 3h3.6l.6 2.6 1.9.8 2.3-1.4 2.5 2.5-1.4 2.3.8 1.9 2.6.6v3.6l-2.6.6-.8 1.9 1.4 2.3-2.5 2.5-2.3-1.4-1.9.8-.6 2.6h-3.6l-.6-2.6-1.9-.8-2.3 1.4-2.5-2.5 1.4-2.3-.8-1.9L3 14.8v-3.6l2.6-.6.8-1.9L5 6.4l2.5-2.5 2.3 1.4 1.9-.8z" />
      <circle cx="13" cy="13" r="3.2" style={{ fill: active ? "var(--bar)" : "none", stroke: active ? "var(--bar)" : "currentColor" }} strokeWidth="1.7" />
    </svg>
  );
}
