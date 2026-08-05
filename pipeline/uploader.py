"""
Optional: auto-uploads the finished video to YouTube as a Short.

One-time setup (free):
1. Go to console.cloud.google.com, create a project, enable "YouTube Data API v3".
2. Create OAuth 2.0 credentials (Desktop app type), download as client_secret.json
   into this project's root folder.
3. First time you run this file directly, a browser window opens for you to
   authorize your own channel. It saves a token.json afterward so future
   automated runs (cron/GitHub Actions) don't need to re-authorize.

Free quota is ~10,000 units/day; one upload costs ~1,600 units, so this
comfortably supports several uploads a day at zero cost.
"""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = ROOT / "token.json"
CLIENT_SECRET_FILE = ROOT / "client_secret.json"


def _get_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    "client_secret.json not found. See the setup steps in "
                    "this file's docstring."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_short(video_path: Path, title: str, description: str = "", tags: list[str] | None = None) -> str:
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or [],
            "categoryId": "27",  # Education
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    print(f"Uploaded: https://youtube.com/shorts/{video_id}")
    return video_id


if __name__ == "__main__":
    import sys

    upload_short(Path(sys.argv[1]), title=sys.argv[2] if len(sys.argv) > 2 else "Untitled")
