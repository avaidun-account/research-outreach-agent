"""
Research Outreach Agent — Arjun Vaidun
Finds research/internship opportunities at SoCal institutions,
scrapes PI/contact info, and drafts personalized cold emails.
Run: python research_outreach_agent.py
Output: drafts.csv (review before sending)
"""

import os
import csv
import json
import time
import random
import sqlite3
import requests
from datetime import datetime
from anthropic import Anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")   # set in .env or Replit secrets
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

YOUR_NAME = "Arjun Vaidun"
YOUR_EMAIL = "a.vaidun@gmail.com"
YOUR_SCHOOL = "UC Riverside"
YOUR_YEAR = "sophomore"
YOUR_MAJOR = "Psychology"
PORTFOLIO_URL = "https://avaidun-account.github.io"

# Alternate between focus areas each run
FOCUS_AREAS = [
    "psychology neuroscience research lab",
    "health technology AI healthcare research",
    "cognitive behavioral neurology research",
    "AI bias healthcare equity research",
    "computational psychiatry mental health AI",
    "neurological disorders Parkinson TBI research",
]

# All SoCal institutions — broad net
TARGET_INSTITUTIONS = [
    # UC System
    "UCLA", "UC San Diego", "UC Irvine", "UC Riverside", "UC Santa Barbara",
    # Private universities
    "USC University of Southern California", "Caltech", "LMU Loyola Marymount",
    "Pepperdine University", "Chapman University", "Claremont McKenna",
    # CSU System
    "Cal State Long Beach", "Cal State Fullerton", "Cal State LA", "San Diego State",
    # Hospitals & medical centers
    "Cedars-Sinai Medical Center", "Children's Hospital Los Angeles",
    "Scripps Research Institute", "Salk Institute", "Rady Children's Hospital",
    "UCLA Medical Center", "UCSD Health", "Hoag Hospital", "Providence Saint Joseph",
    # Biotech / research orgs
    "J. Craig Venter Institute San Diego", "Sanford Burnham Prebys",
    "City of Hope National Medical Center", "Kaiser Permanente Southern California",
]

DAILY_LIMIT = 15          # max leads per run
DELAY_BETWEEN = (2, 4)    # seconds between API calls (be polite)
DB_FILE = os.environ.get("DB_FILE", "outreach.db")
DRAFTS_FILE = os.environ.get("DRAFTS_FILE", "drafts.csv")

# ── DATABASE ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            title TEXT,
            institution TEXT,
            email TEXT,
            lab_url TEXT,
            research_focus TEXT,
            subject TEXT,
            email_drafted TEXT,
            status TEXT DEFAULT 'New',
            created_at TEXT
        )
    """)
    conn.commit()
    return conn


def already_contacted(conn, name, institution):
    row = conn.execute(
        "SELECT id FROM leads WHERE name=? AND institution=?",
        (name, institution)
    ).fetchone()
    return row is not None


def save_lead(conn, lead: dict):
    conn.execute("""
        INSERT INTO leads (name, title, institution, email, lab_url,
                           research_focus, subject, email_drafted, status, created_at)
        VALUES (:name, :title, :institution, :email, :lab_url,
                :research_focus, :subject, :email_drafted, 'New', :created_at)
    """, lead)
    conn.commit()

# ── SEARCH ────────────────────────────────────────────────────────────────────

def search_leads(focus: str, institution: str) -> list[dict]:
    """Use SerpAPI to find lab pages, faculty profiles, and research opportunities."""
    if not SERPAPI_KEY:
        print("  [!] No SERPAPI_KEY — using mock data for demo")
        return _mock_leads(focus, institution)

    query = f"{focus} professor lab {institution} site:edu OR site:org"
    params = {
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 5,
        "hl": "en",
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        r.raise_for_status()
        results = r.json().get("organic_results", [])
        leads = []
        for res in results:
            leads.append({
                "snippet": res.get("snippet", ""),
                "url": res.get("link", ""),
                "title_raw": res.get("title", ""),
                "institution": institution,
                "focus": focus,
            })
        return leads
    except Exception as e:
        print(f"  [!] SerpAPI error: {e}")
        return []


def _mock_leads(focus: str, institution: str) -> list[dict]:
    """Mock data for testing without API keys."""
    return [
        {
            "snippet": f"Dr. Jane Smith studies {focus} at {institution}. The lab is accepting undergraduate research assistants for summer 2025.",
            "url": f"https://example.edu/{institution.lower().replace(' ','')}/smith-lab",
            "title_raw": f"Smith Lab — {focus} — {institution}",
            "institution": institution,
            "focus": focus,
        }
    ]

# ── AI EXTRACTION + EMAIL DRAFTING ────────────────────────────────────────────

client = Anthropic()

SYSTEM_PROMPT = f"""You are a research outreach assistant helping {YOUR_NAME}, a {YOUR_YEAR} Psychology major at {YOUR_SCHOOL}, find summer research and internship opportunities.

