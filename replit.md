# Research Outreach UI

A single-page web app for managing Arjun Vaidun's SoCal PI research outreach pipeline. Click **Run Agent** to discover PIs, draft emails with Claude, then review/edit/track each lead.

## Run & Operate

- `python3 artifacts/outreach-ui/flask/app.py` — run the Flask app (port from $PORT)
- The app is served via the `artifacts/outreach-ui: web` workflow at `/`

## Stack

- Python 3.11 + Flask (web server + API)
- SQLite (persistent lead storage at `artifacts/outreach-ui/flask/data/outreach.db`)
- Plain HTML/CSS/JS frontend (no build step — served as Jinja2 template)
- Anthropic Claude API (email drafting in the agent)
- SerpAPI (PI discovery; runs in mock mode if key is absent)

## Where things live

- `artifacts/outreach-ui/flask/app.py` — Flask app + API routes
- `artifacts/outreach-ui/flask/templates/index.html` — single-page UI
- `artifacts/outreach-ui/flask/agent/research_outreach_agent.py` — outreach agent
- `artifacts/outreach-ui/flask/data/outreach.db` — SQLite DB (created on first run)
- `artifacts/outreach-ui/flask/data/drafts.csv` — CSV export (written each run)

## API routes (Flask, no `/api` prefix — that path routes to the Node.js server)

- `GET /leads` — list all leads
- `PATCH /leads/<id>` — update a lead (status, email body, subject, etc.)
- `DELETE /leads/<id>` — delete a lead
- `POST /agent/run` — start the agent in a background thread
- `GET /agent/status` — poll agent running state + log tail
- `GET /stats` — counts by status

## Architecture decisions

- Flask serves both the HTML page and JSON API — no separate frontend build needed.
- Routes avoid the `/api` prefix to prevent conflicts with the Node.js API server at `/api`.
- The outreach agent runs in a background thread; the UI polls `/agent/status` every 900ms.
- SQLite is used instead of PostgreSQL — the data is local/personal-use only, no multi-user concurrency needed.
- DB path and drafts path are injected via env vars (`DB_FILE`, `DRAFTS_FILE`) so the agent can be run standalone or from the Flask process.

## Product

- **Header**: Run Agent button + Show/Hide log toggle
- **Stats bar**: Total / New / Reviewed / Sent / Responded counts
- **Filter toolbar**: click to filter by status; free-text search on name/institution/focus
- **Table**: all leads sorted newest-first; click any row to open the detail drawer
- **Drawer**: inline editor for subject, email body, status, contact info; Copy email button; Delete

## User preferences

- Keep it simple — single-page Flask app, no auth, local use only.

## Gotchas

- Flask routes must NOT use `/api` prefix — that path is claimed by the Node.js API server proxy.
- The agent uses `claude-sonnet-4-20250514` — update the model string in the agent script if needed.
- Run the agent 2–3x/week max to avoid spamming the same PIs (SQLite deduplication handles this).

## Pointers

- See the `pnpm-workspace` skill for workspace structure details
- Agent script: original was in `attached_assets/research_outreach_agent.py`
