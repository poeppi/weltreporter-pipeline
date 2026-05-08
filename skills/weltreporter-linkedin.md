# Weltreporter LinkedIn posts

Generates a LinkedIn version of each article from the monthly Weltreporter newsletter — public-facing, short, with hashtags and a link to the source.

## When to invoke

Invoke with `/weltreporter-linkedin`. Run once per month after Stage 1 (`/weltreporter-circle`).

## Input

Either:
- The newsletter URL, or
- The full newsletter text pasted directly

Also required:
- **Date** of the newsletter (e.g. "April 2026")
- **Newsletter URL** — appears at the end of every post as a link back to the source

## Processing rules

### Tone and format

LinkedIn posts are public. They address journalists, communications professionals, and people who don't yet know Weltreporter. Tone: curious, factual, journalistic.

Each post follows this structure:

1. **Hook** (line 1–2): The strongest fact or question from the article — no warm-up. LinkedIn truncates after ~3 lines; the hook must stand on its own.
2. **Body** (3–6 sentences): The core of the article. Not a summary — what is the one thing that sticks?
3. **Credit**: "Von [Name], Weltreporter-Korrespondent:in in [Stadt]."
4. **Abbinder**: "Dieser Beitrag ist erschienen im Weltreporter Newsletter vom [Datum]. Hier geht es zur kompletten Ausgabe: [URL]"
5. **Hashtags** (3–5): topically relevant, in German if the post is in German. Always include `#Weltreporter`. Add 2–4 more based on topic (e.g. `#Auslandskorrespondenz`, `#Journalismus`, `#[country or topic hashtag]`).

**Character limit:** Max. 1,300 characters per post (LinkedIn optimum for reach).

### Language

German — unless the article is by an English-language correspondent and clearly addresses an international audience.

### What does not belong in a LinkedIn post

- The full article text (that is for Circle)
- Internal discussion questions
- Any mention of Circle or the community
- Cliché openings: "In einer Welt, in der …", "Immer mehr Menschen …", "In today's fast-paced world …"

## Output format

Output one finished LinkedIn post per article:

```
---
📅 TAG [number] | LinkedIn

[Hook — line 1]
[Hook — line 2, optional]

[Body — 3–6 sentences]

Von [Name], Weltreporter-Korrespondent:in in [Stadt].

Dieser Beitrag ist erschienen im Weltreporter Newsletter vom [Datum]. Hier geht es zur kompletten Ausgabe: [URL]

#Weltreporter #[Hashtag2] #[Hashtag3]

Zeichen: [N]/1.300
---
```

After all posts: **write `schedule.json`** to the project root. One entry per article:

```json
[
  {
    "tag": 1,
    "datum": "YYYY-MM-DD",
    "kanal": "Neues in der Welt",
    "titel": "Article title",
    "circle_post": "...",
    "linkedin_post": "...",
    "hashtags": ["#Weltreporter", "#Journalismus"],
    "posted_circle": false,
    "posted_linkedin": false
  }
]
```

If `schedule.json` already exists (Stage 1 ran first): read it and add `linkedin_post`, `hashtags`, and `posted_linkedin` fields to each entry. Do not overwrite existing fields.

If `schedule.json` does not yet exist: create it with LinkedIn fields filled in; leave `circle_post` as an empty string.

## Completeness check

The number of LinkedIn posts must match the number of articles in the newsletter. If fewer: name the missing ones and ask for the source text.
