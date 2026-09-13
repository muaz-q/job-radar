#!/usr/bin/env bash
# Restore the scanner's saved state (job_radar.db + public/*.json) from the `data` branch.
#
# Safety rule: if the branch exists but cannot be fetched, FAIL. Starting from an empty
# database would re-announce every job ever seen and then overwrite the real state.
#
# Usage: scripts/state_restore.sh <dir>
# Env:   REPO_URL (default: https://github.com/$GITHUB_REPOSITORY.git), STATE_BRANCH (default: data)
set -euo pipefail

dir="${1:?usage: state_restore.sh <dir>}"
url="${REPO_URL:-https://github.com/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is not set}.git}"
branch="${STATE_BRANCH:-data}"

set +e
git ls-remote --exit-code --heads "$url" "$branch" >/dev/null 2>&1
rc=$?
set -e

case "$rc" in
  0)
    rm -rf "$dir"
    git clone --quiet --depth 1 --branch "$branch" "$url" "$dir"
    rm -rf "$dir/.git"
    if [ ! -s "$dir/job_radar.db" ]; then
      echo "::error::The $branch branch exists but has no job_radar.db; refusing to start from empty state."
      exit 1
    fi
    echo "Restored state from branch '$branch' ($(du -h "$dir/job_radar.db" | cut -f1) database)."
    ;;
  2)
    rm -rf "$dir"
    mkdir -p "$dir"
    echo "No '$branch' branch yet: this is the first run, starting with empty state."
    ;;
  *)
    echo "::error::Could not reach the repository to restore state (git exit code $rc). Not scanning."
    exit 1
    ;;
esac
