#!/usr/bin/env python3
"""
Stage 3 — Weltreporter pipeline
Posts today's scheduled entry to Circle and LinkedIn.

Usage (from projects/weltreporter-pipeline/):
  venv/bin/python3 post_today.py                    # posts today's entry
  venv/bin/python3 post_today.py --dry-run          # prints what would be posted
  venv/bin/python3 post_today.py --date 2026-04-17  # override date (for testing)
  venv/bin/python3 post_today.py --circle-only      # skip LinkedIn
  venv/bin/python3 post_today.py --linkedin-only    # skip Circle

Reads:
  schedule.json    — posting schedule with content (built by Stage 1 + 2)
  channel-map.json — maps kanal names to Circle space IDs

Environment (via .env or GitHub Secrets):
  CIRCLE_API_TOKEN      Circle API token
  CIRCLE_COMMUNITY_ID   Circle community ID (integer)
  LINKEDIN_ACCESS_TOKEN LinkedIn OAuth 2.0 access token (Bearer)
  LINKEDIN_ORG_ID       LinkedIn organization numeric ID (from GET /v2/organizations?q=vanityName&vanityName=weltreporter)

LinkedIn setup (one-time):
  1. Create a LinkedIn App at https://developer.linkedin.com/
  2. Authorize with scope: r_liteprofile w_member_social
  3. Exchange the auth code for an access token (valid 60 days; refresh via OAuth)
  4. Fetch your person ID: GET https://api.linkedin.com/v2/me
     → store the "id" field as LINKEDIN_PERSON_ID
"""

import html
import json
import os
import sys
import requests
from datetime import date, datetime


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


def log_error(message):
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] {message}\n"
    with open("errors.log", "a", encoding="utf-8") as f:
        f.write(line)
    print(f"ERROR: {message}", file=sys.stderr)


def text_to_html(text):
    """Convert plain text (double-newline paragraphs) to simple HTML."""
    import re
    paragraphs = text.split("\n\n")
    parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Extract NEWSLETTER_URL marker before escaping — avoids regex bugs with html entities
        m = re.search(r"NEWSLETTER_URL:(https?://\S+)", p)
        if m:
            url = m.group(1)
            before = html.escape(p[:m.start()])
            after = html.escape(p[m.end():])
            escaped = f'{before}<a href="{url}">→ Zur kompletten Ausgabe</a>{after}'
        else:
            escaped = html.escape(p)
        parts.append(f"<p>{escaped.replace(chr(10), '<br>')}</p>")
    return "\n".join(parts)


def post_to_circle(entry, channel_map, community_id, api_token, dry_run=False):
    kanal = entry.get("kanal", "Neues in der Welt")
    space_id = channel_map.get(kanal)

    if not space_id or space_id == "PLACEHOLDER":
        log_error(f"Kein gültiger space_id für Kanal '{kanal}' in channel-map.json")
        return False

    circle_text = entry["circle_post"]
    titel = entry.get("titel") or "Weltreporter"
    body_html = text_to_html(circle_text)

    if dry_run:
        print(f"  [dry-run] Circle → Kanal '{kanal}' (space {space_id})")
        print(f"  Titel: {titel}")
        print(f"  Text ({len(circle_text)} Zeichen)")
        return True

    resp = requests.post(
        "https://app.circle.so/api/v1/posts",
        headers={
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
        },
        json={
            "community_id": int(community_id),
            "space_id": int(space_id),
            "name": titel,
            "body": body_html,
            "published": True,
        },
        timeout=30,
    )

    if resp.status_code in (200, 201):
        return True

    log_error(f"Circle API {resp.status_code}")
    return False


def post_to_linkedin(entry, org_id, access_token, dry_run=False):
    linkedin_text = entry["linkedin_post"]

    if dry_run:
        print(f"  [dry-run] LinkedIn → organization {org_id}")
        print(f"  Text ({len(linkedin_text)} Zeichen)")
        return True

    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json={
            "author": f"urn:li:organization:{org_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": linkedin_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        },
        timeout=30,
    )

    if resp.status_code in (200, 201):
        return True

    log_error(f"LinkedIn API {resp.status_code}")
    return False


def main():
    dry_run = "--dry-run" in sys.argv
    skip_circle = "--linkedin-only" in sys.argv
    skip_linkedin = "--circle-only" in sys.argv

    today_str = date.today().isoformat()
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        try:
            today_str = sys.argv[idx + 1]
        except IndexError:
            raise SystemExit("Verwendung: post_today.py --date YYYY-MM-DD")

    print(f"Datum: {today_str}{' [dry-run]' if dry_run else ''}")

    env = load_env()

    def get(key):
        return env.get(key) or os.environ.get(key, "")

    circle_token = get("CIRCLE_API_TOKEN")
    circle_community_id = get("CIRCLE_COMMUNITY_ID")
    linkedin_token = get("LINKEDIN_ACCESS_TOKEN")
    linkedin_person_id = get("LINKEDIN_ORG_ID")

    if not dry_run:
        if not skip_circle and (not circle_token or not circle_community_id):
            raise SystemExit("CIRCLE_API_TOKEN oder CIRCLE_COMMUNITY_ID fehlt.")
        if not skip_linkedin and (not linkedin_token or not linkedin_person_id):
            print("  LinkedIn: Credentials fehlen — wird übersprungen.")
            skip_linkedin = True

    schedule = load_json("schedule.json")
    channel_map = load_json("channel-map.json")

    entries = [e for e in schedule if e["datum"] == today_str]
    if not entries:
        print(f"Kein Eintrag für {today_str} — nichts zu tun.")
        return

    entry = entries[0]
    print(f"→ Tag {entry['tag']}: {entry['titel']}")

    errors = []

    # Circle
    if skip_circle:
        print("  Circle: übersprungen (--linkedin-only)")
    elif entry.get("posted_circle"):
        print("  Circle: bereits gepostet — übersprungen")
    elif not entry.get("circle_post"):
        print("  Circle: circle_post leer — übersprungen")
    else:
        ok = post_to_circle(entry, channel_map, circle_community_id, circle_token, dry_run)
        if ok:
            entry["posted_circle"] = True
            print("  Circle: ✓")
        else:
            errors.append("Circle")

    # LinkedIn
    if skip_linkedin:
        print("  LinkedIn: übersprungen (--circle-only)")
    elif entry.get("posted_linkedin"):
        print("  LinkedIn: bereits gepostet — übersprungen")
    elif not entry.get("linkedin_post"):
        print("  LinkedIn: linkedin_post leer — übersprungen")
    else:
        ok = post_to_linkedin(entry, linkedin_person_id, linkedin_token, dry_run)
        if ok:
            entry["posted_linkedin"] = True
            print("  LinkedIn: ✓")
        else:
            errors.append("LinkedIn")

    if not dry_run:
        save_json("schedule.json", schedule)
        print("schedule.json aktualisiert.")

    if errors:
        raise SystemExit(f"Fehlgeschlagen: {', '.join(errors)}. Details in errors.log.")


if __name__ == "__main__":
    main()
