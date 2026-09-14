import { useState } from "react";
import { RefreshIcon } from "./Icons";
import { api } from "../services/api";

// Scans run automatically, so starting one by hand is a quiet icon, not a headline button.
// The outcome is reported through a brief toast.
export default function ScanButton({ onScanned, notify, onBusyChange }) {
  const [busy, setBusyState] = useState(false);
  const setBusy = (value) => { setBusyState(value); onBusyChange?.(value); };

  async function scan() {
    setBusy(true);
    try {
      const summary = await api.scan();
      if (summary.queued) { // hosted: the scan runs on GitHub, results arrive later
        notify("Scan started. New results in about 5 minutes.");
        return;
      }
      const failed = summary.sources.filter((s) => s.status === "error").map((s) => s.source);
      const newCount = summary.sources.reduce((n, s) => n + s.new, 0);
      const matching = summary.sources.reduce((n, s) => n + s.matching, 0);
      notify(failed.length
        ? `Scan finished, but ${failed.join(", ")} failed.`
        : `Scan finished: ${newCount} new, ${matching} matching.`, failed.length > 0);
      onScanned?.(summary);
    } catch (error) {
      notify(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button className={busy ? "icon-btn spin" : "icon-btn"} onClick={scan} disabled={busy}
            aria-label={busy ? "Scanning" : "Scan Now"} title={busy ? "Scanning…" : "Scan Now"}>
      <RefreshIcon />
    </button>
  );
}
