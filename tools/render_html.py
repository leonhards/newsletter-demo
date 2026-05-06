"""
Step 5: Render the final email-safe HTML newsletter and plain-text version.
Uses Jinja2 for templating and premailer to inline all CSS for Gmail/Outlook compatibility.
Output: .tmp/newsletter_final.html, .tmp/newsletter_final.txt
"""
import argparse
import json
import os
import re
import sys

import base64

import html2text
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from premailer import transform

load_dotenv()

ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")
TMP_DIR = os.path.join(ROOT_DIR, ".tmp")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
SIZE_WARN_KB = 90


def load_style() -> dict:
    path = os.path.join(CONFIG_DIR, "newsletter_style.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_logo_b64(style: dict) -> str:
    logo_path = os.path.join(ROOT_DIR, style.get("logo_path", "brand_assets/logo.png"))
    if not os.path.exists(logo_path):
        return ""
    with open(logo_path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_template(content: dict, asset_urls: dict, style: dict, template_path: str) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    template = env.get_template(os.path.basename(template_path))

    for i, section in enumerate(content.get("sections", [])):
        section["chart_url"] = asset_urls.get(f"section_{i}_chart.png", "")

    return template.render(
        newsletter=content,
        style=style,
        logo_data_uri=load_logo_b64(style),
    )


def inline_css(html: str) -> str:
    return transform(
        html,
        remove_classes=False,
        keep_style_tags=True,
        cssutils_logging_level=None,
    )


def generate_plain_text(html: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_images = True
    h.ignore_links = False
    h.body_width = 72
    h.ignore_emphasis = False
    text = h.handle(html)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def check_size(html: str):
    size_kb = len(html.encode("utf-8")) / 1024
    if size_kb > SIZE_WARN_KB:
        print(
            f"WARNING: Newsletter HTML is {size_kb:.1f}KB — exceeds {SIZE_WARN_KB}KB. "
            f"Gmail clips emails over 102KB. Consider reducing section count."
        )
    else:
        print(f"HTML size: {size_kb:.1f}KB (OK)")


def run(content_path: str, asset_urls_path: str, template_path: str, html_output: str, txt_output: str):
    content = load_json(content_path)
    style = load_style()

    asset_urls = {}
    if os.path.exists(asset_urls_path):
        asset_urls = load_json(asset_urls_path)

    print("Rendering Jinja2 template...")
    raw_html = render_template(content, asset_urls, style, template_path)

    print("Inlining CSS with premailer...")
    final_html = inline_css(raw_html)

    check_size(final_html)

    print("Generating plain-text version...")
    plain_text = generate_plain_text(final_html)

    os.makedirs(os.path.dirname(html_output), exist_ok=True)
    with open(html_output, "w", encoding="utf-8") as f:
        f.write(final_html)

    with open(txt_output, "w", encoding="utf-8") as f:
        f.write(plain_text)

    print(f"Rendered: {html_output}")
    print(f"Rendered: {txt_output}")


if __name__ == "__main__":
    default_template = os.path.join(TEMPLATES_DIR, "newsletter.html.j2")
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", default=os.path.join(TMP_DIR, "content.json"))
    parser.add_argument("--asset-urls", default=os.path.join(TMP_DIR, "asset_urls.json"))
    parser.add_argument("--template", default=default_template)
    parser.add_argument("--html-output", default=os.path.join(TMP_DIR, "newsletter_final.html"))
    parser.add_argument("--txt-output", default=os.path.join(TMP_DIR, "newsletter_final.txt"))
    args = parser.parse_args()
    run(args.content, args.asset_urls, args.template, args.html_output, args.txt_output)
