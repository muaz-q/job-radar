// Picks the data layer. Both expose the same functions, so pages don't care which one runs.
//   VITE_GITHUB_REPO set   -> hosted mode (Vercel dashboard over GitHub-published data)
//   otherwise              -> local mode (FastAPI backend on port 8010)
import { hostedApi, REPO } from "./hostedApi";
import { localApi } from "./localApi";

export { ApiError } from "./errors";
export const HOSTED = Boolean(REPO);
export const GITHUB_REPO = REPO;
export const api = HOSTED ? hostedApi : localApi;
