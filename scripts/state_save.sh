#!/usr/bin/env bash
# Save the scanner's state to the `data` branch as a single commit, force-pushed.
#
# The branch never accumulates history, so an hourly binary database does not bloat the
# repository. `main` (code, config) is never touched by this script.
#
# Usage: scripts/state_save.sh <dir> <message>
# Env:   REPO_URL (default: token URL for $GITHUB_REPOSITORY), GITHUB_TOKEN, STATE_BRANCH (default: data)
set -euo pipefail

dir="${1:?usage: state_save.sh <dir> <message>}"
message="${2:?usage: state_save.sh <dir> <message>}"
branch="${STATE_BRANCH:-data}"
if [ -z "${REPO_URL:-}" ]; then
  : "${GITHUB_TOKEN:?GITHUB_TOKEN is not set}" "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is not set}"
  REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
fi

if [ ! -s "$dir/job_radar.db" ] || [ ! -s "$dir/public/jobs.json" ]; then
  echo "::error::$dir is missing job_radar.db or public/jobs.json; not saving an incomplete state."
  exit 1
fi

cd "$dir"
rm -rf .git
git init --quiet --initial-branch "$branch"
git add --all
git -c user.name="job-radar-bot" -c user.email="job-radar-bot@users.noreply.github.com" \
  commit --quiet --message "$message ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
set +e
git push --quiet --force "$REPO_URL" "$branch" 2>&1 | sed -E 's#https://[^@]+@#https://***@#g'
push_status=${PIPESTATUS[0]}
set -e
rm -rf .git
if [ "$push_status" -ne 0 ]; then
  echo "::error::Saving state failed (git push exit $push_status)."
  exit "$push_status"
fi
echo "Saved state to branch '$branch'."
