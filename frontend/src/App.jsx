import { useCallback, useState } from "react";
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

export default function App() {
  const { page, id } = useHashRoute();
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const notifier = useNotificationPoller({ onNewAlerts: refresh });

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

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/">JOB RADAR</a>
        <nav>
          {NAV.map(([key, label]) => (
            <a key={key} href={`#/${key}`} className={page === key ? "active" : ""}>{label}</a>
          ))}
        </nav>
        <ScanButton onScanned={onScanned} />
      </header>

      {notifier.permission === "default" && (
        <div className="banner">
          Get alerted the moment a matching job appears.
          <button className="button small primary" onClick={notifier.requestPermission}>Allow notifications</button>
        </div>
      )}
      {notifier.permission === "denied" && (
        <div className="banner warn">
          Browser notifications are blocked for this site. Allow them in the address bar to receive alerts.
        </div>
      )}

      <main>{content}</main>
    </div>
  );
}
