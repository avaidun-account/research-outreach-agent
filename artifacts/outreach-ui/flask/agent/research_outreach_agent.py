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
DELAY         = (2, 4)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_FILE     = os.environ.get("DB_FILE",     os.path.join(BASE_DIR, "..", "data", "outreach.db"))
DRAFTS_FILE = os.environ.get("DRAFTS_FILE", os.path.join(BASE_DIR, "..", "data", "drafts.csv"))

RELEVANCE_KEYWORDS = [
    "neuroscience","neurology","neurological","cognitive","parkinson",
    "traumatic brain","tbi","concussion","alzheimer","dementia",
    "brain","neural","fmri","neuroimaging","health","clinical",
    "behavioral","psychiatry","mental health","artificial intelligence",
    "machine learning","computational","ai","bias","equity",
    "health disparities","health technology","decision making",
    "aging","pediatric","developmental","social neuroscience",
    "psychology","psychophysiology",
]

# Verified static-HTML faculty pages.
# trusted=True → entire dept is relevant, skip card-text keyword filter,
#                check relevance from profile page instead.
DIRECTORIES = [
    # Caltech Biology, Biological Engineering & Neuroscience — rich neuro faculty
    {
        "institution": "Caltech",
        "url": "https://www.bbe.caltech.edu/people/faculty",
        "trusted": True,
        "mode": "caltech",       # custom scraper
    },
    # SDSU Psychology — table rows, each with a profile link
    {
        "institution": "SDSU",
        "url": "https://psychology.sdsu.edu/about-the-department/faculty/",
        "trusted": True,
        "mode": "sdsu",
    },
    # UCSD Cognitive Science — <p class=h3> per faculty, profile links like name.html
    {
        "institution": "UC San Diego",
        "url": "https://cogsci.ucsd.edu/people/faculty/index.html",
        "trusted": True,
        "mode": "ucsd_cogsci",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── DATABASE ──────────────────────────────────────────────────────────────────

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
    return conn.execute(
        "SELECT id FROM leads WHERE name=? AND institution=?", (name, institution)
    ).fetchone() is not None

def save_lead(conn, d):
    conn.execute("""INSERT INTO leads
        (name,title,institution,email,profile_url,research_focus,subject,email_body,status,created_at)
        VALUES (:name,:title,:institution,:email,:profile_url,:research_focus,:subject,:email_body,'drafted',:created_at)""", d)
    conn.commit()

# ── SCRAPING ──────────────────────────────────────────────────────────────────

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

def extract_email(text):
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return m.group(0) if m else "Unknown"

# Nav-link slugs to exclude from Caltech people pages
_CALTECH_NAV = {
    "/people/faculty", "/people/emeritus", "/people/affiliated",
    "/people/memoriam", "/people/staff", "/people/staff/lecturer",
    "/people/staff/professional-staff", "/people/staff/division-contacts",
}

def scrape_caltech(url, institution):
    """Extracts individual faculty by finding /people/<slug> links."""
    soup = fetch_page(url)
    if not soup:
        return []
    base = "https://www.bbe.caltech.edu"
    slug_re = re.compile(r"^/people/[a-z][a-z\-]+$")
    seen = set()
    entries = []
    for a in soup.find_all("a", href=slug_re):
        slug = a["href"]
        if slug in _CALTECH_NAV or slug in seen:
            continue
        seen.add(slug)
        # Walk up to find a text block with name + title
        container = a
        for _ in range(6):
            if container is None:
                break
            text = container.get_text(" ", strip=True)
            if len(text) > 30:
                break
            container = container.parent
        entries.append({
            "text": (text or "")[:600],
            "profile_url": base + slug,
            "institution": institution,
        })
    print(f"    Caltech: {len(entries)} faculty found")
    return entries


def scrape_sdsu(url, institution):
    """SDSU: faculty are in <tr> rows each containing a /people/<name> link."""
    soup = fetch_page(url)
    if not soup:
        return []
    profile_re = re.compile(r"psychology\.sdsu\.edu/people/")
    seen = set()
    entries = []
    for row in soup.find_all("tr"):
        link = row.find("a", href=profile_re)
        if not link:
            continue
        profile_url = link["href"]
        if profile_url in seen:
            continue
        seen.add(profile_url)
        text = row.get_text(" ", strip=True)
        entries.append({"text": text[:600], "profile_url": profile_url, "institution": institution})
    print(f"    SDSU: {len(entries)} faculty rows found")
    return entries


def scrape_ucsd_cogsci(url, institution):
    """UCSD CogSci: faculty in parent containers of <p class='h3'> with a .html link."""
    soup = fetch_page(url)
    if not soup:
        return []
    base = "https://cogsci.ucsd.edu/people/faculty"
    seen = set()
    entries = []
    name_re = re.compile(r"^[a-z][a-z\-]+\.html$")
    for p in soup.find_all("p", class_="h3"):
        a = p.find("a", href=name_re)
        if not a:
            continue
        href = a["href"]
        if href in seen:
            continue
        seen.add(href)
        container = p.parent or p
        text = container.get_text(" ", strip=True)
        profile_url = f"{base}/{href}"
        entries.append({"text": text[:600], "profile_url": profile_url, "institution": institution})
    print(f"    UCSD CogSci: {len(entries)} faculty found")
    return entries


def scrape_standard(url, institution, trusted):
    soup = fetch_page(url)
    if not soup:
        return []
    base = "/".join(url.split("/")[:3])
    raw = []
    candidates = (
        soup.find_all("article") or
        soup.find_all(class_=re.compile(r"faculty|person|profile|member|staff|people|card|directory", re.I)) or
        soup.find_all("li", class_=re.compile(r"faculty|person|member|people", re.I))
    )
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
        # Fallback: rows/divs that contain an @-email
        for row in soup.find_all(["p", "tr", "div"]):
            text = row.get_text(" ", strip=True)
            if "@" in text and len(text) > 20:
                raw.append({"text": text, "profile_url": url, "institution": institution})

    if trusted:
        # Keep anything with a usable profile URL; relevance will be checked via profile
        relevant = [r for r in raw if r.get("profile_url") and r["profile_url"] != url]
        # Fallback: if no profile links, keep everything and let AI decide
        if not relevant:
            relevant = raw
    else:
        relevant = [r for r in raw if is_relevant(r["text"])]

    print(f"    {len(raw)} entries → {len(relevant)} kept")
    return relevant


_ALLOWED_PROFILE_DOMAINS = {
    "https://www.bbe.caltech.edu",
    "https://psychology.sdsu.edu",
    "https://cogsci.ucsd.edu",
}

def scrape_profile(profile_url, directory_url):
    """Fetch profile page text; skip if off-domain or same as directory."""
    if not profile_url or profile_url == directory_url:
        return ""
    dir_base = "/".join(directory_url.split("/")[:3])
    prof_base = "/".join(profile_url.split("/")[:3])
    if prof_base not in (_ALLOWED_PROFILE_DOMAINS | {dir_base}):
        return ""
    soup = fetch_page(profile_url)
    if not soup:
        return ""
    return soup.get_text(" ", strip=True)[:2000]

# ── AI DRAFTING ───────────────────────────────────────────────────────────────

client = Anthropic()

SYSTEM_PROMPT = f"""You are a research outreach assistant helping {YOUR_NAME}, a {YOUR_YEAR} Psychology major at {YOUR_SCHOOL}.

Arjun's background:
- Psychology major at UC Riverside, strong neuroscience coursework
- Research interests: AI in health tech, neurological health (two family members with Parkinson's, sibling with multiple concussions), gender bias in healthcare AI
- Built PlateSwap — live iOS/Android nutrition app using GPT-4o Vision
- Built MedSpa Outreach Agent — end-to-end AI sales automation (Python, Claude API, Flask)
- Built Morning Brief Agent — daily AI briefing via GitHub Actions + Claude
- COPE Health Scholar (hospital clinical placement, 2025-present)
- Research team member, Althea Labs AI (gender bias in healthcare AI)
- Tennis coach for neurodivergent youth with autism, 2+ years
- Stanford CASP clinical anatomy program alumnus
- AMSA/APA/Neuroscience Club member
- Portfolio: {PORTFOLIO_URL}

Draft a short cold email from Arjun to this faculty member.

Rules:
- 150-200 words MAX. Every sentence earns its place.
- First sentence: one specific genuine observation about THEIR research
- Connect Parkinson/concussion motivation naturally when research is neurological
- Lead with PlateSwap or AI agent work as the credential hook
- Ask for ONE thing: 15-min call or consideration for any opening
- Tone: confident, direct — he has real shipped projects, not just coursework
- Subject: specific, under 10 words, no "Prospective Research Assistant" cliché
- Do NOT mention GPA

If this person's research is NOT relevant to neuroscience, brain health, AI in health, or cognitive science, set "skip": true.

Return ONLY valid JSON, no markdown:
{{"skip": false, "name": "Dr. First Last", "title": "their title or Unknown", "email": "their email or Unknown", "research_focus": "2-4 word summary", "subject": "subject line", "body": "email body only"}}"""


def draft_email(raw_text, profile_text, profile_url, institution):
    user_msg = (
        f"Faculty info from {institution}:\n"
        f"Profile URL: {profile_url}\n"
        f"Directory text: {raw_text[:600]}\n"
        f"Profile content: {profile_text[:1200] if profile_text else 'Not available'}\n\n"
        "Extract this faculty member's info and draft Arjun's cold email. "
        "If their research isn't relevant, set skip: true."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
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

# ── CSV ───────────────────────────────────────────────────────────────────────

FIELDS = ["name","title","institution","email","profile_url","research_focus","subject","body","status"]

def write_header():
    os.makedirs(os.path.dirname(DRAFTS_FILE), exist_ok=True)
    with open(DRAFTS_FILE, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()

def append_row(d):
    with open(DRAFTS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(d)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'='*60}")
    print(f"  Research Outreach Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Limit: {DAILY_LIMIT} | DB: {DB_FILE}")
    print(f"{'='*60}\n")

    conn = init_db()
    write_header()

    dirs = DIRECTORIES.copy()
    random.shuffle(dirs)
    total = 0

    for d in dirs:
        if total >= DAILY_LIMIT:
            break
        institution = d["institution"]
        url = d["url"]
        trusted = d.get("trusted", False)
        mode = d.get("mode", "standard")

        print(f"\n→ {institution} ({url})")

        if mode == "caltech":
            entries = scrape_caltech(url, institution)
        elif mode == "sdsu":
            entries = scrape_sdsu(url, institution)
        elif mode == "ucsd_cogsci":
            entries = scrape_ucsd_cogsci(url, institution)
        else:
            entries = scrape_standard(url, institution, trusted)

        random.shuffle(entries)

        for entry in entries:
            if total >= DAILY_LIMIT:
                break

            time.sleep(random.uniform(*DELAY))

            profile_text = scrape_profile(entry["profile_url"], url)
            if profile_text:
                time.sleep(random.uniform(1, 2))

            # For trusted dirs: check relevance via profile text before calling AI
            if trusted and not is_relevant(entry["text"] + " " + profile_text):
                continue

            result = draft_email(entry["text"], profile_text, entry["profile_url"], institution)
            if not result or result.get("skip"):
                continue

            name = result.get("name", "Unknown")
            if not name or name in ("Unknown", ""):
                continue

            if already_exists(conn, name, institution):
                print(f"  ↳ Skip (exists): {name}")
                continue

            full_body = (
                result.get("body", "") +
                f"\n\nBest,\n{YOUR_NAME}\n{YOUR_SCHOOL} | {YOUR_MAJOR}\n{YOUR_EMAIL}\n{PORTFOLIO_URL}"
            )
            db_row = {
                "name": name,
                "title": result.get("title", "Unknown"),
                "institution": institution,
                "email": result.get("email", "Unknown"),
                "profile_url": entry["profile_url"] or url,
                "research_focus": result.get("research_focus", ""),
                "subject": result.get("subject", ""),
                "email_body": full_body,
                "created_at": datetime.now().isoformat(),
            }
            save_lead(conn, db_row)
            append_row({**db_row, "body": full_body, "status": "REVIEW NEEDED"})

            print(f"  ✓ {name} ({result.get('research_focus', '')})")
            print(f"    Subj: {result.get('subject', '')}")
            if result.get("email", "Unknown") != "Unknown":
                print(f"    Email: {result['email']}")
            total += 1

    conn.close()
    print(f"\n{'='*60}")
    print(f"  {total} drafts saved → {DRAFTS_FILE}")
    print(f"  Review every email before sending.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()
