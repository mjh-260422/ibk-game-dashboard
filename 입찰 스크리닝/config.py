import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
GOOGLE_SHEETS_KEY_PATH = os.environ.get(
    "GOOGLE_SHEETS_KEY_PATH",
    str(Path.home() / ".claude" / "google-sheets-key.json")
)
OUTPUT_SPREADSHEET_ID = os.environ.get("OUTPUT_SPREADSHEET_ID", "")

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_IMAGES_PER_BLOG = 5
MAX_URLS_PER_GROUP = 25
SEARCH_RESULTS_PER_KEYWORD = 5

SUPPLIERS = [
    "GS엠비즈", "즐거운", "쿠프마케팅", "네이버파이낸셜", "윈큐브마케팅",
    "기프티쇼(KT엠하우스)", "케이티알파", "다우기술", "엠트웰브(기프트팝)",
    "카카오선물하기", "이지코드", "CJ올리브네트웍스", "모바일리더",
]
