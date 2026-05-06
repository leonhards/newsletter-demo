"""
Step 4: Upload infographic PNGs from .tmp/assets/ to Google Drive (public share).
Returns a JSON map of filename -> direct image URL.
Output: .tmp/asset_urls.json
"""
import argparse
import json
import os

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

TMP_DIR = os.path.join(os.path.dirname(__file__), "..", ".tmp")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
]


def get_drive_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_file(service, local_path: str, folder_id: str) -> str:
    filename = os.path.basename(local_path)
    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype="image/png", resumable=False)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webContentLink",
    ).execute()

    file_id = uploaded["id"]

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    direct_url = f"https://drive.google.com/uc?export=view&id={file_id}"
    return direct_url


def run(assets_dir: str, folder_id: str, output_path: str):
    if not folder_id:
        raise ValueError("DRIVE_IMAGES_FOLDER_ID is not set in .env")

    pngs = [f for f in os.listdir(assets_dir) if f.endswith(".png")]
    if not pngs:
        print("No PNG files found in assets dir — writing empty asset_urls.json")
        with open(output_path, "w") as f:
            json.dump({}, f)
        return

    service = get_drive_service()
    url_map = {}

    for filename in sorted(pngs):
        local_path = os.path.join(assets_dir, filename)
        print(f"  Uploading {filename}...")
        url = upload_file(service, local_path, folder_id)
        url_map[filename] = url
        print(f"    -> {url}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(url_map, f, indent=2)

    print(f"Upload complete. {len(url_map)} images. URLs saved to {output_path}")


if __name__ == "__main__":
    drive_folder_id = os.environ.get("DRIVE_IMAGES_FOLDER_ID", "")
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-dir", default=os.path.join(TMP_DIR, "assets"))
    parser.add_argument("--drive-folder-id", default=drive_folder_id)
    parser.add_argument("--output", default=os.path.join(TMP_DIR, "asset_urls.json"))
    args = parser.parse_args()
    run(args.assets_dir, args.drive_folder_id, args.output)
