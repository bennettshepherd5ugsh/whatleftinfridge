# -*- coding: utf-8 -*-
"""
Định nghĩa interface chung cho mọi scanner.

Muốn thêm nguồn quét mới (ví dụ: dùng API chính thức của nền tảng),
chỉ cần tạo class kế thừa ScannerAdapter và implement 2 method scan_reels
/ scan_topic, rồi đăng ký trong backend/app.py — không cần sửa code cũ.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict


@dataclass
class ScanResult:
    """Một kết quả quét duy nhất (reel / bài viết / tin tức)."""
    title: str                 # tên món / tiêu đề bài viết
    url: str                   # link gốc
    source: str                # "instagram" | "facebook" | "news"
    image_url: str = ""        # ảnh món ăn (thumbnail); "" nếu không lấy được
    summary: str = ""          # tóm tắt NGẮN do app tự tạo (vị + nguyên liệu),
                               # KHÔNG phải caption gốc của reel
    matched_in: list = field(default_factory=list)  # ["title"] và/hoặc ["caption"]
    snippet: str = ""          # đoạn trích tìm được (để đối chiếu keyword)
    taste_tags: list = field(default_factory=list)  # khẩu vị đoán từ tiêu đề/snippet

    def to_dict(self):
        return asdict(self)


@dataclass
class ScanBundle:
    """Kết quả của một lần quét: danh sách + ghi chú cho user."""
    results: list = field(default_factory=list)  # list[ScanResult]
    note: str = ""  # giải thích khi trống / lỗi (hiển thị thân thiện cho user)

    def to_dict(self):
        return {"results": [r.to_dict() for r in self.results], "note": self.note}


class ScannerAdapter(ABC):
    """Interface mọi scanner phải tuân thủ."""

    name = "base"

    @abstractmethod
    def scan_reels(self, keyword, tastes=None, servings=""):
        """Tìm reels nấu ăn công khai theo từ khóa món ăn.

        Trả về ScanBundle. tastes: list khẩu vị user chọn (để ưu tiên
        sắp xếp). servings: "1"/"2"/"3-4"/"5+".
        """
        raise NotImplementedError

    @abstractmethod
    def scan_topic(self, topic, source="all"):
        """Quét chủ đề ẩm thực công khai.

        source: "all" | "facebook" | "instagram" | "news".
        Trả về ScanBundle.
        """
        raise NotImplementedError
