import { useState } from "react";
import { api } from "../services/api";

// Starts a scan and reports the outcome in one short line next to the button.
export default function ScanButton({ onScanned }) {
  const [state, setState] = useState({ busy: false, message: null, error: false, detail: "" });

  async function scan() {
    setState({ busy: true, message: null, error: false, detail: "" });
    try {
      const summary = await api.scan();
      if (summary.queued) { // hosted: the scan runs on GitHub, results arrive later
        setState({ busy: false, message: "Started · results in ~5 min", error: false, detail: summary.detail });
        return;
      }
      const newCount = summary.sources.reduce((n, s) => n + s.new, 0);
      const matching = summary.sources.reduce((n, s) => n + s.matching, 0);
      const failed = summary.sources.filter((s) => s.status === "error").map((s) => s.source);
      const detail = summary.sources.map((s) => `${s.source}: ${s.status === "error" ? "failed" : `${s.new} new, ${s.matching} matching`}`).join(" · ");
      setState({
        busy: false,
        message: failed.length ? `${failed.join(", ")} failed` : `${newCount} new · ${matching} matching`,
        error: failed.length > 0,
        detail,
      });
      onScanned?.(summary);
    } catch (error) {
      setState({ busy: false, message: error.message, error: true, detail: error.message });
    }
  }

  return (
    <>
      {state.message && (
        <span className={state.error ? "scan-msg error" : "scan-msg"} title={state.detail} role="status">{state.message}</span>
      )}
      <button className="btn btn-primary" onClick={scan} disabled={state.busy}>
        {state.busy ? "Scanning…" : "Scan now"}
      </button>
    </>
  );
}
