import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from config import MAX_IMAGES_PER_BLOG

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def scrape_blog(url: str) -> tuple:
    """Returns (text_content, image_url_list)"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception:
        return "", []

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)[:3000]

    imgs = []
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("http"):
            imgs.append(src)

    return text, imgs[: MAX_IMAGES_PER_BLOG * 2]

def download_image_as_base64(url: str):
    """Returns (base64_str, media_type) or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if not any(t in ct for t in ["jpeg", "jpg", "png", "webp"]):
            return None

        data = resp.content
        if len(data) > 5 * 1024 * 1024:
            return None

        img = Image.open(BytesIO(data))
        w, h = img.size
        if w < 100 or h < 100:
            return None

        if "png" in ct:
            media_type = "image/png"
        elif "webp" in ct:
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"

        return base64.standard_b64encode(data).decode("utf-8"), media_type
    except Exception:
        return None

def collect_images(image_urls: list) -> list:
    """Returns list of (base64_str, media_type) tuples."""
    images = []
    for url in image_urls:
        if len(images) >= MAX_IMAGES_PER_BLOG:
            break
        result = download_image_as_base64(url)
        if result:
            images.append(result)
    return images
