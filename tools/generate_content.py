"""
Step 2: Generate structured newsletter content from research.
Uses Claude with prompt caching on the research block.
Output: .tmp/content.json
"""
import argparse
import json
import os
import re
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TMP_DIR = os.path.join(os.path.dirname(__file__), "..", ".tmp")

CONTENT_SCHEMA = {
    "name": "newsletter_content",
    "description": "Structured newsletter content ready for HTML rendering",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject_line": {"type": "string", "description": "Email subject line, max 50 characters"},
            "preheader": {"type": "string", "description": "Preview text shown in email clients, max 90 characters"},
            "headline": {"type": "string", "description": "Main newsletter headline"},
            "subheadline": {"type": "string", "description": "Supporting subheadline"},
            "introduction": {"type": "string", "description": "2-3 sentence intro paragraph"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string", "description": "3-5 sentence section body"},
                        "key_stat": {
                            "type": "object",
                            "properties": {
                                "value": {"type": "string", "description": "e.g. 72% or $4.2B"},
                                "label": {"type": "string"},
                                "source": {"type": "string"},
                            },
                            "required": ["value", "label", "source"],
                        },
                        "chart_type": {
                            "type": "string",
                            "enum": ["bar", "line", "pie", "stat_card", "none"],
                        },
                    },
                    "required": ["title", "body", "key_stat", "chart_type"],
                },
                "minItems": 3,
                "maxItems": 5,
            },
            "key_takeaways": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 3,
            },
            "call_to_action": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["text", "url"],
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["title", "url"],
                },
            },
        },
        "required": [
            "subject_line", "preheader", "headline", "subheadline",
            "introduction", "sections", "key_takeaways", "call_to_action", "sources",
        ],
    },
}

SPAM_WORDS = ["free", "guaranteed", "winner", "limited time", "act now", "urgent", "congratulations"]


def flag_unverified_stats(content: dict, sources: list[dict]) -> dict:
    all_source_text = " ".join(s.get("content", "") for s in sources).lower()
    for section in content.get("sections", []):
        stat_value = section.get("key_stat", {}).get("value", "").lower()
        digits = re.sub(r"[^0-9.]", "", stat_value)
        if digits and digits not in all_source_text:
            section["key_stat"]["unverified"] = True
    return content


def check_subject_line(subject: str) -> list[str]:
    warnings = []
    if len(subject) > 50:
        warnings.append(f"Subject line is {len(subject)} chars (limit: 50)")
    for word in SPAM_WORDS:
        if word in subject.lower():
            warnings.append(f"Subject line contains spam trigger word: '{word}'")
    return warnings


def run(topic: str, research_path: str, output_path: str):
    with open(research_path, "r", encoding="utf-8") as f:
        research = json.load(f)

    sources = research["sources"]
    source_text = "\n\n".join(
        f"Source: {s['title']}\nURL: {s['url']}\nContent: {s['content']}" for s in sources
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print("Generating newsletter content via Claude...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=(
            "You are an expert newsletter writer. Write engaging, factual content grounded strictly in the "
            "provided research sources. Do not invent statistics or facts not supported by the sources. "
            "Write in a clear, professional tone suitable for a business audience."
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Here are the research sources for this newsletter:",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": source_text,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Write a complete newsletter about: {topic}\n\n"
                            "Use the newsletter_content tool to return your response. "
                            "Every key_stat must come directly from the research sources above. "
                            "Subject line must be under 50 characters. "
                            "Preheader must be under 90 characters. "
                            "Choose chart_type based on what best visualises the key_stat for each section."
                        ),
                    },
                ],
            }
        ],
        tools=[CONTENT_SCHEMA],
        tool_choice={"type": "tool", "name": "newsletter_content"},
    )

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    content = tool_use_block.input

    content = flag_unverified_stats(content, sources)

    warnings = check_subject_line(content.get("subject_line", ""))
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  ⚠ {w}")

    unverified = [
        s["title"] for s in content.get("sections", [])
        if s.get("key_stat", {}).get("unverified")
    ]
    if unverified:
        print(f"UNVERIFIED STATS in sections: {unverified}")
        print("Review these before sending — the stat value was not found verbatim in the research sources.")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    print(f"Content generated. {len(content['sections'])} sections saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--research", default=os.path.join(TMP_DIR, "research.json"))
    parser.add_argument("--output", default=os.path.join(TMP_DIR, "content.json"))
    args = parser.parse_args()
    run(args.topic, args.research, args.output)
