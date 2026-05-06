# Newsletter Demo

An AI-powered newsletter pipeline built on the **WAT framework** (Workflows, Agents, Tools). Give it a topic and it researches, writes, designs, and sends a branded HTML email — end to end.

---

## How It Works

```
Topic → Research (Tavily) → Content (Claude) → Infographics (kie.ai) → Upload (Google Drive) → Render (HTML) → Send (Gmail)
```

The architecture separates concerns:

- **Workflows** (`workflows/`) — plain-language SOPs that define what to do and how
- **Agents** — Claude reads the workflow and orchestrates each step
- **Tools** (`tools/`) — Python scripts that do the actual execution (API calls, file ops, rendering)

---

## Output

A fully rendered, email-safe HTML newsletter with:

- Branded header (Hiralis Intelligence Brief)
- 3–5 research-grounded sections with key stats
- AI-generated infographic images per section
- 3 key takeaways + call to action
- Source citations in the footer
- Plain-text fallback for email clients that block HTML

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your_key        # console.anthropic.com
TAVILY_API_KEY=your_key           # tavily.com (1,000 free searches/month)
KIE_API_KEY=your_key              # kie.ai/api-key (~$0.02/image)
GMAIL_SENDER_ADDRESS=you@gmail.com
DRIVE_IMAGES_FOLDER_ID=your_folder_id   # Google Drive folder ID for hosted images
```

### 3. Authorize Google (one-time)

- Create a Google Cloud project with **Gmail API** and **Google Drive API** enabled
- Create an OAuth 2.0 Client ID (Desktop app) and download `credentials.json` to the project root
- Add your Gmail address as a test user on the OAuth consent screen
- Run the auth flow:

```bash
python tools/auth_google.py
```

This opens a browser and writes `token.json`. You're set.

---

## Running the Pipeline

Run each step in order. Each reads from `.tmp/` and writes to `.tmp/`.

```bash
# Step 1 — Research
python tools/research.py --topic "your topic here"

# Step 2 — Generate content
python tools/generate_content.py --topic "your topic here"

# Step 3 — Generate infographics (~$0.02/image, non-blocking)
python tools/generate_infographics.py

# Step 4 — Upload images to Google Drive
python tools/upload_assets.py --drive-folder-id YOUR_FOLDER_ID

# Step 5 — Render HTML
python tools/render_html.py

# Step 6 — Send
python tools/send_gmail.py --to recipient@example.com
```

> **Note:** Steps 1 and 2 call the Anthropic API directly. If you're using Claude Code with a Pro plan, you can have Claude compose the queries and write `content.json` directly — see the `/newsletter` slash command below.

---

## Claude Code Skill

If you're using [Claude Code](https://claude.ai/code), a `/newsletter` slash command is included at `.claude/commands/newsletter.md`. It guides Claude through the full pipeline using your Pro plan for content generation (no separate API credits needed for Steps 1–2).

```
/newsletter agentic AI in healthcare 2025
```

---

## Project Structure

```
.claude/
  commands/
    newsletter.md       # /newsletter slash command for Claude Code
config/
  newsletter_style.json # Brand colors, fonts, infographic style
  recipients.json       # Default recipient list
tools/
  auth_google.py        # One-time Google OAuth setup
  research.py           # Step 1: Tavily search
  generate_content.py   # Step 2: Claude content generation
  generate_infographics.py  # Step 3: kie.ai image generation
  upload_assets.py      # Step 4: Google Drive upload
  render_html.py        # Step 5: Jinja2 + premailer HTML render
  send_gmail.py         # Step 6: Gmail API send
  templates/
    newsletter.html.j2  # Email HTML template
workflows/
  newsletter.md         # Full SOP with edge cases and lessons learned
brand_assets/
  logo.png
  Brand Guidlines.png
.tmp/                   # Auto-generated (gitignored) — intermediate files
```

---

## Cost Per Newsletter

| Service             | Cost                          |
| ------------------- | ----------------------------- |
| Tavily search       | ~free (1,000/month free tier) |
| Claude content      | free (Claude Code Pro plan)   |
| kie.ai infographics | ~$0.08 (4 images × $0.02)     |
| Google APIs         | free                          |
| **Total**           | **~$0.08**                    |

---

## Next Steps

Once you trust your workflow, explore deploying it as a scheduled job so newsletters go out automatically without any manual steps:

- **[Trigger.dev](https://trigger.dev)** — run the pipeline as a background job triggered on a cron schedule, with built-in retries and observability
- **[Modal](https://modal.com)** — deploy the pipeline as a serverless function that spins up on demand or on a schedule, with zero infrastructure management

Both platforms work well with Python-based pipelines like this one. The pattern is: push your code to GitHub → connect the repo → define a schedule → done.

---

## Tech Stack

- [Anthropic Claude](https://anthropic.com) — content generation
- [Tavily](https://tavily.com) — web research
- [kie.ai](https://kie.ai) — AI image generation (Nano Banana 2)
- [Gmail API](https://developers.google.com/gmail/api) — email delivery
- [Google Drive API](https://developers.google.com/drive) — image hosting
- [Jinja2](https://jinja.palletsprojects.com) + [premailer](https://github.com/peterbe/premailer) — HTML rendering
