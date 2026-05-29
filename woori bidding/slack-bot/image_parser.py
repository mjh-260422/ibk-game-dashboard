import json
import base64
import anthropic
from dataclasses import dataclass
from config import ANTHROPIC_API_KEY

@dataclass
class ProductInfo:
    name: str
    face_value: int
    quantity: int
    discount_rate: float

@dataclass
class BidInfo:
    bid_number: str
    event_name: str
    manager: str
    is_pin_delivery: bool
    products: list[ProductInfo]

SYSTEM_PROMPT = """당신은 우리카드 모바일쿠폰 입찰 공고 이미지에서 정보를 추출하는 전문가입니다.
이미지에서 아래 정보를 추출하여 반드시 JSON만 출력하세요. 다른 텍스트는 절대 포함하지 마세요.

{
  "bid_number": "입찰번호(숫자만, 예: 1766)",
  "event_name": "이벤트/캠페인명",
  "manager": "담당자명",
  "is_pin_delivery": true/false (공고에 'PIN번호 전달 희망' 문구가 있으면 true),
  "products": [
    {
      "name": "품목명 (브랜드명 포함, 예: [스타벅스] 아이스 아메리카노 Tall)",
      "face_value": 액면가(정수, 단위 원),
      "quantity": 수량(정수),
      "discount_rate": 제안할인율(실수, %, 예: 18.0)
    }
  ]
}"""

def parse_bid_image(image_bytes: bytes, media_type: str) -> BidInfo:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "이 입찰 공고 이미지에서 정보를 추출해주세요."}
            ]
        }],
        system=SYSTEM_PROMPT,
    )

    data = json.loads(response.content[0].text)
    products = [ProductInfo(**p) for p in data["products"]]
    return BidInfo(
        bid_number=data["bid_number"],
        event_name=data["event_name"],
        manager=data["manager"],
        is_pin_delivery=data["is_pin_delivery"],
        products=products,
    )
