"""
Research Outreach Agent - Arjun Vaidun
Targets: faculty, PhD students, and AI-healthcare companies.
Drafts personalized cold emails via Gemini.

Run:  python research_outreach_agent.py
Output: drafts.csv  -- review before sending anything
"""

import os, csv, json, time, random, sqlite3, re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from google import genai
from google.genai import types

# -- CONFIG -------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

YOUR_NAME = "Arjun Vaidun"
YOUR_EMAIL = "a.vaidun@gmail.com"
YOUR_SCHOOL = "UC Riverside"
YOUR_YEAR = "sophomore"
YOUR_MAJOR = "Psychology"
PORTFOLIO_URL = "https://avaidun-account.github.io"

DAILY_LIMIT = 20
DELAY = (2, 5)
DB_FILE = "outreach.db"
DRAFTS_FILE = "drafts.csv"

RELEVANCE_KEYWORDS = [
    "neuroscience", "neurology", "neurological", "cognitive",
    "parkinson", "traumatic brain", "tbi", "concussion",
    "alzheimer", "dementia", "brain", "neural", "fmri", "neuroimaging",
    "health", "clinical", "behavioral", "psychiatry", "mental health",
    "artificial intelligence", "machine learning", "computational", "ai",
    "bias", "equity", "health disparities", "health technology",
    "decision making", "decision-making", "aging", "pediatric",
    "developmental", "social neuroscience", "psychophysiology",
]

COMPANY_KEYWORDS = [
    "research", "science", "clinical", "data", "machine learning", "ai",
    "engineer", "product", "health", "behavioral", "psychology", "neuroscience",
    "physician", "therapist", "psychiatry", "intern", "fellow",
]

# Format: (target_type, label, url)
# target_type is one of: "faculty", "phd", "company"

FACULTY_DIRS = [
    ("faculty", "UCLA",         "https://www.psych.ucla.edu/faculty/"),
    ("faculty", "UCLA",         "https://www.psych.ucla.edu/directory/all/"),
    ("faculty", "UC San Diego", "https://psychology.ucsd.edu/people/faculty.html"),
    ("faculty", "USC",          "https://dornsife.usc.edu/psyc/faculty/"),
    ("faculty", "USC",          "https://dornsife.usc.edu/psyc/brain-and-cognitive-science-faculty/"),
    ("faculty", "USC",          "https://dornsife.usc.edu/psyc/clinical-faculty/"),
    ("faculty", "UC Riverside", "https://psychology.ucr.edu/professors"),
    ("faculty", "Salk Institute", "https://www.salk.edu/scientists/laboratories/"),
    ("faculty", "City of Hope",
     "https://www.cityofhope.org/research/beckman-research-institute/research-departments-and-divisions/neurosciences"),
    ("faculty", "Cedars-Sinai",
     "https://www.cedars-sinai.org/research/departments-institutes/neurological-sciences.html"),
]

PHD_DIRS = [
    ("phd", "UCLA",         "https://www.psych.ucla.edu/graduate/current-students/"),
    ("phd", "UC San Diego", "https://neurosciences.ucsd.edu/students/index.html"),
    ("phd", "USC",          "https://dornsife.usc.edu/psyc/graduate-students/"),
    ("phd", "UC Riverside", "https://psychology.ucr.edu/graduate-students"),
]

COMPANY_DIRS = [
    ("company", "Spring Health",    "https://springhealth.com/about/"),
    ("company", "Woebot Health",    "https://woebothealth.com/team/"),
    ("company", "Lyra Health",      "https://lyrahealth.com/about-us/"),
    ("company", "Alto Neuroscience","https://altoneuroscience.com/team"),
    ("company", "Eleos Health",     "https://eleoshealth.com/about/"),
    ("company", "Osmind",           "https://www.osmind.org/about"),
    ("company", "Brightline",       "https://www.brightlinehealth.com/about"),
    ("company", "Cerebral",         "https://cerebral.com/about"),
    ("company", "SonderMind",       "https://www.sondermind.com/about"),
    ("company", "Headway",          "https://headway.co/about"),
]

