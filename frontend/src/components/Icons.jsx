// Small inline icons (no icon library). All inherit currentColor.

export function RadarMark() {
  return (
    <svg viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="13" cy="13" r="11.25" stroke="currentColor" strokeWidth="1.5" opacity=".35" />
      <circle cx="13" cy="13" r="6.5" stroke="currentColor" strokeWidth="1.5" opacity=".6" />
      <path d="M13 13 L21.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="13" cy="13" r="2.25" fill="currentColor" />
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

export function ChevronLeft() {
  return (
    <svg viewBox="0 0 11 18" fill="none" aria-hidden="true">
      <path d="M9.5 1.5L2 9l7.5 7.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ArrowUpRight() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M5 11L11 5M6 5h5v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BellIcon() {
  return (
    <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <path d="M11 3a5.5 5.5 0 0 0-5.5 5.5v3.2L4 14.5h14l-1.5-2.8V8.5A5.5 5.5 0 0 0 11 3z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M8.8 17.5a2.3 2.3 0 0 0 4.4 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
