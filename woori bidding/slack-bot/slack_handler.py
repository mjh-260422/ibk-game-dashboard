import hashlib
import hmac
import os
import time

import httpx
from slack_sdk import WebClient

from config import BID_CHANNEL_ID, SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET

slack_client = WebClient(token=SLACK_BOT_TOKEN)


def verify_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - float(timestamp)) > 300:
        return False
    base = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(SLACK_SIGNING_SECRET.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def download_image(file_id: str) -> tuple[bytes, str]:
    info = slack_client.files_info(file=file_id)["file"]
    url = info["url_private_download"]
    media_type = info.get("mimetype", "image/jpeg")
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    resp = httpx.get(url, headers=headers, follow_redirects=True)
    resp.raise_for_status()
    return resp.content, media_type


def post_thread_reply(channel: str, thread_ts: str, text: str) -> None:
    slack_client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text, mrkdwn=True)


def upload_files(channel: str, thread_ts: str, files: list[str], comment: str = "") -> None:
    for i, file_path in enumerate(files):
        slack_client.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            file=file_path,
            filename=os.path.basename(file_path),
            initial_comment=comment if i == 0 else "",
        )


def is_bid_channel(channel_id: str) -> bool:
    return channel_id == BID_CHANNEL_ID
