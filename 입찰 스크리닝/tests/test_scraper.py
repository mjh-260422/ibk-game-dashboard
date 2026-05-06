from unittest.mock import patch, MagicMock
from scraper import scrape_blog, collect_images

SAMPLE_HTML = """
<html><body>
<nav>Navigation</nav>
<main>
  <p>우리카드 GS25 쿠폰 이벤트를 받았습니다. 기프티쇼 문자로 왔어요!</p>
  <img src="https://example.com/coupon_large.jpg" />
  <img src="https://example.com/icon_tiny.png" />
</main>
<footer>Footer</footer>
</body></html>
"""

def _make_mock_resp(html):
    m = MagicMock()
    m.text = html
    m.raise_for_status.return_value = None
    return m

def test_scrape_blog_extracts_text():
    with patch("scraper.requests.get", return_value=_make_mock_resp(SAMPLE_HTML)):
        text, _ = scrape_blog("https://example.com/blog")
    assert "우리카드 GS25" in text
    assert "기프티쇼" in text

def test_scrape_blog_removes_nav_and_footer():
    with patch("scraper.requests.get", return_value=_make_mock_resp(SAMPLE_HTML)):
        text, _ = scrape_blog("https://example.com/blog")
    assert "Navigation" not in text
    assert "Footer" not in text

def test_scrape_blog_extracts_image_urls():
    with patch("scraper.requests.get", return_value=_make_mock_resp(SAMPLE_HTML)):
        _, images = scrape_blog("https://example.com/blog")
    assert "https://example.com/coupon_large.jpg" in images

def test_scrape_blog_handles_connection_error():
    with patch("scraper.requests.get", side_effect=Exception("timeout")):
        text, images = scrape_blog("https://example.com/bad")
    assert text == ""
    assert images == []

def test_collect_images_skips_unavailable_urls():
    with patch("scraper.download_image_as_base64", return_value=None):
        result = collect_images(["https://example.com/bad.jpg"])
    assert result == []