Arjun's background:
- Psychology major at UC Riverside, strong coursework in psychology and neuroscience
- Research interests: AI in health tech, neurological health (motivated by two family members with Parkinson's and a sibling with multiple concussions), gender bias in healthcare AI
- Built PlateSwap — a live iOS/Android nutrition app using GPT-4o Vision (plateswap.replit.app)
- Built MedSpa Outreach Agent — end-to-end AI sales automation pipeline
- Built Morning Brief Agent — daily AI briefing via GitHub Actions + Claude
- COPE Health Scholar (hospital clinical placement, 2025)
- Research team member at Althea Labs AI (gender bias in healthcare AI)
- Tennis coach for neurodivergent youth (FCSN, 2+ years)
- Stanford CASP clinical anatomy program alumnus
- NASM CPT in progress
- Member: AMSA, APA, Neuroscience Club
- Portfolio: {PORTFOLIO_URL}

Your job:
1. Extract PI/contact info from a search snippet
2. Draft a short, genuine cold email from Arjun to that person

Email rules:
- 150-200 words MAX. Professors skim. Every sentence must earn its place.
- Open with ONE specific thing about their research — not generic flattery
- Connect Arjun's personal motivation (family Parkinson's/concussion experience) naturally if relevant
- Lead with PlateSwap or the AI work — it's his strongest hook
- Ask for a specific, low-friction thing: 15-min call, or to be considered for any volunteer/paid opening
- No groveling. Confident but not arrogant.
- Subject line must be specific and under 10 words
- DO NOT mention GPA

Return ONLY valid JSON, no markdown, no preamble:
{{
  "name": "Dr. First Last or Unknown",
  "title": "their title or Unknown",
  "email": "email if found in snippet or Unknown",
  "lab_url": "url",
  "research_focus": "2-3 word summary of their research",
  "subject": "email subject line",
  "body": "full email body"
}}"""


def extract_and_draft(snippet: str, url: str, institution: str, focus: str) -> dict | None:
    """Send snippet to Claude — extract contact info and draft email."""
    user_msg = f"""Search result from {institution}:
URL: {url}
Snippet: {snippet}
Research focus searched: {focus}

Extract contact info and draft a cold email from Arjun."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}]
        )
        raw = response.content[0].text.strip()
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [!] JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  [!] Claude error: {e}")
        return None

# ── DRAFTS CSV ────────────────────────────────────────────────────────────────

def write_drafts_header():
    with open(DRAFTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "title", "institution", "email", "lab_url",
            "research_focus", "subject", "body", "status"
        ])
        writer.writeheader()


def append_draft(lead: dict):
    with open(DRAFTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "title", "institution", "email", "lab_url",
            "research_focus", "subject", "body", "status"
        ])
        writer.writerow({
            "name": lead["name"],
            "title": lead["title"],
            "institution": lead["institution"],
            "email": lead["email"],
            "lab_url": lead["lab_url"],
            "research_focus": lead["research_focus"],
            "subject": lead.get("subject", ""),
            "body": lead.get("email_drafted", ""),
            "status": "REVIEW NEEDED",
        })

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'='*60}")
    print(f"  Research Outreach Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    conn = init_db()
    write_drafts_header()

    # Pick 3 random focus areas and 5 random institutions this run
    focuses = random.sample(FOCUS_AREAS, 3)
    institutions = random.sample(TARGET_INSTITUTIONS, 5)

    total = 0
    new_leads = 0

    for institution in institutions:
        if total >= DAILY_LIMIT:
            break
        for focus in focuses:
            if total >= DAILY_LIMIT:
                break

            print(f"→ Searching: [{focus}] @ {institution}")
            raw_leads = search_leads(focus, institution)

            for raw in raw_leads:
                if total >= DAILY_LIMIT:
                    break

                time.sleep(random.uniform(*DELAY_BETWEEN))

                result = extract_and_draft(
                    snippet=raw["snippet"],
                    url=raw["url"],
                    institution=institution,
                    focus=focus,
                )

                if not result:
                    continue

                name = result.get("name", "Unknown")
                if name == "Unknown":
                    print(f"  ↳ Skipped — no PI identified")
                    continue

                if already_contacted(conn, name, institution):
                    print(f"  ↳ Skipped — already in DB: {name}")
                    continue

                # Compose the email body with signature
                body = result.get("body", "")
                body += f"\n\nBest,\n{YOUR_NAME}\n{YOUR_SCHOOL} | {YOUR_MAJOR}\n{YOUR_EMAIL}\n{PORTFOLIO_URL}"

                db_lead = {
                    "name": name,
                    "title": result.get("title", "Unknown"),
                    "institution": institution,
                    "email": result.get("email", "Unknown"),
                    "lab_url": result.get("lab_url", raw["url"]),
                    "research_focus": result.get("research_focus", focus),
                    "subject": result.get("subject", ""),
                    "email_drafted": body,
                    "created_at": datetime.now().isoformat(),
                }

                save_lead(conn, db_lead)

                draft_row = {**db_lead, "subject": result.get("subject", ""), "email_drafted": body}
                append_draft(draft_row)

                print(f"  ✓ Drafted: {name} — {result.get('research_focus','')}")
                print(f"    Subject: {result.get('subject','')}")

                new_leads += 1
                total += 1

    conn.close()

    print(f"\n{'='*60}")
    print(f"  Done. {new_leads} new drafts → {DRAFTS_FILE}")
    print(f"  Review drafts.csv before sending anything.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()
