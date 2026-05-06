# Newsletter Generation Workflow

## Objective

Given a topic, research it using Tavily, generate structured content with Claude, create AI infographics via kie.ai Nano Banana 2, render an email-safe HTML newsletter, and send it via Gmail.

---

## Required Inputs

| Input | Description |
|---|---|
| `topic` | Newsletter topic (e.g. "AI agents in healthcare 2025") |
| `recipient_email` | Who to send the newsletter to |
| `drive_images_folder_id` | Google Drive folder ID where infographic images will be hosted |

---

## Prerequisites

Before running the pipeline for the first time:

1. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Set up API keys in `.env`**
   - `ANTHROPIC_API_KEY` — from console.anthropic.com
   - `TAVILY_API_KEY` — from tavily.com (free tier: 1,000 searches/month)
   - `KIE_API_KEY` — from kie.ai/api-key (~$0.02/image)
   - `GMAIL_SENDER_ADDRESS` — your Gmail address
   - `DRIVE_IMAGES_FOLDER_ID` — Google Drive folder ID for hosted images (must be set to "anyone with link can view")

3. **Authorize Google (one-time)**
   - Place your `credentials.json` from Google Cloud Console in the project root
   - Enable Gmail API and Google Drive API in your Google Cloud project
   - Run: `python tools/auth_google.py`
   - Complete the browser OAuth flow — this creates `token.json`

---

## Pipeline Steps

Run each step in order. Each step reads from `.tmp/` and writes to `.tmp/`.

### Step 1 — Research

```
python tools/research.py --topic "{topic}"
```

Decomposes the topic into 4 focused search queries using Claude, then runs each through Tavily. Deduplicates results by URL.

**Success:** `.tmp/research.json` exists with at least 3 sources.

**On failure:**
- `TAVILY_API_KEY invalid` → check `.env`
- `< 3 sources returned` → try a broader or more specific topic phrasing
- Rate limited (HTTP 429) → wait 60 seconds and retry once

---

### Step 2 — Generate Content

```
python tools/generate_content.py --topic "{topic}"
```

Feeds the research to Claude (with prompt caching) and returns a structured content schema: sections, key stats, subject line, takeaways, CTA.

**Success:** `.tmp/content.json` validates — has `sections`, `subject_line`, `key_takeaways`.

**On failure:**
- JSON parse error → retry once; Claude occasionally produces malformed tool output
- Unverified stats flagged → review the flagged sections before sending; the stat value was not found in the source text

**Review before continuing:**
- Check the console for `⚠ WARNINGS` about subject line length or spam trigger words
- Check for `UNVERIFIED STATS` — these should be removed or manually verified

---

### Step 3 — Generate Infographics

```
python tools/generate_infographics.py
```

For each section with `chart_type != "none"`, submits a generation task to kie.ai Nano Banana 2 and polls until complete (~30 seconds per image). Downloads PNGs to `.tmp/assets/`.

**Success:** `.tmp/assets/` contains at least one PNG.

**This step is non-blocking** — if image generation fails for a section, the pipeline continues. The HTML template handles missing images gracefully (images are supplementary; stats still appear as text callout boxes).

**On failure:**
- HTTP 402 → insufficient kie.ai credits; top up at kie.ai
- HTTP 429 → rate limited (20 req/10s); not expected for newsletters with <5 sections
- Task status `failed` → kie.ai service error; skip that section and continue
- Timeout after 90s → same as above

**Cost:** ~$0.02 per image. A 4-section newsletter = ~$0.08.

---

### Step 4 — Upload Images to Google Drive

```
python tools/upload_assets.py --drive-folder-id {drive_images_folder_id}
```

Uploads all PNGs from `.tmp/assets/` to the specified Google Drive folder, sets each file to "anyone can view", and records the direct image URLs.

**Success:** `.tmp/asset_urls.json` contains one entry per PNG.

