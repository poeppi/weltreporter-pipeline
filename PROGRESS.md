# Weltreporter Pipeline — interim status (May 2026)

## What's built and live on GitHub

**Stage 0 — Fetch (`fetch_newsletter.py`)**
Fetches the monthly newsletter from Brevo via API, converts HTML to plain text, extracts all articles using Claude Haiku, and writes structured output to `newsletter-content.json`. Idempotent: skips re-fetching if the same campaign ID is already cached. Run with `--id` to target a specific campaign or `--list` to browse past issues.

**Stage 1 — Circle posts (`generate_circle_posts.py`)**
Reads `newsletter-content.json` and the existing `schedule.json`, formats each article as a Circle community post (exact text, author credit, clickable link back to the newsletter), and routes it to the correct regional channel. No Claude API call needed: formatting is deterministic. Writes all posts into the `circle_post` fields of `schedule.json`.

**Stage 2 — LinkedIn posts (`skills/weltreporter-linkedin.md`)**
Claude Code skill (`/weltreporter-linkedin`) that generates a public-facing LinkedIn version of each article: hook, body, author credit, hashtags, link back to the newsletter. Output is written into the `linkedin_post` fields of `schedule.json`. Currently invoked manually; automated wiring to `newsletter-content.json` is still pending.

**Stage 3 — Automated posting (`post_today.py` + `.github/workflows/post-today.yml`)**
Daily GitHub Actions workflow (08:00 UTC). Reads `schedule.json`, finds today's entry, posts to Circle via API and to LinkedIn via the UGC Posts API. Marks entries as `posted_circle: true` / `posted_linkedin: true` and commits the updated `schedule.json` back to the repo — no separate database needed. Supports `--dry-run`, `--circle-only`, and `--linkedin-only` flags for testing.

**Supporting files**
- `channel-map.json`: maps the seven Weltreporter regional channels to their Circle space IDs
- `get_linkedin_token.py`: one-time OAuth helper that fetches a LinkedIn access token and organization ID via a local redirect server
- `requirements.txt`, `.env.example`, `.gitignore`

**What's been tested end-to-end**
The full April 2026 newsletter (10 articles) has been fetched, formatted, and posted to the correct Circle channels. Format issues (header line removal, clickable link) were caught and fixed during testing.

---

## What's missing

**Stage 2 — automation gap** ✅ closed
`generate_linkedin_posts.py` reads `newsletter-content.json`, generates LinkedIn posts for each article using Claude Haiku (hook, body, credit, footer, hashtags), and writes them into `schedule.json`. Idempotent: skips entries already filled; use `--force` to regenerate.

**LinkedIn posting — not yet verified**
The LinkedIn OAuth flow is complete (access token and organization ID are stored as GitHub Secrets), but posting to the Weltreporter organization page has not been tested end-to-end. The UGC Posts API with `w_member_social` scope should allow posting as an org admin, but this needs a live test.

**Stage 4 — archive access (stretch goal)**
A lightweight MCP server wrapping the Brevo API to expose `list_issues()` and `fetch_issue()` as tools for Claude Code. Not yet started.

**LinkedIn token renewal**
The LinkedIn access token expires after ~60 days. No automated renewal is in place yet; token refresh will need to be done manually by re-running `get_linkedin_token.py`.
