import { useCallback, useEffect, useRef, useState } from "react";
import { MoonIcon, RadarMark, SunIcon, TabHistory, TabJobs, TabSettings, TabSources } from "./components/Icons";
import ScanButton from "./components/ScanButton";
import { useHashRoute } from "./hooks/useHashRoute";
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

function useScrollY() {
  const [y, setY] = useState(0);
  useEffect(() => {
    const onScroll = () => setY(window.scrollY);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return y;
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
  const scrollY = useScrollY();
  const [toast, notify] = useToast();

  const onScanned = useCallback(() => {
    refresh();
    notifier.poll();
  }, [refresh, notifier]);

  useEffect(() => { window.scrollTo(0, 0); }, [page, id]);

  const current = NAV.some((n) => n.key === page) ? page : "jobs";
  const isDetail = page === "jobs" && id;
  const title = isDetail ? "Job" : NAV.find((n) => n.key === current).label;
  const dark = theme.resolved === "dark";

  let content;
  if (isDetail) content = <JobDetailPage id={id} />;
  else if (page === "sources") content = <SourcesPage refreshKey={refreshKey} />;
  else if (page === "notifications") content = <NotificationsPage refreshKey={refreshKey} />;
  else if (page === "settings") content = <SettingsPage notifier={notifier} theme={theme} />;
  else content = <JobsPage refreshKey={refreshKey} newSince={newSince} />;

  const barClass = ["topbar", scrollY > 4 && "scrolled", scrollY > 64 && "past-title"].filter(Boolean).join(" ");

  return (
    <div className="shell">
      <div className="backdrop" aria-hidden="true" />
      <header className={barClass}>
        <a className="brand" href="#/" aria-label="Job Radar home"><RadarMark /><span>Job Radar</span></a>
        <nav className="tabs" aria-label="Sections">
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
          <ScanButton onScanned={onScanned} notify={notify} />
        </div>
      </header>

      <main>{content}</main>

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
