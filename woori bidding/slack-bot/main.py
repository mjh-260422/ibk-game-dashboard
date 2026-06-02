import asyncio
import tempfile

from fastapi import FastAPI, Request, Response

from image_parser import parse_bid_image
from message_builder import build_result_message
from sheets import write_sim_block
from slack_handler import (
    download_image,
    is_bid_channel,
    post_thread_reply,
    upload_files,
    verify_signature,
)

app = FastAPI()


@app.post("/slack/events")
async def slack_events(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_signature(body, timestamp, signature):
        return Response(status_code=401)

    payload = await request.json()

    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    event = payload.get("event", {})
    if event.get("type") != "message":
        return Response(status_code=200)
    if event.get("bot_id"):
        return Response(status_code=200)
    if not is_bid_channel(event.get("channel", "")):
        return Response(status_code=200)

    files = event.get("files", [])
    if not files:
        return Response(status_code=200)

    asyncio.create_task(_process_files(files, event["channel"], event["ts"]))
    return Response(status_code=200)


async def _process_files(files: list, channel: str, thread_ts: str) -> None:
    results = []
    for file in files:
        try:
            image_bytes, media_type = download_image(file["id"])
            bid = parse_bid_image(image_bytes, media_type)
            write_result = write_sim_block(bid)
            message = build_result_message(bid, write_result)
            results.append(message)

            try:
                from quotation import convert_to_pdf, create_quotation_excel  # noqa: PLC0415

                with tempfile.TemporaryDirectory() as tmpdir:
                    xlsx = create_quotation_excel(bid, tmpdir)
                    try:
                        pdf = convert_to_pdf(xlsx)
                        upload_files(channel, thread_ts, [xlsx, pdf], comment="📄 견적서")
                    except Exception as e:
                        upload_files(channel, thread_ts, [xlsx], comment=f"📄 견적서 (PDF 변환 실패: {e})")
            except ImportError:
                print("quotation 모듈 없음 — 견적서 생략")

        except Exception as e:
            results.append(f"❌ 처리 실패 ({file.get('name', '?')}): {e}")

    try:
        post_thread_reply(channel, thread_ts, "\n\n---\n\n".join(results))
    except Exception as e:
        print(f"Slack 메시지 전송 실패: {e}")
