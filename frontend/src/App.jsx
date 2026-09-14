import { useCallback, useEffect, useState } from "react";
import { BellIcon, RadarMark } from "./components/Icons";
import ScanButton from "./components/ScanButton";
import { useHashRoute } from "./hooks/useHashRoute";
import { useNotificationPoller } from "./hooks/useNotificationPoller";
import JobDetailPage from "./pages/JobDetailPage";
import JobsPage from "./pages/JobsPage";
import NotificationsPage from "./pages/NotificationsPage";
import SettingsPage from "./pages/SettingsPage";
import SourcesPage from "./pages/SourcesPage";

const NAV = [
  ["jobs", "Jobs"],
  ["sources", "Sources"],
  ["notifications", "History"],
  ["settings", "Settings"],
];

function useScrolled() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return scrolled;
}

export default function App() {
  const { page, id } = useHashRoute();
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const notifier = useNotificationPoller({ onNewAlerts: refresh });
  const scrolled = useScrolled();

  const onScanned = useCallback(() => {
    refresh();
    notifier.poll();
  }, [refresh, notifier]);

  let content;
  if (page === "jobs" && id) content = <JobDetailPage id={id} />;
  else if (page === "sources") content = <SourcesPage refreshKey={refreshKey} />;
  else if (page === "notifications") content = <NotificationsPage refreshKey={refreshKey} />;
  else if (page === "settings") content = <SettingsPage notifier={notifier} />;
  else content = <JobsPage refreshKey={refreshKey} />;

  const current = page === "jobs" || !NAV.some(([key]) => key === page) ? "jobs" : page;

  return (
    <div className="shell">
      <header className={scrolled ? "topbar scrolled" : "topbar"}>
        <a className="brand" href="#/"><RadarMark />Job Radar</a>
        <nav className="nav" aria-label="Sections">
          {NAV.map(([key, label]) => (
            <a key={key} href={`#/${key}`} className={current === key ? "active" : ""}
               aria-current={current === key ? "page" : undefined}>{label}</a>
          ))}
        </nav>
        <div className="topbar-actions">
          <ScanButton onScanned={onScanned} />
        </div>
      </header>

      {notifier.permission === "default" && (
        <div className="banner">
          <BellIcon />
          <p>Get a browser alert the moment a matching job appears.</p>
          <button className="btn btn-tinted btn-sm" onClick={notifier.requestPermission}>Allow</button>
        </div>
      )}
      {notifier.permission === "denied" && (
        <div className="banner warn">
          <BellIcon />
          <p>Browser notifications are blocked for this site. Allow them from the address bar to get alerts here.</p>
        </div>
      )}

      <main>{content}</main>
    </div>
  );
}
