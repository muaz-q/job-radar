// POST /api/settings  (header x-admin-password, body {settings})
// Commits config/settings.json to the repo. That push triggers the scan workflow, which
// applies the new filters to the dashboard data within a few minutes.
import { github, handler, requireAdmin, requireRepoConfig, validateSettings } from "./_lib.js";

const PATH = "config/settings.json";

export async function saveSettings(req, env = process.env, fetchImpl = fetch) {
  await requireAdmin(req, env);
  const { token, repo } = requireRepoConfig(env);
  const settings = validateSettings(req.body?.settings);

  const current = await github(`/repos/${repo}/contents/${PATH}?ref=main`, { token, fetchImpl });
  const content = Buffer.from(JSON.stringify(settings, null, 2) + "\n", "utf8").toString("base64");
  await github(`/repos/${repo}/contents/${PATH}`, {
    token, fetchImpl, method: "PUT",
    body: { message: "Update settings from dashboard", content, sha: current.sha, branch: "main" },
  });
  return { settings, detail: "Saved. A scan is starting on GitHub to apply them (a few minutes)." };
}

export default handler((req) => saveSettings(req));
