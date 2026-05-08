#!/usr/bin/env python3
"""
Stage 0 — Weltreporter pipeline
Fetches a newsletter from Brevo and extracts all articles via Ollama (local).
Output: newsletter-content.json

Usage:
  python3 fetch_newsletter.py          # fetches latest campaign
  python3 fetch_newsletter.py --list   # lists last 20 campaigns with IDs
  python3 fetch_newsletter.py --id 42  # fetches campaign with ID 42

Dependencies: pip install requests html2text
Ollama must be running: ollama serve
"""

import os, json, requests, html2text, sys, re
import anthropic
from datetime import datetime


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


def list_campaigns(api_key, limit=20):
    resp = requests.get(
        "https://api.brevo.com/v3/emailCampaigns",
        params={"type": "classic", "status": "sent", "limit": limit, "sort": "desc"},
        headers={"api-key": api_key, "accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json().get("campaigns", [])


def get_latest_campaign(api_key):
    campaigns = list_campaigns(api_key, limit=5)
    if not campaigns:
        raise SystemExit("Keine gesendeten Kampagnen gefunden.")
    return campaigns[0]


def get_campaign_by_id(api_key, campaign_id):
    campaigns = list_campaigns(api_key, limit=20)
    for c in campaigns:
        if c["id"] == campaign_id:
            return c
    raise SystemExit(f"Kampagne mit ID {campaign_id} nicht gefunden.")


def get_campaign_html(api_key, campaign_id):
    resp = requests.get(
        f"https://api.brevo.com/v3/emailCampaigns/{campaign_id}",
        headers={"api-key": api_key, "accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def html_to_text(html_content):
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(html_content)


def parse_xml_articles(raw):
    """Parst das XML-Format das Claude zurückgibt — kein JSON-Escaping nötig."""
    articles = []
    for block in re.findall(r"<item>(.*?)</item>", raw, re.DOTALL):
        def get(tag):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.DOTALL)
            v = m.group(1).strip() if m else None
            return None if v in (None, "null", "") else v
        articles.append({
            "type":     get("type") or "article",
            "headline": get("headline"),
            "subtitle": get("subtitle"),
            "author":   get("author"),
            "city":     get("city"),
            "text":     get("text"),
        })
    return articles


def extract_articles_claude(plain_text, campaign_name, anthropic_key):
    client = anthropic.Anthropic(api_key=anthropic_key)

    prompt = f"""Extract all content from this Weltreporter newsletter "{campaign_name}".

Include the editorial (starts with "Liebe Leser" or similar) and every article.

Return each item in this XML format — nothing else, no JSON, no markdown:

<items>
<item>
<type>editorial</type>
<headline>null</headline>
<subtitle>null</subtitle>
<author>Full Name</author>
<city>City</city>
<text>Complete body text word for word, preserving paragraphs.</text>
</item>
<item>
<type>article</type>
<headline>Exact headline</headline>
<subtitle>Exact subtitle or null</subtitle>
<author>Full Name</author>
<city>City</city>
<text>Complete body text word for word.</text>
</item>
</items>

Newsletter text:
{plain_text[:40000]}"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()

    articles = parse_xml_articles(raw)
    if not articles:
        print(f"  ! Keine Artikel geparsed. Rohausgabe (erste 300 Zeichen):\n{raw[:300]}")
        raise SystemExit("Extraktion fehlgeschlagen.")
    return articles


def main():
    env = load_env()
    brevo_key = env.get("BREVO_API_KEY") or os.environ.get("BREVO_API_KEY")
    anthropic_key = env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")

    if not brevo_key:
        raise SystemExit("BREVO_API_KEY fehlt. Bitte in .env eintragen.")
    if not anthropic_key:
        raise SystemExit("ANTHROPIC_API_KEY fehlt. Bitte in .env eintragen.")

    # --list: Kampagnenliste ausgeben und beenden
    if "--list" in sys.argv:
        print("Letzte 20 Kampagnen:\n")
        for c in list_campaigns(brevo_key):
            print(f"  ID {c['id']:5}  {c.get('sentDate','')[:10]}  {c['name']}")
        return

    # --id <n>: bestimmte Kampagne abrufen
    campaign_id = None
    if "--id" in sys.argv:
        idx = sys.argv.index("--id")
        try:
            campaign_id = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            raise SystemExit("Verwendung: python3 fetch_newsletter.py --id <ID>")

    print("Kampagne von Brevo holen ...")
    if campaign_id:
        campaign = get_campaign_by_id(brevo_key, campaign_id)
    else:
        campaign = get_latest_campaign(brevo_key)
    campaign_id = campaign["id"]
    campaign_name = campaign["name"]
    campaign_date = campaign.get("sentDate", "")[:10]
    print(f"  → {campaign_name} (ID: {campaign_id}, gesendet: {campaign_date})")

    # Idempotenz: API-Call überspringen wenn diese Kampagne schon extrahiert wurde
    if os.path.exists("newsletter-content.json") and "--force" not in sys.argv:
        with open("newsletter-content.json") as f:
            cached = json.load(f)
        if cached.get("campaign_id") == campaign_id:
            print(f"  → Bereits extrahiert. Nutze newsletter-content.json (--force zum Überschreiben)")
            return

    print("Vollständigen Newsletter-HTML laden ...")
    campaign_data = get_campaign_html(brevo_key, campaign_id)
    html_content = campaign_data.get("htmlContent", "")

    if not html_content:
        raise SystemExit("Kein HTML-Inhalt in der Kampagne gefunden.")

    print("HTML in Klartext umwandeln ...")
    plain_text = html_to_text(html_content)

    print("Artikel via Claude API extrahieren ...")
    articles = extract_articles_claude(plain_text, campaign_name, anthropic_key)
    print(f"  → {len(articles)} Beiträge extrahiert")

    output = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "date": campaign_date,
        "extracted_at": datetime.now().isoformat(),
        "articles": articles,
    }

    with open("newsletter-content.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Gespeichert: newsletter-content.json")
    print("\nInhalt:")
    for i, a in enumerate(articles, 1):
        t = a.get("type", "article")
        h = a.get("headline", "–")
        author = a.get("author", "–")
        print(f"  {i:2}. [{t}] {h} ({author})")


if __name__ == "__main__":
    main()
