# weltreporter-pipeline

Multi-channel distribution pipeline for the Weltreporter newsletter.

## The problem

Weltreporter e.V. is a network of German-speaking foreign correspondents, publishing a newsletter with 10+ articles every month — each from a different region of the world. Distributing newsletter content manually — copy, format, route to the right regional channel, adapt for LinkedIn, repeat for every article — takes roughly two hours a month and happens inconsistently. This pipeline replaces that with three commands and a daily cron job.

## What's built

### Stage 0 — Fetch (`fetch_newsletter.py`)

Fetches the monthly newsletter from Brevo via API, converts HTML to plain text, extracts all articles using Claude Haiku, and writes structured output to `newsletter-content.json`.

```bash
venv/bin/python3 fetch_newsletter.py            # fetch latest campaign
venv/bin/python3 fetch_newsletter.py --id 64    # fetch specific campaign
venv/bin/python3 fetch_newsletter.py --list     # list last 20 campaigns
```

Idempotent: skips re-fetching if the same campaign is already cached. Use `--force` to override.

### Stage 1 — Circle posts (`generate_circle_posts.py`)

Reads `newsletter-content.json`, formats each article as a Circle community post (exact text, author credit, clickable link), routes it to the correct regional channel, and writes the result into `schedule.json`.

```bash
venv/bin/python3 generate_circle_posts.py
venv/bin/python3 generate_circle_posts.py --force   # regenerate all
```

No AI call needed: formatting is deterministic. Channel routing is defined in `channel-map.json`.

### Stage 2 — LinkedIn posts (`generate_linkedin_posts.py`)

Reads `newsletter-content.json`, generates a public-facing LinkedIn version of each article using Claude Haiku — hook, condensed body, author credit, hashtags — and writes the result into `schedule.json`.

```bash
venv/bin/python3 generate_linkedin_posts.py
venv/bin/python3 generate_linkedin_posts.py --force  # regenerate all
```

Character limit: 1,300 characters per post. The script warns if a post exceeds this.

### Stage 3 — Automated posting (`post_today.py` + `.github/workflows/post-today.yml`)

A GitHub Actions workflow runs daily at 08:00 UTC. It reads `schedule.json`, finds today's entry, and posts to Circle and LinkedIn. After each successful post it marks the entry as `posted_circle: true` / `posted_linkedin: true` and commits the updated `schedule.json` back to the repo.

```bash
venv/bin/python3 post_today.py --dry-run --date 2026-04-18   # preview
venv/bin/python3 post_today.py --circle-only --date 2026-04-18
venv/bin/python3 post_today.py --linkedin-only --date 2026-04-18
```

### Stage 4 — Archive access (stretch goal, not yet built)

A lightweight MCP server wrapping the Brevo API to expose `list_issues()` and `fetch_issue()` as tools for Claude Code — enabling back-catalogue processing.

## Monthly workflow

```bash
# 1. Fetch newsletter (once the new issue is sent)
venv/bin/python3 fetch_newsletter.py

# 2. Generate Circle posts
venv/bin/python3 generate_circle_posts.py

# 3. Generate LinkedIn posts
venv/bin/python3 generate_linkedin_posts.py

# GitHub Actions handles the rest: one post per day at 08:00 UTC
```

## Setup

### Requirements

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in all values:

```
BREVO_API_KEY               Brevo API key (newsletter source)
ANTHROPIC_API_KEY           Anthropic API key (Claude Haiku)
CIRCLE_API_TOKEN            Circle community API token
CIRCLE_COMMUNITY_ID         Circle community ID (integer)
LINKEDIN_CLIENT_ID          LinkedIn Developer App client ID
LINKEDIN_CLIENT_SECRET      LinkedIn Developer App client secret
LINKEDIN_ACCESS_TOKEN       LinkedIn OAuth access token (valid ~60 days)
LINKEDIN_ORG_ID             LinkedIn organization numeric ID
```

### LinkedIn token setup (one-time)

1. Create a LinkedIn Developer App at https://developer.linkedin.com/
2. Add product: **Share on LinkedIn**
3. Add redirect URI: `http://localhost:8080/callback`
4. Enter `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` in `.env`
5. Run the OAuth helper:
   ```bash
   venv/bin/python3 get_linkedin_token.py
   ```
   The script opens a browser, handles the redirect, and prints `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_ORG_ID`.

Token expires after ~60 days. Re-run `get_linkedin_token.py` to renew.

### GitHub Secrets

For the GitHub Actions workflow, set these repository secrets:

| Secret | Value |
|---|---|
| `CIRCLE_API_TOKEN` | from `.env` |
| `CIRCLE_COMMUNITY_ID` | from `.env` |
| `LINKEDIN_ACCESS_TOKEN` | from LinkedIn OAuth flow |
| `LINKEDIN_ORG_ID` | from LinkedIn OAuth flow |

### Channel map

`channel-map.json` maps Weltreporter regional channel names to Circle space IDs. Update if channels change:

```json
{
  "Neues in der Welt": 2514327,
  "Europa": 2514237,
  ...
}
```

## Repository structure

```
fetch_newsletter.py         Stage 0: fetch + extract newsletter
generate_circle_posts.py    Stage 1: format Circle posts
generate_linkedin_posts.py  Stage 2: generate LinkedIn posts
post_today.py               Stage 3: post today's entry
get_linkedin_token.py       LinkedIn OAuth helper (one-time setup)
channel-map.json            Circle channel → space ID mapping
schedule.json               Posting schedule with content + status flags
newsletter-content.json     Extracted newsletter (gitignored, rebuilt each month)
.github/workflows/
  post-today.yml            Daily GitHub Actions workflow
```

## Sample output

`schedule.json` after a full run:

```json
[
  {
    "tag": 1,
    "datum": "2026-04-17",
    "kanal": "Neues in der Welt",
    "titel": "Gott, Götter und das Weltgeschehen",
    "circle_post": "...",
    "linkedin_post": "...",
    "hashtags": ["#Weltreporter", "#Religion", "#Glaube"],
    "posted_circle": true,
    "posted_linkedin": false
  }
]
```

## Why it matters

Two hours of monthly copy-paste become three commands. Weltreporter content lands in the right channels, every day, on schedule.
