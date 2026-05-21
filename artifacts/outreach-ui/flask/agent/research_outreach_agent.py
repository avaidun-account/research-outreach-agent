import os, csv, json, time, random, sqlite3, re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from anthropic import Anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
YOUR_NAME     = "Arjun Vaidun"
YOUR_EMAIL    = "a.vaidun@gmail.com"
YOUR_SCHOOL   = "UC Riverside"
YOUR_YEAR     = "sophomore"
YOUR_MAJOR    = "Psychology"
PORTFOLIO_URL = "https://avaidun-account.github.io"
DAILY_LIMIT   = 20
DELAY         = (2, 5)
DB_FILE       = "outreach.db"
DRAFTS_FILE = "/home/runner/workspace/artifacts/outreach-ui/flask/data/drafts.csv"

RELEVANCE_KEYWORDS = [
    "neuroscience","neurology","neurological","cognitive","parkinson",
    "traumatic brain","tbi","concussion","alzheimer","dementia",
    "brain","neural","fmri","neuroimaging","health","clinical",
    "behavioral","psychiatry","mental health","artificial intelligence",
    "machine learning","computational","ai","bias","equity",
    "health disparities","health technology","decision making",
    "aging","pediatric","developmental","social neuroscience",
]

DIRECTORIES = [
    ("UCLA",         "https://www.psych.ucla.edu/faculty/"),
    ("UCLA",         "https://www.psych.ucla.edu/directory/all/"),
    ("UC San Diego", "https://psychology.ucsd.edu/people/faculty.html"),
    ("USC",          "https://dornsife.usc.edu/psyc/faculty/"),
    ("USC",          "https://dornsife.usc.edu/psyc/brain-and-cognitive-science-faculty/"),
    ("USC",          "https://dornsife.usc.edu/psyc/clinical-faculty/"),
    ("UCI", "https://www.faculty.uci.edu/profile.cfm?search_type=dept&dept=Psychological+Science"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, title TEXT, institution TEXT,
        email TEXT, profile_url TEXT, research_focus TEXT,
        subject TEXT, email_body TEXT,
        status TEXT DEFAULT 'drafted', created_at TEXT)""")
    conn.commit()
    return conn

def already_exists(conn, name, institution):
    return conn.execute("SELECT id FROM leads WHERE name=? AND institution=?", (name, institution)).fetchone() is not None

def save_lead(conn, d):
    conn.execute("""INSERT INTO leads (name,title,institution,email,profile_url,research_focus,subject,email_body,status,created_at)
        VALUES (:name,:title,:institution,:email,:profile_url,:research_focus,:subject,:email_body,'drafted',:created_at)""", d)
    conn.commit()

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"    [!] Fetch failed: {url} — {e}")
        return None

def is_relevant(text):
    t = text.lower()
    return any(kw in t for kw in RELEVANCE_KEYWORDS)

def scrape_directory(institution, url):
    soup = fetch_page(url)
    if not soup:
        return []
    base = "/".join(url.split("/")[:3])
    raw = []
    candidates = (soup.find_all("article") or
                  soup.find_all(class_=re.compile(r"faculty|person|profile|member", re.I)) or
                  soup.find_all("li", class_=re.compile(r"faculty|person|member", re.I)))
    if candidates:
        for el in candidates:
            text = el.get_text(" ", strip=True)
            if len(text) < 10:
                continue
            link = el.find("a", href=True)
            profile_url = ""
            if link:
                href = link["href"]
                profile_url = href if href.startswith("http") else base + "/" + href.lstrip("/")
            raw.append({"text": text, "profile_url": profile_url, "institution": institution})
    else:
        for row in soup.find_all(["p", "tr", "div"]):
            text = row.get_text(" ", strip=True)
            if "@" in text and len(text) > 20:
                raw.append({"text": text, "profile_url": url, "institution": institution})
    relevant = [r for r in raw if is_relevant(r["text"])]
    print(f"    {len(raw)} entries → {len(relevant)} relevant")
    return relevant

def scrape_profile(profile_url, base_url):
    if not profile_url or profile_url == base_url:
        return ""
    base = "/".join(base_url.split("/")[:3])
    if not profile_url.startswith(base):
        return ""
    soup = fetch_page(profile_url)
    if not soup:
        return ""
    return soup.get_text(" ", strip=True)[:1500]

client = Anthropic()

SYSTEM_PROMPT = f"""You are a research outreach assistant helping {YOUR_NAME}, a {YOUR_YEAR} Psychology major at {YOUR_SCHOOL}, find summer research and internship opportunities.

Arjun's background:
- Psychology major at UC Riverside, strong coursework in psychology and neuroscience
- Research interests: AI in health tech, neurological health (motivated by two family members with Parkinson's disease and a sibling with multiple concussions), gender bias in healthcare AI
- Built PlateSwap — live iOS/Android nutrition app using GPT-4o Vision (plateswap.replit.app)
- Built MedSpa Outreach Agent — end-to-end AI sales automation pipeline
- Built Morning Brief Agent — daily AI briefing via GitHub Actions + Claude
- COPE Health Scholar (hospital clinical placement, 2025-present)
- Research team member, Althea Labs AI (gender bias in healthcare AI)
- Tennis coach for neurodivergent youth with autism, 2+ years
- Stanford CASP clinical anatomy program alumnus
- NASM CPT in progress, AMSA/APA/Neuroscience Club member
- Portfolio: {PORTFOLIO_URL}

Draft a short cold email from Arjun to this faculty member.

Rules:
- 150-200 words MAX
- First sentence: one specific observation about THEIR research
- Connect Parkinson/concussion motivation when research is neurological
- Lead with PlateSwap or AI agent work as credential hook
- Ask for ONE thing: 15-min call or any opening (volunteer or paid)
- Tone: confident, direct — he has real shipped projects
- Subject: specific, under 10 words, no cliches
- Do NOT mention GPA

Return ONLY valid JSON, nothing else:
{{"name":"Dr. First Last","title":"their title or Unknown","email":"their email or Unknown","research_focus":"2-4 words","subject":"subject line","body":"email body only"}}"""

def draft_email(raw_text, profile_text, profile_url, institution):
    user_msg = f"Faculty info from {institution}:\nProfile URL: {profile_url}\nDirectory text: {raw_text[:800]}\nProfile content: {profile_text[:800] if profile_text else 'Not available'}\n\nExtract info and draft Arjun's cold email."
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=900,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"    [!] Draft error: {e}")
        return None

FIELDS = ["name","title","institution","email","profile_url","research_focus","subject","body","status"]

def write_header():
    with open(DRAFTS_FILE, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()

def append_row(d):
    with open(DRAFTS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(d)

def run():
    print(f"\n{'='*60}\n  Research Outreach Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n  Limit: {DAILY_LIMIT} | Output: {DRAFTS_FILE}\n{'='*60}\n")
    conn = init_db()
    write_header()
    dirs = DIRECTORIES.copy()
    random.shuffle(dirs)
    total = 0
    for institution, url in dirs:
        if total >= DAILY_LIMIT:
            break
        print(f"\n→ {institution}")
        entries = scrape_directory(institution, url)
        random.shuffle(entries)
        for entry in entries:
            if total >= DAILY_LIMIT:
                break
            time.sleep(random.uniform(*DELAY))
            profile_text = scrape_profile(entry["profile_url"], url)
            if profile_text:
                time.sleep(random.uniform(1, 2))
            result = draft_email(entry["text"], profile_text, entry["profile_url"], institution)
            if not result:
                continue
            name = result.get("name", "Unknown")
            if not name or name == "Unknown":
                continue
            if already_exists(conn, name, institution):
                print(f"  ↳ Skip: {name}")
                continue
            full_body = result.get("body","") + f"\n\nBest,\n{YOUR_NAME}\n{YOUR_SCHOOL} | {YOUR_MAJOR}\n{YOUR_EMAIL}\n{PORTFOLIO_URL}"
            db_row = {
                "name": name, "title": result.get("title","Unknown"),
                "institution": institution, "email": result.get("email","Unknown"),
                "profile_url": entry["profile_url"] or url,
                "research_focus": result.get("research_focus",""),
                "subject": result.get("subject",""),
                "email_body": full_body, "created_at": datetime.now().isoformat(),
            }
            save_lead(conn, db_row)
            append_row({"name":db_row["name"],"title":db_row["title"],"institution":db_row["institution"],
                        "email":db_row["email"],"profile_url":db_row["profile_url"],
                        "research_focus":db_row["research_focus"],"subject":db_row["subject"],
                        "body":full_body,"status":"REVIEW NEEDED"})
            print(f"  ✓ {name} ({result.get('research_focus','')})")
            print(f"    Subj: {result.get('subject','')}")
            total += 1
    conn.close()
    print(f"\n{'='*60}\n  {total} drafts → {DRAFTS_FILE}\n  Review every email before sending.\n{'='*60}\n")

if __name__ == "__main__":
    run()
