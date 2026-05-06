# Newsletter Pipeline

Generate and send a branded Hiralis Intelligence Brief newsletter on any topic.

**Usage:** `/newsletter <topic>`

---

## What This Skill Does

Runs the full WAT pipeline: research → content → infographics → upload → render → send.

**Important:** Steps 1 and 2 are handled directly by Claude (no Anthropic API key needed — Claude Code uses the Pro plan). Steps 3–6 use Python tools.

---

## Step 1 — Research (Claude + Tavily)

Compose 4 focused search queries covering:
- Latest news and developments
- Key statistics and market data
- Key players, companies, and startups
- Future outlook and risks

Then run this Python snippet (replace queries with the ones you composed):

```
python -c "
import json, os, sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
tavily = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])

topic = '<TOPIC>'
queries = [
    '<QUERY 1>',
    '<QUERY 2>',
    '<QUERY 3>',
    '<QUERY 4>'
]

seen_urls = set()
sources = []
for q in queries:
    print(f'Searching: {q}')
    result = tavily.search(query=q, search_depth='advanced', max_results=5, include_raw_content=False)
    for r in result.get('results', []):
        url = r.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({'title': r.get('title',''), 'url': url, 'content': r.get('content',''), 'score': r.get('score', 0.0)})

print(f'Total sources: {len(sources)}')
os.makedirs('.tmp', exist_ok=True)
with open('.tmp/research.json', 'w', encoding='utf-8') as f:
    json.dump({'topic': topic, 'queries_used': queries, 'sources': sources, 'generated_at': datetime.now(timezone.utc).isoformat()}, f, indent=2, ensure_ascii=False)
print('Saved to .tmp/research.json')
"
```

**Success check:** `.tmp/research.json` has at least 3 sources.

---

## Step 2 — Generate Content (Claude writes directly)

Read `.tmp/research.json`. Using only facts present in those sources, write `.tmp/content.json` with this exact schema:

```json
{
  "subject_line": "...",        // max 50 chars, no spam words
  "preheader": "...",           // max 90 chars
  "headline": "...",
  "subheadline": "...",
  "introduction": "...",        // 2-3 sentences
  "sections": [                 // 3-5 sections
    {
      "title": "...",
      "body": "...",            // 3-5 sentences, grounded in sources
      "key_stat": {
        "value": "...",         // e.g. "$4.2B" or "72%"
        "label": "...",
        "source": "..."         // domain or publication name
      },
      "chart_type": "bar|line|pie|stat_card|none"
    }
  ],
  "key_takeaways": ["...", "...", "..."],   // exactly 3
  "call_to_action": {
    "text": "...",
    "url": "..."                // use a real source URL
  },
  "sources": [
    {"title": "...", "url": "..."}
  ]
}
```

**Rules:**
- Every `key_stat.value` must come from the research sources
- `subject_line` under 50 chars — check manually: count characters
- No invented statistics

---

## Step 3 — Infographics (kie.ai)

```
python tools/generate_infographics.py
```

**Costs ~$0.02/image.** Non-blocking — pipeline continues if some fail.

**Known quirks (already fixed in the tool):**
- Model: `nano-banana-2` (no prefix)
- output_format: `png` (lowercase)
- Polling endpoint: `GET /api/v1/jobs/recordInfo?taskId={taskId}` (query param)
- State field: `state` (values: `waiting/queuing/generating/success/fail`)
- Image URL: inside `resultJson` — a nested JSON string → parse it → `resultUrls[0]`

---

## Step 4 — Upload to Google Drive

```
python tools/upload_assets.py --drive-folder-id {DRIVE_IMAGES_FOLDER_ID}
```

The folder ID is already in `.env` as `DRIVE_IMAGES_FOLDER_ID`. If no images were generated, this produces an empty `asset_urls.json` and the render step handles it gracefully.

**If token.json is expired:** run `python tools/auth_google.py` first.

---

## Step 5 — Render HTML

```
python tools/render_html.py
```

CSS `linear-gradient` warnings from premailer are harmless — Gmail doesn't support gradients anyway, the fallback color is used.

**Success check:** `.tmp/newsletter_final.html` exists and is under 90KB (Gmail clips above 102KB; premailer adds ~20–30KB overhead).

---

## Step 6 — Send via Gmail

```
python tools/send_gmail.py --to {recipient_email}
```

Default recipient is `leonhardsinaga@gmail.com` (from `config/recipients.json`).

---

## Full Run Checklist

| Step | Command | Cost |
|------|---------|------|
| 1. Research | Python inline (Tavily) | ~free |
| 2. Content | Claude writes directly | free (Pro plan) |
| 3. Infographics | `python tools/generate_infographics.py` | ~$0.02/image |
| 4. Upload | `python tools/upload_assets.py` | free |
| 5. Render | `python tools/render_html.py` | free |
| 6. Send | `python tools/send_gmail.py --to ...` | free |

## Common Errors

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Google 403 access_denied | Add email as test user in OAuth consent screen |
| Gmail API disabled | Enable Gmail API + Drive API in Google Cloud Console |
| kie.ai 402 credits | Top up at kie.ai — then rerun steps 3–6 only |
| token.json expired | `python tools/auth_google.py` |
| HTML > 90KB | Remove one section from `.tmp/content.json`, rerun steps 5–6 |
