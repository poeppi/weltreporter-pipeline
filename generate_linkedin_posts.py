#!/usr/bin/env python3
"""
Stage 2 — Weltreporter pipeline
Generates LinkedIn posts from newsletter-content.json using Claude Haiku.
Writes linkedin_post and hashtags fields into schedule.json.

Usage (from projects/weltreporter-pipeline/):
  venv/bin/python3 generate_linkedin_posts.py                # skips entries already filled
  venv/bin/python3 generate_linkedin_posts.py --force        # regenerates all
  venv/bin/python3 generate_linkedin_posts.py --url <URL>    # override newsletter URL

Requires: newsletter-content.json (Stage 0).
Creates schedule.json if it doesn't exist yet; otherwise updates existing entries.
"""

import json
import os
import re
import sys
from datetime import datetime

import anthropic

# httpx picks up ALL_PROXY for SOCKS — unset it so the Anthropic SDK uses HTTP_PROXY instead
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)


MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def load_env(path=".env"):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def format_date(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def extract_url_from_schedule(schedule):
    for entry in schedule:
        post = entry.get("linkedin_post", "")
        m = re.search(r"(https?://\S+)", post)
        if m:
            return m.group(1).rstrip(".,")
    return None


def channel_for_article(article):
    city = article.get("city", "")
    article_type = article.get("type", "article")
    if article_type == "editorial":
        return "Neues in der Welt"
    country_map = {
        "Deutschland": "Neues in der Welt",
        "Griechenland": "Europa", "Tschechien": "Europa", "Frankreich": "Europa",
        "Italien": "Europa", "Russland": "Europa", "Türkei": "Europa",
        "USA": "Nordamerika", "Kanada": "Nordamerika", "Mexiko": "Nordamerika",
        "Kenia": "Afrika", "Nigeria": "Afrika", "Südafrika": "Afrika",
        "Indien": "Ost- und Südostasien", "China": "Ost- und Südostasien",
        "Japan": "Ost- und Südostasien", "Indonesien": "Ost- und Südostasien",
        "Irak": "Naher und Mittlerer Osten", "Iran": "Naher und Mittlerer Osten",
        "Israel": "Naher und Mittlerer Osten",
        "Brasilien": "Südamerika", "Argentinien": "Südamerika",
    }
    for country, channel in country_map.items():
        if country in city:
            return channel
    return "Neues in der Welt"


def generate_linkedin_post(article, date_str, newsletter_url, client):
    article_type = article.get("type", "article")
    headline = article.get("headline") or "(Editorial)"
    author = article.get("author", "")
    city = article.get("city", "")
    text = article.get("text", "")
    date_formatted = format_date(date_str)

    if article_type == "editorial":
        type_instruction = (
            "This is an editorial introduction by the editor. "
            "Hook (1-2 lines): name the newsletter's monthly theme directly. "
            "Body: tease exactly 2 of the most striking stories — one sentence each. No more. "
            "Keep it short: hook + 2 teasers + credit + footer must fit in 1.300 characters total."
        )
    else:
        type_instruction = (
            "Hook (lines 1-2): the single strongest fact or question from the article. "
            "No warm-up sentence. LinkedIn truncates after ~3 lines; the hook must stand alone. "
            "Body (3-6 sentences): not a summary — what is the one thing that sticks?"
        )

    prompt = f"""Write a LinkedIn post for this Weltreporter newsletter article. Output XML only — no explanation.

Rules:
- Language: German
- {type_instruction}
- Credit line: "Von {author}, Weltreporter-Korrespondent:in in {city}."
- Footer (exact wording): "Dieser Beitrag ist erschienen im Weltreporter Newsletter vom {date_formatted}. Hier geht es zur kompletten Ausgabe: {newsletter_url}"
- Hashtags: 3-5, topically relevant, in German. Always include #Weltreporter. Add 2-4 more based on topic.
- Total length: max 1.300 characters (body + credit + footer + hashtags combined).
- No cliché openings: no "In einer Welt...", "Immer mehr Menschen...", "In unserer schnelllebigen..."
- No "Nicht X, sondern Y" constructions. State things directly.

Article:
Headline: {headline}
Author: {author}
City: {city}
Text: {text[:3000]}

Output format (XML, nothing else):
<result>
<body>full post text including credit line and footer, no hashtags here</body>
<hashtags>#Weltreporter #Tag2 #Tag3</hashtags>
</result>"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()

    body_m = re.search(r"<body>(.*?)</body>", raw, re.DOTALL)
    tags_m = re.search(r"<hashtags>(.*?)</hashtags>", raw, re.DOTALL)

    if not body_m:
        print(f"  ! Kein <body> in Antwort. Rohausgabe: {raw[:200]}")
        return None, []

    body = body_m.group(1).strip()
    hashtags_raw = tags_m.group(1).strip() if tags_m else "#Weltreporter"
    hashtags = [t.strip() for t in hashtags_raw.split() if t.startswith("#")]

    full_post = body + "\n\n" + " ".join(hashtags)
    return full_post, hashtags


def build_schedule_entry(i, article, date_str):
    """Create a new schedule.json entry for an article."""
    from datetime import datetime, timedelta
    base = datetime.strptime(date_str, "%Y-%m-%d")
    posting_date = (base + timedelta(days=i)).strftime("%Y-%m-%d")
    return {
        "tag": i + 1,
        "datum": posting_date,
        "kanal": channel_for_article(article),
        "titel": article.get("headline") or article.get("author", "Editorial"),
        "autor": article.get("author", ""),
        "stadt": article.get("city", "").split(",")[0].strip(),
        "circle_post": "",
        "linkedin_post": "",
        "hashtags": [],
        "posted_circle": False,
        "posted_linkedin": False,
    }


def main():
    force = "--force" in sys.argv

    newsletter_url_override = None
    if "--url" in sys.argv:
        idx = sys.argv.index("--url")
        try:
            newsletter_url_override = sys.argv[idx + 1]
        except IndexError:
            raise SystemExit("Verwendung: generate_linkedin_posts.py --url <URL>")

    env = load_env()
    anthropic_key = env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise SystemExit("ANTHROPIC_API_KEY fehlt.")

    print("Lade newsletter-content.json ...")
    try:
        newsletter = load_json("newsletter-content.json")
    except FileNotFoundError:
        raise SystemExit("newsletter-content.json nicht gefunden. Erst Stage 0 ausführen.")

    articles = newsletter["articles"]
    date_str = newsletter["date"]

    # Load or create schedule.json
    try:
        schedule = load_json("schedule.json")
    except FileNotFoundError:
        print("schedule.json nicht gefunden — wird neu erstellt.")
        schedule = [build_schedule_entry(i, a, date_str) for i, a in enumerate(articles)]

    newsletter_url = newsletter_url_override or extract_url_from_schedule(schedule)
    if not newsletter_url:
        raise SystemExit(
            "Newsletter-URL nicht gefunden. Bitte angeben: --url <URL>"
        )

    print(f"Newsletter: {newsletter['campaign_name']} ({date_str})")
    print(f"URL: {newsletter_url}")
    print(f"Artikel: {len(articles)}\n")

    client = anthropic.Anthropic(api_key=anthropic_key)
    updated = 0

    for i, entry in enumerate(schedule):
        tag = entry["tag"]

        if entry.get("linkedin_post") and not force:
            print(f"  → Tag {tag}: übersprungen (bereits befüllt)")
            continue

        if i >= len(articles):
            print(f"  ! Tag {tag}: kein passender Artikel")
            continue

        article = articles[i]
        titel = entry.get("titel") or article.get("headline") or "Editorial"
        print(f"  Generiere Tag {tag}: {titel[:55]} ...")

        post, hashtags = generate_linkedin_post(article, date_str, newsletter_url, client)
        if post:
            entry["linkedin_post"] = post
            entry["hashtags"] = hashtags
            char_count = len(post)
            flag = " ⚠ zu lang" if char_count > 1300 else ""
            print(f"  ✓ Tag {tag}: {char_count} Zeichen{flag}")
            updated += 1
        else:
            print(f"  ! Tag {tag}: Generierung fehlgeschlagen")

    save_json("schedule.json", schedule)
    print(f"\n{updated} LinkedIn-Posts generiert. schedule.json aktualisiert.")


if __name__ == "__main__":
    main()
