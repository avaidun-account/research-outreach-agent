# Research Outreach Agent

Finds research and internship opportunities at SoCal institutions — universities, hospitals, and biotech firms — and drafts personalized cold emails for review.

## How It Works

1. **Discovery** — Randomly samples from 6 research focus areas and 20+ SoCal institutions per run, querying Google via SerpAPI
2. **Extraction** — Claude reads each search snippet and extracts the PI name, title, email (if present), and lab URL
3. **Email Drafting** — Claude drafts a personalized cold email (150–200 words) specific to that PI's research
4. **Deduplication** — SQLite DB ensures no PI is contacted twice across runs
5. **Output** — All drafts saved to `drafts.csv` for your review before anything is sent

## Setup

```bash
pip install anthropic requests
```

Add secrets (Replit secrets or `.env`):
```
ANTHROPIC_API_KEY=your_key
SERPAPI_KEY=your_key   # optional — runs in mock mode without it
```

## Run

```bash
python research_outreach_agent.py
```

Outputs `drafts.csv` — open in Excel or Google Sheets, review each email, edit as needed, then send manually.

## Target Scope

**Focus areas (alternated each run):**
- Psychology / neuroscience research
- Health tech / AI in healthcare
- Cognitive behavioral neurology
- AI bias / healthcare equity
- Computational psychiatry
- Neurological disorders (Parkinson's, TBI)

**Institutions:**
- UC System (UCLA, UCSD, UCI, UCR, UCSB)
- Private universities (USC, Caltech, LMU, Chapman, Claremont)
- CSU System (CSULB, CSUF, CSLA, SDSU)
- Hospitals (Cedars-Sinai, CHLA, Hoag, Providence, Kaiser)
- Research institutes (Salk, Scripps, Sanford Burnham, City of Hope)

## Output Format (`drafts.csv`)

| Column | Description |
|---|---|
| `name` | PI / contact name |
| `title` | Their title |
| `institution` | Institution |
| `email` | Email if found, else `Unknown` |
| `lab_url` | Lab or faculty page |
| `research_focus` | 2–3 word research summary |
| `subject` | Drafted email subject |
| `body` | Full email body with signature |
| `status` | Always `REVIEW NEEDED` — you send manually |

## Tips

- Run 2–3x per week for steady pipeline without spamming
- When `email = Unknown`, find the address manually via the lab URL before sending
- Edit emails before sending — Claude drafts a strong base but your personal voice matters
- Leads with direct relevance to Parkinson's or TBI research are worth extra editing time
