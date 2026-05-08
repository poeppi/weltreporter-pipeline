# AI usage rules — weltreporter-pipeline

## Modell-Hierarchie

Immer das schwächste Modell einsetzen, das die Aufgabe zuverlässig erledigt:

| Aufgabe | Modell |
|---|---|
| Strukturierte Extraktion (Newsletter → JSON) | `claude-haiku-4-5-20251001` |
| Texte generieren (LinkedIn-Posts, Circle-Posts) | `claude-haiku-4-5-20251001` |
| Komplexe Entscheidungen, Kanalzuordnung bei Grenzfällen | `claude-sonnet-4-6` |
| Opus | nicht einsetzen — kein Use Case in dieser Pipeline |

Modell nur upgraden, wenn Haiku nachweislich scheitert (schlechte JSON-Qualität, falsche Zuordnungen).

## Idempotenz — kein doppelter API-Call

`fetch_newsletter.py` prüft vor jedem API-Call, ob `newsletter-content.json` bereits die aktuelle Kampagne enthält. Ist das der Fall, überspringt es die Extraktion.

Nur mit `--force` erzwingen:
```bash
venv/bin/python3 fetch_newsletter.py --id 64 --force
```

## Token-Sparsamkeit

- HTML wird vor dem API-Call mit `html2text` in Klartext umgewandelt (Faktor 5–10 weniger Tokens als rohes HTML)
- Kontextfenster auf 40.000 Zeichen begrenzt — reicht für jeden Weltreporter-Newsletter
- Kein Streaming, kein Multi-Turn: ein Call pro Extraktion

## Was nie in einen API-Call gehört

- API-Keys, Tokens, Passwörter
- Persönliche Daten aus `.env`
- Interne Brevo- oder Circle-IDs (die sind nur lokal relevant)

## Kosten im Blick

Haiku kostet ca. $0.25 pro Million Input-Tokens. Ein kompletter Newsletter-Lauf (Extraktion + 10 Posts) liegt unter $0.01. Monatliche Gesamtkosten bei normalem Betrieb: unter $0.10.

Bei unerwartet hohem Verbrauch: console.anthropic.com → Usage prüfen.
