import { useCallback, useEffect, useRef, useState } from "react";
import { MoonIcon, RadarMark, SunIcon, TabHistory, TabJobs, TabSettings, TabSources } from "./components/Icons";
import ScanButton from "./components/ScanButton";
import { useHashRoute } from "./hooks/useHashRoute";
import { useSlidingIndicator, useSpotlight } from "./hooks/useMotion";
import { useNewSince } from "./hooks/useLastVisit";
import { useNotificationPoller } from "./hooks/useNotificationPoller";
import { useTheme } from "./hooks/useTheme";
import JobDetailPage from "./pages/JobDetailPage";
import JobsPage from "./pages/JobsPage";
import NotificationsPage from "./pages/NotificationsPage";
import SettingsPage from "./pages/SettingsPage";
import SourcesPage from "./pages/SourcesPage";

const NAV = [
  { key: "jobs", label: "Jobs", Icon: TabJobs },
  { key: "sources", label: "Sources", Icon: TabSources },
  { key: "notifications", label: "History", Icon: TabHistory },
  { key: "settings", label: "Settings", Icon: TabSettings },
];

// Only the two thresholds matter, so state changes (and re-renders) happen when a threshold is crossed,
// not on every scrolled pixel.
function useScrollFlags() {
  const [flags, setFlags] = useState({ scrolled: false, pastTitle: false });
  useEffect(() => {
    let frame = 0;
    const read = () => {
      frame = 0;
      const y = window.scrollY;
      const scrolled = y > 4;
      const pastTitle = y > 64;
      setFlags((prev) => (prev.scrolled === scrolled && prev.pastTitle === pastTitle ? prev : { scrolled, pastTitle }));
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(read); };
    read();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { cancelAnimationFrame(frame); window.removeEventListener("scroll", onScroll); };
  }, []);
  return flags;
}

function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);
  const notify = useCallback((message, error = false) => {
    clearTimeout(timer.current);
    setToast({ message, error, key: Date.now() });
    timer.current = setTimeout(() => setToast(null), 4200);
  }, []);
  return [toast, notify];
}

export default function App() {
  const { page, id } = useHashRoute();
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const notifier = useNotificationPoller({ onNewAlerts: refresh });
  const theme = useTheme();
  const newSince = useNewSince();
  const scroll = useScrollFlags();
  const [toast, notify] = useToast();
  const [scanning, setScanning] = useState(false);
  const spotlightRef = useRef(null);
  const tabsRef = useRef(null);
  useSpotlight(spotlightRef);

  const onScanned = useCallback(() => {
    refresh();
    notifier.poll();
  }, [refresh, notifier]);

  useEffect(() => { window.scrollTo(0, 0); }, [page, id]);

  const current = NAV.some((n) => n.key === page) ? page : "jobs";
  const isDetail = page === "jobs" && id;
  const title = isDetail ? "Job" : NAV.find((n) => n.key === current).label;
  const dark = theme.resolved === "dark";
  const tabIndicator = useSlidingIndicator(tabsRef, "a.active", [current]);

  let content;
  if (isDetail) content = <JobDetailPage id={id} />;
  else if (page === "sources") content = <SourcesPage refreshKey={refreshKey} />;
  else if (page === "notifications") content = <NotificationsPage refreshKey={refreshKey} />;
  else if (page === "settings") content = <SettingsPage notifier={notifier} theme={theme} />;
  else content = <JobsPage refreshKey={refreshKey} newSince={newSince} />;

  const barClass = ["topbar", scroll.scrolled && "scrolled", scroll.pastTitle && "past-title"].filter(Boolean).join(" ");

  return (
    <div className="shell">
      <div className="backdrop" aria-hidden="true" />
      <div ref={spotlightRef} className="spotlight" aria-hidden="true" />
      <header className={barClass}>
        <a className={scanning ? "brand scanning" : "brand"} href="#/" aria-label="Job Radar home"><RadarMark /><span>Job Radar</span></a>
        <nav ref={tabsRef} className="tabs" aria-label="Sections">
          {tabIndicator.style && <span className={tabIndicator.ready ? "tab-pill ready" : "tab-pill"} style={tabIndicator.style} aria-hidden="true" />}
          {NAV.map(({ key, label }) => (
            <a key={key} href={`#/${key}`} className={current === key ? "active" : ""}
               aria-current={current === key ? "page" : undefined}>{label}</a>
          ))}
        </nav>
        <span className="compact-title" aria-hidden="true">{title}</span>
        <div className="topbar-actions">
          <button className="icon-btn" onClick={theme.toggle}
                  aria-label={dark ? "Switch to light appearance" : "Switch to dark appearance"}
                  title={dark ? "Light Appearance" : "Dark Appearance"}>
            {dark ? <SunIcon /> : <MoonIcon />}
          </button>
          <ScanButton onScanned={onScanned} notify={notify} onBusyChange={setScanning} />
        </div>
      </header>

      {/* Keyed by route: each screen enters with a short fade-and-rise */}
      <main key={isDetail ? `job-${id}` : current} className="page">{content}</main>

      {toast && (
        <div key={toast.key} className={toast.error ? "toast error" : "toast"} role="status" aria-live="polite">
          {toast.message}
        </div>
      )}

      <nav className="tabbar" aria-label="Sections">
        {NAV.map(({ key, label, Icon }) => (
          <a key={key} href={`#/${key}`} className={current === key ? "active" : ""}
             aria-current={current === key ? "page" : undefined}>
            <Icon active={current === key} />
            {label}
          </a>
        ))}
      </nav>
    </div>
  );
}
