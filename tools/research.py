"""
Step 1: Research a topic using Tavily search.
Decomposes the topic into focused queries via Claude, then runs each through Tavily.
Output: .tmp/research.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]

TMP_DIR = os.path.join(os.path.dirname(__file__), "..", ".tmp")


def decompose_topic(client: anthropic.Anthropic, topic: str, depth: int) -> list[str]:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    f"You are helping research a newsletter topic. Break the following topic into exactly {depth} "
                    f"focused search queries that together cover: latest news/developments, key statistics/data, "
                    f"key players or companies, and future outlook or implications.\n\n"
                    f"Topic: {topic}\n\n"
                    f"Return ONLY a JSON array of {depth} query strings, nothing else. "
                    f'Example: ["query one", "query two", "query three", "query four"]'
                ),
            }
        ],
    )
    return json.loads(response.content[0].text.strip())


def search(tavily: TavilyClient, query: str) -> list[dict]:
    result = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5,
        include_raw_content=False,
    )
    return result.get("results", [])


def run(topic: str, depth: int, output_path: str):
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

    print(f"Decomposing topic into {depth} search queries...")
    queries = decompose_topic(anthropic_client, topic, depth)
    print(f"Queries: {queries}")

    seen_urls = set()
    sources = []

    for query in queries:
        print(f"  Searching: {query}")
        results = search(tavily_client, query)
        if len(results) < 3:
            # Broaden and retry once
            print(f"  Only {len(results)} results — retrying with broader query...")
            results = search(tavily_client, topic + " " + query)

        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(
                    {
                        "title": r.get("title", ""),
                        "url": url,
                        "content": r.get("content", ""),
                        "score": r.get("score", 0.0),
                    }
                )

    if len(sources) < 3:
        print("ERROR: Fewer than 3 unique sources found. Check TAVILY_API_KEY and try a broader topic.")
        sys.exit(1)

    output = {
        "topic": topic,
        "queries_used": queries,
        "sources": sources,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Research complete. {len(sources)} sources saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--output", default=os.path.join(TMP_DIR, "research.json"))
    args = parser.parse_args()
    run(args.topic, args.depth, args.output)
