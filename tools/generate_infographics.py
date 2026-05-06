"""
Step 3: Generate infographic images for each newsletter section using kie.ai Nano Banana 2.
Polls the async task API until images are ready, then downloads them locally.
Output: .tmp/assets/section_N_chart.png
"""
import argparse
import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

KIE_API_KEY = os.environ["KIE_API_KEY"]
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def load_style() -> dict:
    path = os.path.join(CONFIG_DIR, "newsletter_style.json")
    with open(path, "r", encoding="utf-8") as f:
        import json
        return json.load(f)
KIE_BASE_URL = "https://api.kie.ai"
KIE_MODEL = "nano-banana-2"

TMP_DIR = os.path.join(os.path.dirname(__file__), "..", ".tmp")
ASSETS_DIR = os.path.join(TMP_DIR, "assets")

POLL_INTERVAL = 5
POLL_TIMEOUT = 90


def build_prompt(section: dict, style: dict) -> str:
    title = section["title"]
    body = section["body"]
    stat = section.get("key_stat", {})
    stat_value = stat.get("value", "")
    stat_label = stat.get("label", "")
    chart_type = section.get("chart_type", "stat_card")

    style_map = {
        "bar": "a clean horizontal bar chart infographic",
        "line": "a clean line graph infographic showing a trend over time",
        "pie": "a clean pie chart infographic with percentage labels",
        "stat_card": "a bold, modern stat callout card with a large number prominently centered",
    }
    chart_description = style_map.get(chart_type, "a clean data infographic")

    infographic_style = style.get("infographic_style", "dark background, purple accent, white text, minimal")

    return (
        f"Create {chart_description} for a professional AI technology newsletter. "
        f"Topic: '{title}'. "
        f"Key statistic to feature prominently: {stat_value} — {stat_label}. "
        f"Context: {body[:200]}. "
        f"Visual style: {infographic_style}. "
        f"The stat value '{stat_value}' must appear large and bold. "
        f"No clipart, no stock photo style, no watermarks, no brand names in the image. "
        f"Landscape orientation, 16:9 aspect ratio."
    )


def create_task(client: httpx.Client, prompt: str) -> str:
    response = client.post(
        f"{KIE_BASE_URL}/api/v1/jobs/createTask",
        headers={
            "Authorization": f"Bearer {KIE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": KIE_MODEL,
            "input": {
                "prompt": prompt,
                "image_size": "16:9",
                "output_format": "png",
            },
        },
    )
    response.raise_for_status()
    data = response.json()
    api_code = data.get("code") if isinstance(data, dict) else None
    if api_code is not None and api_code != 200:
        raise ValueError(f"kie.ai error {api_code}: {data.get('msg', data)}")
    inner = data.get("data") if isinstance(data, dict) else None
    task_id = (inner or {}).get("taskId") or data.get("taskId")
    if not task_id:
        raise ValueError(f"No taskId in response: {data}")
    return task_id


def poll_task(client: httpx.Client, task_id: str) -> str | None:
    import json as _json
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        response = client.get(
            f"{KIE_BASE_URL}/api/v1/jobs/recordInfo",
            params={"taskId": task_id},
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
        )
        response.raise_for_status()
        data = response.json()
        job = data.get("data") or {}
        state = job.get("state", "")

        if state == "success":
            result_raw = job.get("resultJson") or "{}"
            result = _json.loads(result_raw) if isinstance(result_raw, str) else result_raw
            urls = result.get("resultUrls") or []
            return urls[0] if urls else None
        elif state == "fail":
            print(f"    Task {task_id} failed")
            return None

        time.sleep(POLL_INTERVAL)

    print(f"    Task {task_id} timed out after {POLL_TIMEOUT}s")
    return None


def download_image(url: str, dest_path: str):
    with httpx.Client(timeout=30) as client:
        response = client.get(url)
        response.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(response.content)


def run(content_path: str, output_dir: str):
    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)

    style = load_style()
    os.makedirs(output_dir, exist_ok=True)
    sections = content.get("sections", [])
    generated = 0

    with httpx.Client(timeout=30) as client:
        for i, section in enumerate(sections):
            chart_type = section.get("chart_type", "none")
            if chart_type == "none":
                print(f"  Section {i} ({section['title'][:40]}): skipped (chart_type=none)")
                continue

            print(f"  Section {i} ({section['title'][:40]}): generating {chart_type}...")
            prompt = build_prompt(section, style)

            try:
                task_id = create_task(client, prompt)
                print(f"    Task created: {task_id}. Polling...")
                image_url = poll_task(client, task_id)

                if image_url:
                    dest = os.path.join(output_dir, f"section_{i}_chart.png")
                    download_image(image_url, dest)
                    print(f"    Saved: {dest}")
                    generated += 1
                else:
                    print(f"    No image URL returned — skipping this section.")

            except Exception as e:
                print(f"    ERROR: {e} — skipping section {i} (pipeline continues)")

    print(f"Infographics done. {generated}/{len(sections)} images generated in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", default=os.path.join(TMP_DIR, "content.json"))
    parser.add_argument("--output-dir", default=ASSETS_DIR)
    args = parser.parse_args()
    run(args.content, args.output_dir)