ALL_DIRECTORIES = FACULTY_DIRS + PHD_DIRS + COMPANY_DIRS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# -- DATABASE -----------------------------------------------------------------


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT, name TEXT, title TEXT, institution TEXT,
            email TEXT, profile_url TEXT, research_focus TEXT,
            subject TEXT, email_body TEXT,
            status TEXT DEFAULT 'drafted', created_at TEXT
        )
    """)
    conn.commit()
    return conn


def already_exists(conn, name, institution):
    return (
        conn.execute(
            "SELECT id FROM leads WHERE name=? AND institution=?", (name, institution)
        ).fetchone()
        is not None
    )


def save_lead(conn, d):
    conn.execute(
        """
        INSERT INTO leads (target_type, name, title, institution, email, profile_url,
                           research_focus, subject, email_body, status, created_at)
        VALUES (:target_type,:name,:title,:institution,:email,:profile_url,
                :research_focus,:subject,:email_body,'drafted',:created_at)
    """,
        d,
    )
    conn.commit()


# -- SCRAPING -----------------------------------------------------------------


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"    [!] Fetch failed: {url} -- {e}")
        return None


def is_relevant(text, target_type):
    t = text.lower()
    keywords = COMPANY_KEYWORDS if target_type == "company" else RELEVANCE_KEYWORDS
    return any(kw in t for kw in keywords)


def extract_email(text):
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else "Unknown"


def scrape_directory(target_type, institution, url):
    soup = fetch(url)
    if not soup:
        return []

    base = "/".join(url.split("/")[:3])
    raw = []

    candidates = (
        soup.find_all("article")
        or soup.find_all(class_=re.compile(r"faculty|person|profile|member|student|team", re.I))
        or soup.find_all("li", class_=re.compile(r"faculty|person|member|student|team", re.I))
    )

    if candidates:
        for el in candidates:
            text = el.get_text(" ", strip=True)
            if len(text) < 10:
                continue
            link_tag = el.find("a", href=True)
            profile_url = ""
            if link_tag:
                href = link_tag["href"]
                profile_url = href if href.startswith("http") else base + href
            raw.append({
                "text": text,
                "profile_url": profile_url,
                "institution": institution,
                "target_type": target_type,
                "source_url": url,
            })
    else:
        for row in soup.find_all(["p", "tr", "div"]):
            text = row.get_text(" ", strip=True)
            if "@" in text and len(text) > 20:
                raw.append({
                    "text": text,
                    "profile_url": url,
                    "institution": institution,
                    "target_type": target_type,
                    "source_url": url,
                })

    relevant = [r for r in raw if is_relevant(r["text"], target_type)]
    print(f"    {len(raw)} entries -> {len(relevant)} relevant")
    return relevant


def scrape_profile(profile_url):
    if not profile_url:
        return ""
    soup = fetch(profile_url)
    if not soup:
        return ""
    return soup.get_text(" ", strip=True)[:1500]


# -- AI EMAIL DRAFTING --------------------------------------------------------

_genai_client = genai.Client(api_key=GEMINI_API_KEY)

_BACKGROUND = f"""
{YOUR_NAME}'s background:
- Psychology major at UC Riverside, strong coursework in psychology and neuroscience
- Research interests: AI in health tech, neurological health (motivated by two family members with Parkinson's disease and a sibling with multiple concussions), gender bias in healthcare AI
- Built PlateSwap -- live iOS/Android nutrition app using GPT-4o Vision (plateswap.replit.app)
- Built MedSpa Outreach Agent -- end-to-end AI sales automation pipeline (Python, Claude API, SendGrid, Flask)
- Built Morning Brief Agent -- daily AI briefing via GitHub Actions + Claude
- COPE Health Scholar (hospital clinical placement, 2025-present)
- Research team member, Althea Labs AI (gender bias in healthcare AI)
- Tennis coach for neurodivergent youth with autism, 2+ years (FCSN)
- Stanford CASP clinical anatomy program alumnus
- NASM CPT in progress
- Member: AMSA, APA, Neuroscience Club
- Portfolio: {PORTFOLIO_URL}
""".strip()

_JSON_SCHEMA = """
Return ONLY valid JSON, no markdown, no preamble:
{
  "name": "First Last",
  "title": "their title or Unknown",
  "email": "their email if found or Unknown",
  "research_focus": "2-4 word summary",
  "subject": "subject line",
  "body": "email body only, no subject line"
}"""

FACULTY_PROMPT = f"""You are a research outreach assistant helping {YOUR_NAME}, a {YOUR_YEAR} Psychology major at {YOUR_SCHOOL}, find summer research opportunities.

{_BACKGROUND}

Draft a short cold email from Arjun to this FACULTY MEMBER.

Rules:
- 150-200 words MAX. Professors skim.
- First sentence: one specific genuine observation about THEIR research
- Connect Parkinson's/concussion motivation naturally when research is neurological
- Lead with PlateSwap or an AI agent as the credential hook
- Ask for ONE thing: 15-min call or to be considered for any opening (volunteer or paid)
- Tone: confident and direct -- he has real shipped projects, not just coursework
- Subject: specific, under 10 words, no "Prospective Research Assistant" cliche
- Do NOT mention GPA

{_JSON_SCHEMA}"""

PHD_PROMPT = f"""You are helping {YOUR_NAME}, a {YOUR_YEAR} Psychology major at {YOUR_SCHOOL}, reach out to PhD students for lab referrals or openings.

{_BACKGROUND}

Draft a short peer-to-peer email from Arjun to this PhD STUDENT.

Rules:
- 100-150 words MAX. Keep it light and collegial.
- First sentence: one genuine observation about THEIR research area
- Tone: curious and peer-level -- they're a grad student, not a gatekeeper
- Mention Parkinson's/concussion motivation if their work is neurological
- Briefly mention PlateSwap or an AI agent as evidence he builds real things
- Ask for ONE thing: a 10-min chat about their lab experience, or whether they know of openings or could point him toward the right PI
- Do NOT ask for a position directly -- ask for advice or a referral
- Subject: casual, specific, under 8 words

{_JSON_SCHEMA}"""

COMPANY_PROMPT = f"""You are helping {YOUR_NAME}, a {YOUR_YEAR} Psychology major at {YOUR_SCHOOL}, reach out to AI-healthcare companies about internship or research opportunities.

{_BACKGROUND}

Draft a short professional cold email from Arjun to a relevant contact at this COMPANY.

Rules:
- 150-200 words MAX
- First sentence: one specific observation about what THIS company does at the intersection of AI and mental/behavioral health
- Lead credential: PlateSwap (live iOS/Android nutrition app, GPT-4o Vision) or MedSpa Outreach Agent (end-to-end AI sales automation pipeline)
- Tie his psychology background + clinical exposure (COPE Health Scholar, Althea Labs AI) to their mission
- Ask for ONE thing: summer internship, research role, or 15-min call
- Tone: confident and direct -- he ships real products
- Subject: specific, under 10 words, no generic "Internship Inquiry"
- Do NOT mention GPA

{_JSON_SCHEMA}"""

PROMPTS = {
    "faculty": FACULTY_PROMPT,
    "phd":     PHD_PROMPT,
    "company": COMPANY_PROMPT,
}

TARGET_LABELS = {
    "faculty": "faculty member",
    "phd":     "PhD student",
    "company": "company contact",
}


def draft_email(raw_text, profile_text, profile_url, institution, target_type):
    label = TARGET_LABELS.get(target_type, "contact")
    user_msg = (
        f"Info about this {label} from {institution}:\n"
        f"Profile URL: {profile_url}\n"
        f"Directory snippet: {raw_text[:800]}\n"
        f"Profile content: {profile_text[:800] if profile_text else 'Not available'}\n\n"
        f"Extract their info and draft Arjun's cold email."
    )
    try:
        resp = _genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=PROMPTS[target_type]),
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, Exception) as e:
        print(f"    [!] Draft error: {e}")
        return None


# -- CSV ----------------------------------------------------------------------

FIELDS = [
    "target_type", "name", "title", "institution",
    "email", "profile_url", "research_focus", "subject", "body", "status",
]


def write_header():
    with open(DRAFTS_FILE, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def append_row(d):
    with open(DRAFTS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(d)


# -- MAIN ---------------------------------------------------------------------


def run():
    print(f"\n{'=' * 60}")
    print(f"  Research Outreach Agent - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Targets: faculty / PhD students / AI-health companies")
    print(f"  Limit: {DAILY_LIMIT} drafts | Output: {DRAFTS_FILE}")
    print(f"{'=' * 60}\n")

    conn = init_db()
    write_header()

    dirs = ALL_DIRECTORIES.copy()
    random.shuffle(dirs)

    total = 0

    for target_type, institution, url in dirs:
        if total >= DAILY_LIMIT:
            break

        type_label = {"faculty": "Faculty", "phd": "PhD", "company": "Company"}[target_type]
        print(f"\n-> [{type_label}] {institution}")
        entries = scrape_directory(target_type, institution, url)
        random.shuffle(entries)

        for entry in entries:
            if total >= DAILY_LIMIT:
                break

            time.sleep(random.uniform(*DELAY))

            profile_text = ""
            same_domain = (
                entry["profile_url"]
                and entry["profile_url"] != url
                and entry["profile_url"].startswith("/".join(url.split("/")[:3]))
            )
            if same_domain:
                profile_text = scrape_profile(entry["profile_url"])
                time.sleep(random.uniform(1, 2))

            result = draft_email(
                raw_text=entry["text"],
                profile_text=profile_text,
                profile_url=entry["profile_url"],
                institution=institution,
                target_type=target_type,
            )

            if not result:
                continue

            name = result.get("name", "Unknown")
            if name in ("Unknown", ""):
                continue

            if already_exists(conn, name, institution):
                print(f"  ~ Skip (exists): {name}")
                continue

            body = result.get("body", "")
            full_body = (
                body + f"\n\nBest,\n{YOUR_NAME}\n"
                f"{YOUR_SCHOOL} | {YOUR_MAJOR}\n"
                f"{YOUR_EMAIL}\n{PORTFOLIO_URL}"
            )

            db_row = {
                "target_type": target_type,
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

            print(f"  + {name} [{target_type}] ({result.get('research_focus', '')})")
            print(f"    Subj: {result.get('subject', '')}")
            if result.get("email", "Unknown") != "Unknown":
                print(f"    Email: {result['email']}")

            total += 1

    conn.close()
    print(f"\n{'=' * 60}")
    print(f"  {total} drafts -> {DRAFTS_FILE}")
    print(f"  Review every email before sending.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run()
