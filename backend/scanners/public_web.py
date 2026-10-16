# -*- coding: utf-8 -*-
"""
Scanner v1: tìm reels / bài viết / tin tức công khai qua web search.

Cách hoạt động (best-effort, không cần đăng nhập, không API key):
  1. Gửi NHIỀU truy vấn SONG SONG tới DuckDuckGo (giao diện HTML công khai)
     với các biến thể như "site:instagram.com reel <từ khóa> nấu ăn"
     (ThreadPoolExecutor — vừa nhanh vừa nhiều kết quả, mục tiêu 15-20).
  2. Bóc tách tiêu đề + link + đoạn trích từ HTML trả về, khử trùng URL.
  3. Đối chiếu từng token của từ khóa với TIÊU ĐỀ và ĐOẠN TRÍCH (đóng vai
     trò "phụ đề/caption") -> ghi nhận khớp ở đâu: ["title"] / ["caption"].
  4. Lấy ảnh og:image của các trang gốc SONG SONG (timeout ngắn); trang nào
     không lấy được thì dùng ảnh placeholder do app tự vẽ — MỖI kết quả
     luôn có ảnh.
  5. Tóm tắt cực ngắn do APP tự tạo từ từ khóa + khẩu vị user chọn
     (KHÔNG copy caption gốc của reel).

Giới hạn đã biết (ghi rõ cho user trong README):
  - Instagram/Facebook chặn bot khá mạnh nên kết quả có thể ít hoặc trống;
    khi đó app trả về trạng thái trống thân thiện thay vì lỗi.
  - Không bao giờ thử đăng nhập hay cào dữ liệu hàng loạt.
"""
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import unquote, quote

import requests

from .base import ScannerAdapter, ScanResult, ScanBundle

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}
DDG_HTML_URL = "https://html.duckduckgo.com/html/"

# Khẩu vị app hỗ trợ -> dùng để đoán taste_tags từ tiêu đề/snippet
TASTE_WORDS = {
    "mặn": "mặn",
    "ngọt": "ngọt",
    "cay": "cay",
    "chua": "chua",
    "béo": "béo ngậy",
    "béo ngậy": "béo ngậy",
    "thanh đạm": "thanh đạm",
    "thanh dam": "thanh đạm",
    "chay": "chay",
}

# Ảnh placeholder khi không lấy được thumbnail (SVG tự vẽ, nhúng data URI)
_PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">'
    '<rect width="400" height="300" fill="#f3e8d3"/>'
    '<text x="200" y="140" font-size="72" text-anchor="middle">🍲</text>'
    '<text x="200" y="200" font-size="20" text-anchor="middle" '
    'fill="#8a6d3b" font-family="sans-serif">Tủ Lạnh Nấu Gì</text>'
    "</svg>"
)
PLACEHOLDER_IMG = "data:image/svg+xml;utf8," + quote(_PLACEHOLDER_SVG)


