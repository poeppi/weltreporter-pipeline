#!/usr/bin/env python3
"""
Stage 1 — Weltreporter pipeline
Generates Circle posts from newsletter-content.json and writes them into schedule.json.

Usage (run from projects/weltreporter-pipeline/):
  venv/bin/python3 generate_circle_posts.py           # skips entries already filled
  venv/bin/python3 generate_circle_posts.py --force   # overwrites all circle_posts
  venv/bin/python3 generate_circle_posts.py --url <URL>  # override newsletter URL

Requires: newsletter-content.json (Stage 0) + schedule.json (Stage 2 or prior run).
"""

import json, re, sys
from datetime import datetime


MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_newsletter_url(schedule):
    for entry in schedule:
        post = entry.get("linkedin_post", "")
        m = re.search(r"(https?://\S+)", post)
        if m:
            return m.group(1).rstrip(".,")
    return None


def format_date(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def format_circle_post(article, tag, kanal, date_str, newsletter_url):
    headline = article.get("headline")
    text = article.get("text", "").strip()
    author = article.get("author", "")
    city = article.get("city", "")
    date_formatted = format_date(date_str)

    parts = []
    if headline:
        parts += [headline, ""]
    parts += [
        text,
        "",
        f"Von {author}, {city}.",
        "",
        f"Dieser Beitrag stammt aus dem Weltreporter-Newsletter vom {date_formatted}. NEWSLETTER_URL:{newsletter_url}",
    ]
    return "\n".join(parts)


def main():
    force = "--force" in sys.argv

    newsletter_url_override = None
    if "--url" in sys.argv:
        idx = sys.argv.index("--url")
        try:
            newsletter_url_override = sys.argv[idx + 1]
        except IndexError:
            raise SystemExit("Verwendung: generate_circle_posts.py --url <URL>")

    print("Lade newsletter-content.json ...")
    try:
        newsletter = load_json("newsletter-content.json")
    except FileNotFoundError:
        raise SystemExit("newsletter-content.json nicht gefunden. Erst Stage 0 ausführen.")

    print("Lade schedule.json ...")
    try:
        schedule = load_json("schedule.json")
    except FileNotFoundError:
        raise SystemExit("schedule.json nicht gefunden. Erst Stage 2 ausführen oder LinkedIn-Skill nutzen.")

    articles = newsletter["articles"]
    date_str = newsletter["date"]

    newsletter_url = newsletter_url_override or extract_newsletter_url(schedule)
    if not newsletter_url:
        raise SystemExit(
            "Newsletter-URL nicht gefunden. Bitte angeben: generate_circle_posts.py --url <URL>"
        )

    print(f"Newsletter: {newsletter['campaign_name']} ({date_str})")
    print(f"URL: {newsletter_url}")
    print(f"Artikel: {len(articles)}, Schedule-Einträge: {len(schedule)}\n")

    if len(articles) != len(schedule):
        print(f"  ! Warnung: Anzahl stimmt nicht überein ({len(articles)} Artikel vs {len(schedule)} Einträge).")

    updated = 0
    for i, entry in enumerate(schedule):
        tag = entry["tag"]

        if entry.get("circle_post") and not force:
            print(f"  → Tag {tag}: übersprungen (bereits befüllt)")
            continue

        if i >= len(articles):
            print(f"  ! Tag {tag}: kein passender Artikel in newsletter-content.json")
            continue

        article = articles[i]
        kanal = entry.get("kanal", "Neues in der Welt")

        if article.get("author") and entry.get("autor"):
            if article["author"] != entry["autor"]:
                print(
                    f"  ! Tag {tag}: Autoren stimmen nicht überein "
                    f"({article['author']} ≠ {entry['autor']}) — bitte prüfen"
                )

        entry["circle_post"] = format_circle_post(article, tag, kanal, date_str, newsletter_url)
        titel = entry.get("titel") or article.get("headline") or "Editorial"
        print(f"  ✓ Tag {tag}: {titel[:55]}")
        updated += 1

    save_json("schedule.json", schedule)
    print(f"\n{updated} Circle-Posts generiert. schedule.json aktualisiert.")


if __name__ == "__main__":
    main()
