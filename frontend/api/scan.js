// POST /api/scan  (header x-admin-password)
// Starts the "Scan for new jobs" GitHub Actions workflow. GitHub queues at most one extra
// run (see `concurrency` in scan.yml), so pressing it repeatedly cannot pile up scans.
import { github, handler, requireAdmin, requireRepoConfig } from "./_lib.js";

export async function startScan(req, env = process.env, fetchImpl = fetch) {
  await requireAdmin(req, env);
  const { token, repo } = requireRepoConfig(env);
  await github(`/repos/${repo}/actions/workflows/scan.yml/dispatches`, {
    token, fetchImpl, method: "POST", body: { ref: "main" },
  });
  return { queued: true, detail: "Scan started on GitHub. New results appear in about 3–5 minutes." };
}

export default handler((req) => startScan(req));