def strip_accents(text):
    """Bỏ dấu tiếng Việt để đối chiếu keyword tolerant hơn."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", text).lower()


def norm(text):
    return strip_accents(text)


def _clean_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return unescape(text).strip()


def _unwrap_ddg_url(href):
    """DuckDuckGo bọc link thật trong /l/?uddg=... -> gỡ ra."""
    href = unescape(href or "")
    m = re.search(r"[?&]uddg=([^&]+)", href)
    if m:
        return unquote(m.group(1))
    return href


def _norm_url(url):
    """Chuẩn hóa URL để khử trùng lặp (bỏ tracking params, slash cuối)."""
    url = (url or "").strip().lower().rstrip("/")
    url = re.sub(r"[?&](utm_[^=&]*|fbclid|gclid)=[^&]*", "", url).rstrip("?&")
    return url


class PublicWebScanner(ScannerAdapter):
    name = "public_web"

    def __init__(self, timeout=6, max_results=8, img_timeout=4):
        self.timeout = timeout          # timeout mỗi request tìm kiếm (giây)
        self.max_results = max_results  # số kết quả tối đa mỗi truy vấn
        self.img_timeout = img_timeout  # timeout lấy thumbnail (giây)

    # ---------------- tìm kiếm thô ----------------
    def _ddg_search(self, query):
        """Trả về list dict {title, url, snippet}; [] nếu bị chặn/lỗi."""
        try:
            resp = requests.post(
                DDG_HTML_URL,
                data={"q": query},
                headers=HEADERS,
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return []
            html = resp.text
        except Exception:
            return []

        titles = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html, re.S,
        )
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S
        )
        out = []
        for i, (href, raw_title) in enumerate(titles[: self.max_results]):
            url = _unwrap_ddg_url(href)
            if not url.startswith("http"):
                continue
            snippet = _clean_html(snippets[i]) if i < len(snippets) else ""
            out.append({
                "title": _clean_html(raw_title),
                "url": url,
                "snippet": snippet,
            })
        return out

    # ---------------- ảnh món ăn ----------------
    def _fetch_og_image(self, url):
        """Thử lấy og:image của trang gốc; None nếu không được."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=self.img_timeout)
            if resp.status_code != 200:
                return None
            html = resp.text[:200000]  # chỉ đọc phần đầu cho nhanh
            m = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html, re.I,
            ) or re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.I,
            )
            if m:
                img = unescape(m.group(1)).strip()
                if img.startswith("http"):
                    return img
        except Exception:
            pass
        return None

    # ---------------- chạy song song ----------------
    def _parallel_search(self, queries):
        """Chạy nhiều truy vấn tìm kiếm SONG SONG.

        queries: list[(source, query_text)].
        Trả về list[(source, items)] theo đúng thứ tự queries.
        """
        results = [None] * len(queries)

        def _one(i):
            source, q = queries[i]
            return i, source, self._ddg_search(q)

        with ThreadPoolExecutor(max_workers=min(8, len(queries))) as ex:
            futures = [ex.submit(_one, i) for i in range(len(queries))]
            for fut in futures:
                i, source, items = fut.result()
                results[i] = (source, items)
        return results

    def _fill_images_parallel(self, results):
        """Lấy thumbnail SONG SONG cho danh sách kết quả.

        Mỗi kết quả LUÔN có image_url sau hàm này (og:image thật,
        hoặc ảnh placeholder do app tự vẽ nếu không lấy được).
        """
        def _one(r):
            try:
                r.image_url = self._fetch_og_image(r.url) or PLACEHOLDER_IMG
            except Exception:
                r.image_url = PLACEHOLDER_IMG
            return r

        with ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(_one, results))
        return results

    # ---------------- đối chiếu keyword ----------------
    def _match_where(self, tokens, title, snippet):
        """Trả về ["title"] và/hoặc ["caption"] tùy nơi keyword xuất hiện."""
        n_title, n_snip = norm(title), norm(snippet)
        in_title = any(t in n_title for t in tokens)
        in_snip = any(t in n_snip for t in tokens)
        where = []
        if in_title:
            where.append("title")
        if in_snip:
            where.append("caption")
        return where

    def _extract_tastes(self, text):
        n = norm(text)
        found = []
        for word, tag in TASTE_WORDS.items():
            if norm(word) in n and tag not in found:
                found.append(tag)
        return found

    # ---------------- tóm tắt do app tự tạo ----------------
    def _make_summary(self, keyword, tastes, servings):
        # Triết lý "nhiều hình, ít chữ": tóm tắt cực ngắn, không dài dòng
        vi_tastes = ", ".join(tastes) if tastes else "đậm đà"
        portion = f" · {servings} người" if servings else ""
        return (f"Vị {vi_tastes}{portion} · "
                f"Nguyên liệu: {keyword.lower()} + gia vị cơ bản")

    # ---------------- API chính ----------------
    def _build_results(self, raw_items, source, keyword, tastes, servings):
        """Biến kết quả thô thành ScanResult (chưa có ảnh, chưa xếp hạng).

        Ảnh được lấy sau, SONG SONG, ở _fill_images_parallel.
        """
        tokens = [t for t in norm(keyword).split() if len(t) > 1]
        results = []
        for item in raw_items:
            where = self._match_where(tokens, item["title"], item["snippet"])
            if tokens and not where:
                continue  # bỏ kết quả không liên quan keyword
            results.append(ScanResult(
                title=item["title"] or keyword,
                url=item["url"],
                source=source,
                image_url="",  # điền sau bằng _fill_images_parallel
                summary=self._make_summary(keyword, tastes, servings),
                matched_in=where or ["title"],
                snippet=item["snippet"][:300],
                taste_tags=self._extract_tastes(
                    item["title"] + " " + item["snippet"]),
            ))
        return results

    def _rank(self, results, tastes):
        """Ưu tiên kết quả hợp khẩu vị user chọn; giữ thứ tự ổn định."""
        picked = set(tastes or [])
        results.sort(
            key=lambda r: len(set(r.taste_tags) & picked), reverse=True)
        return results

    def _dedupe(self, results):
        seen, out = set(), []
        for r in results:
            key = _norm_url(r.url)
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    def scan_reels(self, keyword, tastes=None, servings=""):
        """Tìm reels nấu ăn: 4 truy vấn SONG SONG, mục tiêu 15-20 kết quả.

        Vẫn lazy (chỉ chạy khi user bấm tìm); cache do tầng app.py lo.
        """
        tastes = tastes or []
        queries = [
            ("instagram", f"site:instagram.com reel {keyword} nấu ăn"),
            ("instagram", f"site:instagram.com {keyword} công thức món ăn"),
            ("facebook", f"site:facebook.com reel {keyword} nấu ăn"),
            ("facebook", f"site:facebook.com {keyword} công thức nấu ăn"),
        ]
        results = []
        for source, items in self._parallel_search(queries):
            results.extend(
                self._build_results(items, source, keyword, tastes, servings))
        results = self._dedupe(results)
        results = self._rank(results, tastes)[:20]
        self._fill_images_parallel(results)  # mỗi kết quả LUÔN có ảnh
        note = ""
        if not results:
            note = ("Không tìm thấy reel công khai cho từ khóa này lúc này. "
                    "Instagram/Facebook thường chặn truy vấn tự động — "
                    "hãy thử từ khóa khác hoặc bấm 'Quét lại' sau.")
        return ScanBundle(results=results, note=note)

    def scan_topic(self, topic, source="all"):
        queries = []
        if source in ("all", "facebook"):
            queries.append(("facebook", f"site:facebook.com {topic} món ăn"))
            queries.append(("facebook", f"site:facebook.com {topic} công thức"))
        if source in ("all", "instagram"):
            queries.append(("instagram", f"site:instagram.com {topic} món ăn"))
            queries.append(("instagram", f"site:instagram.com {topic} reel nấu ăn"))
        if source in ("all", "news"):
            queries.append(("news", f"{topic} ẩm thực tin tức"))
        results = []
        for src, items in self._parallel_search(queries):
            results.extend(self._build_results(items, src, topic, [], ""))
        results = self._dedupe(results)[:20]
        self._fill_images_parallel(results)
        # Tin tức: tóm tắt cực ngắn từ đoạn trích
        for r in results:
            if r.source == "news":
                r.summary = (r.snippet[:90] + "…") if r.snippet else \
                    f"Tin về '{topic}' — mở link gốc để đọc."
        note = ""
        if not results:
            note = ("Chưa quét được nội dung công khai cho chủ đề này. "
                    "Thử từ khóa khác hoặc bấm 'Quét lại'.")
        return ScanBundle(results=results, note=note)
