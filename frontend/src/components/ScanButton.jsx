import { useState } from "react";
import { api } from "../services/api";

// Triggers POST /scan and reports what came back in one short line.
export default function ScanButton({ onScanned }) {
  const [state, setState] = useState({ busy: false, message: null, error: false });

  async function scan() {
    setState({ busy: true, message: "Scanning…", error: false });
    try {
      const summary = await api.scan();
      if (summary.queued) { // hosted: the scan runs on GitHub, results arrive later
        setState({ busy: false, message: summary.detail, error: false });
        return;
      }
      const parts = summary.sources.map((s) =>
        s.status === "error"
          ? `${s.source}: failed`
          : `${s.source}: ${s.new} new, ${s.matching} matching`,
      );
      const failed = summary.sources.some((s) => s.status === "error");
      setState({ busy: false, message: parts.join(" · "), error: failed });
      onScanned?.(summary);
    } catch (error) {
      setState({ busy: false, message: error.message, error: true });
    }
  }

  return (
    <div className="scan">
      {state.message && <span className={state.error ? "scan-msg error" : "scan-msg"}>{state.message}</span>}
      <button className="button" onClick={scan} disabled={state.busy}>
        {state.busy ? "Scanning…" : "Scan now"}
      </button>
    </div>
  );
}
