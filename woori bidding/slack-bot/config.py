import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SIMULATION_SPREADSHEET_ID = os.environ["SIMULATION_SPREADSHEET_ID"]
BID_CHANNEL_ID = os.environ["BID_CHANNEL_ID"]

_key_raw = os.environ.get("GOOGLE_SHEETS_KEY_JSON")
_key_file = os.environ.get(
    "GOOGLE_SHEETS_KEY_FILE",
    str(Path.home() / ".claude" / "google-sheets-key.json"),
)

def get_google_creds_info() -> dict:
    try:
        if _key_raw:
            return json.loads(_key_raw)
        with open(_key_file, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ValueError(f"Google Sheets 키 파일을 찾을 수 없음: {_key_file}") from e
    except json.JSONDecodeError as e:
        raise ValueError("Google Sheets 키 JSON 파싱 실패") from e
