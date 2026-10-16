# Tủ Lạnh Nấu Gì (WhatLeftInFridge)

Web app nấu ăn tại nhà, giao diện tiếng Việt: xem còn gì trong tủ lạnh,
tìm món muốn nấu, xem reels liên quan, và nhận gợi ý công thức nấu được
từ nguyên liệu có sẵn.

## Chạy app

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python backend/app.py
```

Mở trình duyệt: **http://127.0.0.1:5000**

Không cần build, không cần database — dữ liệu lưu trong các file JSON
ở `backend/data/`.

## Tính năng

- **🧊 Tủ lạnh**: database ~78 nguyên liệu Việt Nam theo nhóm
  (thịt, hải sản, rau củ quả, gia vị, trứng & sữa, đồ khô…).
  Gõ để lọc nhanh, chạm để chọn — không cần gõ tay từng món.
- **🔍 Tìm món**: nhập từ khóa + tick chọn khẩu vị
  (mặn, ngọt, cay, chua, béo ngậy, thanh đạm, chay) và số người ăn
  (1 / 2 / 3–4 / 5+ người). Kết quả được ưu tiên theo lựa chọn.
- **Thẻ reel**: mỗi kết quả có ảnh món ăn (chọn bằng mắt), tên món,
  tóm tắt ngắn do app tự tạo (hương vị + nguyên liệu — KHÔNG copy
  caption gốc), nhãn cho biết từ khóa khớp ở **tiêu đề** hay **phụ đề**,
  và link reel gốc.
- **Lazy scanning**: chỉ quét khi bạn bấm Tìm. Kết quả được cache theo
  từ khóa (+ khẩu vị + số người ăn); lần sau mở ra thấy ngay, có nhãn
  "Kết quả đã lưu" và nút **↻ Quét lại** để lấy mới.
- **💡 Gợi ý từ tủ**: gợi ý món từ database công thức (~20 món Việt),
  xếp hạng theo số nguyên liệu đã có trong tủ lạnh:
  "Món đủ nguyên liệu" và "Món gần đủ nguyên liệu" (hiện đồ còn thiếu).
- **🌍 Khám phá**: quét chủ đề ẩm thực công khai trên Facebook,
  Instagram và tin tức; lọc theo nguồn; lưu / quét lại / xóa chủ đề.
  Chỉ quét khi bạn bấm nút, không chạy nền.

## Scanner hoạt động thế nào (và giới hạn)

`backend/scanners/` định nghĩa interface `ScannerAdapter`
(`base.py`): mọi nguồn quét mới chỉ cần implement
`scan_reels()` và `scan_topic()`.

Bản v1 (`public_web.py`) tìm nội dung công khai qua web search
(DuckDuckGo, không cần đăng nhập hay API key), với 4 truy vấn chạy
**song song** (ThreadPoolExecutor) mỗi lần tìm món — mục tiêu 15–20 kết
quả, mỗi kết quả luôn có ảnh. Vẫn lazy: chỉ quét khi user bấm tìm,
kết quả cache theo từ khóa ở tầng `app.py`. Các bước:
1. Đối chiếu từng từ của từ khóa với tiêu đề và đoạn trích
   (đóng vai "phụ đề/caption") của kết quả.
2. Lấy ảnh `og:image` của các trang gốc **song song** (timeout ngắn);
   trang nào không lấy được thì dùng ảnh placeholder do app tự vẽ —
   **mỗi kết quả luôn có ảnh** để chọn bằng mắt.
3. Tóm tắt cực ngắn do app tự tạo ("Vị mặn, cay · 2 người ·
   Nguyên liệu: tôm + gia vị cơ bản") — nhiều hình, ít chữ.

**Giới hạn đã biết:**
- Instagram/Facebook chặn truy vấn tự động khá mạnh — có những lúc
  kết quả ít hoặc trống. App sẽ báo rõ thay vì báo lỗi khó hiểu.
- Không bao giờ thử đăng nhập, không cào dữ liệu hàng loạt,
  không vượt paywall/login-wall.
- Muốn nguồn xịn hơn sau này: cắm API chính thức của nền tảng vào
  một adapter mới là xong, không cần sửa code cũ.

## Cấu trúc project

```
whatleftinfridge/
├── README.md
├── requirements.txt            # flask, requests
├── backend/
│   ├── app.py                  # Flask app + toàn bộ API
│   ├── scanners/
│   │   ├── __init__.py
│   │   ├── base.py             # interface ScannerAdapter / ScanResult
│   │   └── public_web.py       # scanner v1: public web search (best-effort)
│   └── data/
│       ├── foods.json          # database nguyên liệu (~78 món)
│       ├── recipes.json        # database công thức (~20 món Việt)
│       ├── fridge.json         # tủ lạnh của bạn (tự tạo khi lưu)
│       ├── cache.json          # cache kết quả quét (tự tạo)
│       └── topics.json         # chủ đề khám phá đã lưu (tự tạo)
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js                  # vanilla JS, không build step
```

## API tóm tắt

| Method | Endpoint | Chức năng |
|---|---|---|
| GET | `/api/foods` | database nguyên liệu |
| GET/POST | `/api/fridge` | đọc / lưu tủ lạnh |
| POST | `/api/search` | tìm reels (`keyword, tastes, servings, rescan`) |
| GET | `/api/suggestions` | gợi ý món theo tủ lạnh |
| GET/POST | `/api/explore/topics` | danh sách / lưu chủ đề |
| DELETE | `/api/explore/topics/<id>` | xóa chủ đề |
| POST | `/api/explore/scan` | quét chủ đề (`topic, source, rescan`) |
