# weltreporter-pipeline
Multi-channel distribution pipeline for Weltreporter newsletter (MOOC final project)

## Weltreporter newsletter → multi-channel distribution pipeline

### The problem

Weltreporter e.V. is a network of German-speaking foreign correspondents, publishing a newsletter with 10+ articles every month — each from a different region of the world.

We're building a Circle community for our members and designing the content workflows from scratch. Distributing newsletter content manually — copy, format, route to the right regional channel, adapt for LinkedIn, repeat for every article — takes roughly two hours a month and happens inconsistently. This pipeline solves that before it becomes a habit.

### The solution

A multi-stage CLI pipeline built with Claude Code:

**Stage 1 — Extract & route** *(already built in Module 2)*
Takes a newsletter URL, extracts each article, formats it as a Circle post, and routes it to the correct regional channel. Generates a posting schedule: one article per day.

**Stage 2 — LinkedIn adaptation** *(Module 2/3)*
Generates a LinkedIn version of each post: shorter, public-facing, with hashtags and a link back to the newsletter.

**Stage 3 — Automated scheduling** *(Module 3)*
Stage 1/2 writes a `schedule.json` file: one entry per article, each with the Circle post, the LinkedIn version, the target channel, and the posting date.

A GitHub Actions workflow runs daily at 8:00 UTC. It reads `schedule.json`, finds today's entry, and executes two steps:

1. **Circle:** POST request to the Circle API with the formatted post and channel ID. Auth via `CIRCLE_API_TOKEN` stored as a GitHub Secret.
2. **LinkedIn:** POST request to the LinkedIn Posts API. Auth via OAuth 2.0 access token, stored as `LINKEDIN_ACCESS_TOKEN`. *(OAuth setup pending — one-time flow required.)*

After posting, the workflow marks the entry as `posted: true` in `schedule.json` and commits the update back to the repo. That gives a built-in posting log without a separate database.

If a post fails (API error, rate limit), the workflow retries once and logs the error to a `errors.log` file in the repo.

**Stage 4 — Archive access** *(Module 4, stretch goal)*
Weltreporter's newsletter archive sits in Mailchimp or Brevo. Both services offer a REST API that lists past campaigns and returns the full HTML content of each issue.

Stage 4 builds a lightweight MCP server that wraps this API and exposes two tools to Claude Code:

- `list_issues(limit)` — returns a list of past newsletter issues with title, date, and campaign ID
- `fetch_issue(campaign_id)` — returns the full HTML of a specific issue, ready for Stage 1 to parse

With these tools in place, Claude Code can process the entire back catalogue: fetch an issue, run it through Stage 1 (extract & route) and Stage 2 (LinkedIn), write the results into `schedule.json`, and hand off to Stage 3 for drip-posting — one article per day, spreading historical content across weeks.

Practical use case: when the Circle community launches, Stage 4 pre-populates channels with the best articles from the past 12 months, scheduled to post daily so the community feels active from day one.

*[OPEN: confirm whether the archive runs on Mailchimp or Brevo — API auth setup differs.]*

### Why it matters

Two hours of monthly copy-paste becomes one command. Weltreporter content lands in the right channels, every day, on schedule — without anyone having to remember.

### What I'll submit

- Claude Code skill file (`/weltreporter-circle`) with channel routing logic
- GitHub Actions workflow (`.github/workflows/post-today.yml`) for scheduled posting
- MCP server for Mailchimp/Brevo archive access *(Stage 4)*
- README: setup, usage, expected output, limitations
- Sample input (newsletter URL) + sample output (formatted posts)
- GitHub: https://github.com/poeppi/weltreporter-pipeline
