import { useCallback, useEffect, useState } from "react";
import { BellIcon, RadarMark, TabHistory, TabJobs, TabSettings, TabSources } from "./components/Icons";
import ScanButton from "./components/ScanButton";
import { useHashRoute } from "./hooks/useHashRoute";
import { useNotificationPoller } from "./hooks/useNotificationPoller";
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

// iOS large titles collapse into the navigation bar once they scroll out of view.
function useScroll() {
  const [y, setY] = useState(0);
  useEffect(() => {
    const onScroll = () => setY(window.scrollY);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return y;
}

export default function App() {
  const { page, id } = useHashRoute();
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const notifier = useNotificationPoller({ onNewAlerts: refresh });
  const scrollY = useScroll();

  const onScanned = useCallback(() => {
    refresh();
    notifier.poll();
  }, [refresh, notifier]);

  // Each page starts at the top, like pushing a new screen.
  useEffect(() => { window.scrollTo(0, 0); }, [page, id]);

  const current = NAV.some((n) => n.key === page) ? page : "jobs";
  const isDetail = page === "jobs" && id;
  const title = isDetail ? "Job" : NAV.find((n) => n.key === current).label;

  let content;
  if (isDetail) content = <JobDetailPage id={id} />;
  else if (page === "sources") content = <SourcesPage refreshKey={refreshKey} />;
  else if (page === "notifications") content = <NotificationsPage refreshKey={refreshKey} />;
  else if (page === "settings") content = <SettingsPage notifier={notifier} />;
  else content = <JobsPage refreshKey={refreshKey} />;

  const barClass = ["topbar", scrollY > 4 && "scrolled", scrollY > 64 && "past-title"].filter(Boolean).join(" ");

  return (
    <div className="shell">
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
