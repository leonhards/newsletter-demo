"""
Step 6: Send the rendered newsletter via Gmail API.
Sends a multipart/alternative message (plain text + HTML).
Adds UTM tracking parameters to all links in the HTML body.
"""
import argparse
import base64
import json
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")
TMP_DIR = os.path.join(ROOT_DIR, ".tmp")
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
TOKEN_FILE = os.path.join(ROOT_DIR, "token.json")


def load_recipients(list_name: str = "default") -> list[dict]:
    path = os.path.join(CONFIG_DIR, "recipients.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("lists", {}).get(list_name, [])
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
]


def get_gmail_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("gmail", "v1", credentials=creds)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def add_utm(url: str, campaign_slug: str) -> str:
    if not url or url.startswith("#") or url.startswith("mailto:"):
        return url
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.setdefault("utm_source", ["newsletter"])
    params.setdefault("utm_medium", ["email"])
    params.setdefault("utm_campaign", [campaign_slug])
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


def inject_utm(html: str, campaign_slug: str) -> str:
    def replace_href(match):
        url = match.group(1)
        tracked = add_utm(url, campaign_slug)
        return f'href="{tracked}"'
    return re.sub(r'href="([^"]+)"', replace_href, html)


def build_message(sender: str, to: str, subject: str, html: str, plain: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def run(to: str, subject: str, html_path: str, txt_path: str, topic: str):
    sender = os.environ.get("GMAIL_SENDER_ADDRESS", "me")
    campaign_slug = slugify(topic)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    with open(txt_path, "r", encoding="utf-8") as f:
        plain = f.read()

    html = inject_utm(html, campaign_slug)

    service = get_gmail_service()
    message = build_message(sender, to, subject, html, plain)

    print(f"Sending newsletter to {to}...")
    print(f"  Subject: {subject}")
    result = service.users().messages().send(userId="me", body=message).execute()
    print(f"Sent. Gmail message ID: {result['id']}")


if __name__ == "__main__":
    content_path = os.path.join(TMP_DIR, "content.json")
    with open(content_path) as f:
        content = json.load(f)

    parser = argparse.ArgumentParser()
    parser.add_argument("--to", default=None, help="Recipient email (overrides recipients.json)")
    parser.add_argument("--list", default="default", help="Recipient list name from recipients.json")
    parser.add_argument("--subject", default=content.get("subject_line", "Your Newsletter"))
    parser.add_argument("--topic", default=content.get("headline", "newsletter"))
    parser.add_argument("--html", default=os.path.join(TMP_DIR, "newsletter_final.html"))
    parser.add_argument("--txt", default=os.path.join(TMP_DIR, "newsletter_final.txt"))
    args = parser.parse_args()

    if args.to:
        recipients = [{"email": args.to}]
    else:
        recipients = load_recipients(args.list)
        if not recipients:
            print(f"No recipients found in list '{args.list}' in config/recipients.json")
            raise SystemExit(1)

    for recipient in recipients:
        run(recipient["email"], args.subject, args.html, args.txt, args.topic)
