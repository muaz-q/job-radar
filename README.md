# Job Radar

Watches job sources for **new** postings and alerts you the moment a relevant one appears.
You decide whether to apply. No AI, no auto-apply.

```
NEW JOB → DETECT → FILTER → NOTIFY → YOU DECIDE
```

Sources: **Unstop** internships, **company careers boards** (Greenhouse / Lever / Ashby), **Wellfound**.
Alerts: **Telegram** (hosted) or browser notifications (local).

## Two ways to run it

| | Hosted (always on) | Local |
|---|---|---|
| Scanner | GitHub Actions, hourly | FastAPI on your PC, every 15 min |
| Data | `data` branch of the repo | SQLite file |
| Dashboard | Vercel | `localhost:5173` |
| Alerts | Telegram, even with every device closed | Browser, while the tab is open |
| Cost | Free (public repo) | Free |

```
 GitHub Actions (hourly)                      Vercel
 ┌───────────────────────────────┐            ┌──────────────────────────────┐
 │ restore state (data branch)   │            │ dashboard (static React)     │
 │ scan sources → dedup → filter │  JSON on   │   reads jobs/sources/history │
 │ save state + public/*.json ───┼──────────► │   from raw.githubusercontent │
 │ send Telegram alerts          │  GitHub    │ /api/settings  ─┐ password   │
 └───────────────▲───────────────┘            │ /api/scan      ─┤ protected  │
                 │ commit config/settings.json│                 │            │
                 └────── or workflow_dispatch ◄─────────────────┘            │
                                              └──────────────────────────────┘
```

## Hosted setup (about 15 minutes)

### 1. Telegram bot
1. In Telegram, message **@BotFather** → `/newbot` → pick a name. Copy the **token**.
2. Send any message to your new bot (it can only message people who wrote to it first).
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy `"chat":{"id": ...}`: that is your **chat id**.

### 2. GitHub (public repo)
1. Push this project to a new **public** repository.
2. *Settings → Secrets and variables → Actions*:
   - Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - Variables: `DASHBOARD_URL` = your Vercel URL (add after step 3)
3. *Actions* tab → enable workflows → **Scan for new jobs** → **Run workflow**.
   The first run creates the `data` branch and sends one Telegram summary of everything matching.