**On failure:**
- `token.json` expired → run `python tools/auth_google.py` to refresh
- `DRIVE_IMAGES_FOLDER_ID` not set → add to `.env`
- No PNG files in `.tmp/assets/` → step 3 produced no images; `asset_urls.json` will be empty and template will render without images (acceptable)

---

### Step 5 — Render HTML

```
python tools/render_html.py
```

Renders the Jinja2 template (`tools/templates/newsletter.html.j2`) with the content and image URLs, inlines all CSS with premailer (required for Gmail/Outlook compatibility), generates a plain-text version with html2text.

**Success:** Both `.tmp/newsletter_final.html` and `.tmp/newsletter_final.txt` exist.

**Watch for:**
- `WARNING: Newsletter HTML is XXkB` — if over 90KB, Gmail will clip the email. Reduce section count (edit content.json to remove a section) and re-run this step.

**On failure:**
- Template rendering error → check that `content.json` and `asset_urls.json` are valid JSON
- premailer error → usually malformed HTML in the template; check for unclosed tags

---

### Step 6 — Send via Gmail

```
python tools/send_gmail.py --to {recipient_email}
```

Injects UTM tracking parameters into all links, then sends via Gmail API as a multipart/alternative message (plain text + HTML).

**Success:** Console prints `Sent. Gmail message ID: ...`

**On failure:**
- `token.json` expired → run `python tools/auth_google.py`
- Gmail API quota exceeded (very unlikely for personal use) → wait and retry
- Message bounced → check recipient address

---

## Edge Cases & Notes

| Situation | Action |
|---|---|
| Topic produces very few search results | Rephrase topic to be more specific or add a year (e.g. "2025") |
| Key stat marked `⚠ Unverified` | Remove or manually verify before sending |
| HTML > 90KB | Open `.tmp/content.json`, delete one section, re-run steps 5–6 |
| Infographic looks wrong | Edit the prompt in `generate_infographics.py::build_prompt()` and rerun step 3 |
| OAuth token expired | `python tools/auth_google.py` (opens browser) |
| Want to resend without regenerating | Run only steps 5–6 |
| Want new images but same content | Run only steps 3–6 |

---

## CAN-SPAM Compliance Checklist

Before sending to any real subscriber list, ensure the footer in the template contains:

- [ ] Your real sender identity (name / company)
- [ ] A physical mailing address
- [ ] A working unsubscribe link
- [ ] An honest, non-deceptive subject line

Update `tools/templates/newsletter.html.j2` footer section with real values before production use.

---

## Dependencies

```
pip install -r requirements.txt
```

Key libraries: `anthropic`, `tavily-python`, `httpx`, `jinja2`, `premailer`, `html2text`, `google-api-python-client`, `google-auth-oauthlib`, `python-dotenv`

---

## Lessons Learned

*(This section grows as you run the pipeline — document rate limits, quirks, model behavior, etc.)*

- kie.ai Nano Banana 2: tasks typically complete in 15–30 seconds; budget 90s timeout per image
- Gmail clips HTML emails exceeding 102KB; premailer's CSS inlining adds ~20–30KB to template size
- Claude's tool use output is reliable for structured JSON; retry once on parse failure before debugging
- **kie.ai model name fix**: correct model ID is `nano-banana-2` (not `google/nano-banana-2`); `output_format` must be lowercase `png` not `PNG`
- **kie.ai polling endpoint**: correct URL is `GET /api/v1/jobs/recordInfo?taskId={taskId}` (query param, NOT path param). State field is `state` with values `waiting/queuing/generating/success/fail`. Image URL is inside `resultJson` which is a nested JSON string: parse it and read `resultUrls[0]`.
- **Anthropic API vs Claude Pro plan**: The Python tools call the Anthropic API directly (requires API credits from console.anthropic.com). Claude Pro plan (used by Claude Code) is separate billing. If API credits are zero, Claude Code can substitute Steps 1 and 2 directly: compose Tavily search queries inline, run research.py Tavily portion only, then write content.json manually from research output.
