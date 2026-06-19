# Vercel Migration Handoff

## What We Did

We migrated the portfolio dashboard from a Streamlit-only app toward a Vercel-ready web app.

The original Python/Streamlit dashboard still exists, but the new shareable frontend now lives in `web/` as a Next.js app. Python remains the data engine. It pulls market data, calculates portfolio metrics, generates AI commentary, and exports a static JSON file that the Next.js app reads.

## Architecture Pattern

```text
Python analytics + data refresh
        ↓
web/public/data/dashboard.json
        ↓
Next.js frontend in web/
        ↓
Vercel deployment
```

This lets us keep the trusted Python calculation layer while replacing the Streamlit UI with a polished HTML/CSS/React dashboard.

## Key Files

- `jobs/export_dashboard_data.py`
  Exports the full dashboard data contract to `web/public/data/dashboard.json`.

- `web/app/page.jsx`
  Main React dashboard UI.

- `web/app/globals.css`
  Dashboard visual system and responsive styling.

- `web/public/data/dashboard.json`
  Static data artifact served by Vercel.

- `.github/workflows/generate_daily_insight.yml`
  Runs every 6 hours, refreshes data/commentary, exports dashboard JSON, and commits the updated artifacts.

- `web/README.md`
  Local dev and Vercel setup instructions.

## Vercel Settings

When importing the repo into Vercel:

```text
Framework: Next.js
Root Directory: web
Build Command: npm run build
Install Command: npm install
Output Directory: Next.js default
```

No Vercel environment variables are needed for the frontend. The OpenAI key belongs in GitHub Actions secrets because the data generation happens in GitHub Actions.

## Refresh Behavior

The GitHub Action runs every 6 hours:

1. installs Python dependencies
2. runs `jobs/generate_daily_insight.py --force`
3. runs `jobs/export_dashboard_data.py`
4. commits `data/daily_insight.json` and `web/public/data/dashboard.json`
5. Vercel redeploys from the new commit

The site stays live on Vercel and does not sleep like Streamlit Community Cloud.

## Important Lessons

- Keep Streamlit untouched during the first migration. Treat it as legacy/reference until the web version is stable.
- Export a single static JSON contract first. Do not rewrite the Python analytics layer unless needed.
- Strip internal errors from public JSON artifacts before deploying.
- Add `OPENAI_API_KEY` to GitHub repository secrets, not Vercel.
- Test the workflow manually after updating secrets.
- Use GitHub CLI auth locally so Codex/terminal can push:

```bash
brew install gh
gh auth login
```

## Validation Commands

From `web/`:

```bash
npm run lint
npm run build
```

From repo root:

```bash
python jobs/export_dashboard_data.py
python -m json.tool web/public/data/dashboard.json
```

## Reusable Migration Plan For Another App

1. Identify the current Streamlit data/calculation outputs.
2. Add an export script that writes a stable JSON file under `web/public/data/`.
3. Scaffold a Next.js app in `web/`.
4. Build the frontend against the exported JSON, not live Python.
5. Add a scheduled GitHub Action to refresh the JSON.
6. Deploy `web/` to Vercel.
7. Keep Streamlit until the Vercel app is verified.