### 3. Vercel dashboard
1. vercel.com → *Add New Project* → import the repo → **Root Directory: `frontend`** (framework: Vite).
2. Environment variables:
   - `VITE_GITHUB_REPO` = `owner/repo` (makes the dashboard read the GitHub data)
   - `GITHUB_REPO` = `owner/repo`
   - `GITHUB_TOKEN` = a [fine-grained token](https://github.com/settings/personal-access-tokens/new) for **only this repo** with *Contents: Read and write* and *Actions: Read and write*
   - `ADMIN_PASSWORD` = a password of 12+ characters (needed to save settings or start a scan)
3. Deploy. Put the URL into the `DASHBOARD_URL` GitHub variable.

**Anyone with the URL can view the dashboard** (the job data is public anyway). Only someone with the
admin password can change settings or start scans.

### Changing things later
- **Filters:** Settings page → Save (or edit `config/settings.json` on GitHub). A scan starts automatically.
- **Companies to watch:** edit `config/sources.json` on GitHub. Add `{ "ats": "lever", "slug": "...", "name": "..." }`.
  The slug is the part after `jobs.lever.co/`, `boards.greenhouse.io/` or `jobs.ashbyhq.com/` in a company's careers link.
  A wrong slug shows as a warning on the Sources page.
- **Scan frequency:** the `cron` line in `.github/workflows/scan.yml`.

### Hosted: what to expect
- **Delay:** hourly, and GitHub often starts scheduled runs 10–30+ minutes late. Alerts arrive
  roughly 15–90 minutes after a posting appears.
- **60-day rule:** GitHub pauses scheduled workflows in repos with no activity for 60 days. Every scan
  pushes the `data` branch, which should count as activity. If scans ever stop, re-enable the
  workflow from the Actions tab.
- **Blocked sources:** some sites refuse requests from GitHub's data-centre addresses. That shows up
  as an error on the Sources page, and after 3 failed scans in a row you get a Telegram message.
- **Everything is public:** the repo, the `data` branch (seen jobs, filters) and Actions logs.
  Secrets (Telegram token, GitHub token) are never exposed.

## Local setup

```powershell
cd job-radar\backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:create_app --factory --port 8010
```
```powershell
cd job-radar\frontend
npm install
npm run dev          # http://localhost:5173
```

Both windows must stay open. To try alerts without waiting for a real new job:
`$env:ENABLED_SOURCES="mock"; $env:MOCK_EMIT_NEW_JOB_EACH_SCAN="true"; $env:MIN_MANUAL_SCAN_GAP_SECONDS="0"`
before starting the backend, then press **Scan now** repeatedly.

**Tests:** `backend\.venv\Scripts\python -m pytest` (in `backend`) and `npm test` (in `frontend`).
GitHub runs both on every push.

## Sources and why these

| Source | Access | Notes |
|---|---|---|
| Unstop | Public API; `robots.txt` explicitly allows `/api/public/*` | ~900 open internships, many non-tech (filters handle it). All ~30 pages are read because results aren't date-sorted. |
| Company boards | Official public job-board APIs of Greenhouse, Lever, Ashby | Only India-based / India-remote roles kept (`india_only`). 20 companies preset. |
| Big-company careers sites | Workday career sites (robots.txt explicitly allows them and publishes job sitemaps), amazon.jobs search (only `/internal` disallowed), Microsoft's `/api/pcsx` (explicitly allowed in robots.txt) | Salesforce, NVIDIA, Adobe, Autodesk, Target, Workday, Amazon, Microsoft. Workday is queried for Bengaluru first, because multi-city postings only say "3 Locations". Microsoft rate-limits, so it gets 2 requests per scan. |
| Wellfound | Public role pages allowed by `robots.txt` | Very few internships on public pages. |

Checked and **not** used, because their terms forbid automated collection: Internshala
("data mining or similar data gathering"), Cutshort ("systematic or automated data collection"; its API is
recruiters-only), HireHire ("scrape, copy, or resell data"). startup.jobs only exposes jobs through its
own site search and has no feed. Google careers is excluded because its robots.txt disallows the job
search results; Intuit's job search is disallowed and its Workday site requires login.

## How it works

```
backend/app/
  sources/            one file per source + settings_file.py (config/sources.json schema)
  normalize.py        job type, category, location, URL normalization (deterministic rules)
  dedup.py            fingerprints and new-job detection
  filters.py          filter matching
  notifications.py    channels: browser, telegram (record first, deliver second)
  scanner.py          fetch → dedup → filter → store → notify, per source
  export.py           public/*.json for the hosted dashboard
  cli.py              `scan` / `deliver` commands used by GitHub Actions
scripts/state_*.sh    restore/save the data branch (refuses to start from empty state if GitHub is unreachable)
frontend/
  src/services/       localApi (FastAPI) and hostedApi (GitHub JSON + Vercel functions)
  api/                Vercel functions: settings.js, scan.js
config/               settings.json, sources.json
```

### Key decisions
- **Every seen job is stored, matching or not**, so widening filters never re-announces old jobs.
- **Two identities per job:**
  - `fingerprint` = source + id. If there is no id, the canonical URL is used, and if there is no URL either, company + title + location.
  - `content_key` = company + title + location, ignoring the source. It catches reposts and the same job on two sites.

  A job is new only if both are unseen.
- **Save, then send.** The workflow saves scan results before sending Telegram messages, and saves again
  after. A crash can at worst retry unsent alerts; it never loses or duplicates a job.
- **`data` branch = one force-pushed commit**, so an hourly database doesn't bloat git history.
- **Categories come from the job title.** Hints like team names only refine them, and non-engineering
  titles ("Content", "Operations", "Support") are always Other.
- **Filter rules exist only in Python.** The export precomputes match flags and location tags, and the dashboard just displays them.
