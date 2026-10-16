#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tủ Lạnh Nấu Gì — backend Flask.

Chạy:  python backend/app.py        (mở http://127.0.0.1:5000)
Lưu trữ: JSON file trong backend/data/ (không cần database).
Quét reels/bài viết: qua ScannerAdapter (xem backend/scanners/), lazy —
chỉ quét khi user bấm tìm, kết quả cache theo từ khóa.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory, abort

from scanners import PublicWebScanner

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

FOODS_PATH = os.path.join(DATA_DIR, "foods.json")
RECIPES_PATH = os.path.join(DATA_DIR, "recipes.json")
FRIDGE_PATH = os.path.join(DATA_DIR, "fridge.json")
CACHE_PATH = os.path.join(DATA_DIR, "cache.json")
TOPICS_PATH = os.path.join(DATA_DIR, "topics.json")

app = Flask(__name__)
# Giữ nguyên tiếng Việt trong JSON (không \uXXXX)
app.json.ensure_ascii = False
app.config["JSON_AS_ASCII"] = False

scanner = PublicWebScanner(timeout=6, max_results=6)


# ---------- tiện ích JSON ----------
def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _cache_key(*parts):
    raw = "|".join(str(p).strip().lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_get(key):
    return _load(CACHE_PATH, {}).get(key)


def _cache_set(key, bundle_dict):
    cache = _load(CACHE_PATH, {})
    cache[key] = {"ts": _now_iso(), **bundle_dict}
    _save(CACHE_PATH, cache)


# ---------- trang chủ / file tĩnh ----------
@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    # Không để route tĩnh nuốt mất /api/*
    if filename.startswith("api/"):
        abort(404)
    return send_from_directory(FRONTEND_DIR, filename)


# ---------- tủ lạnh ----------
@app.get("/api/foods")
def api_foods():
    """Database nguyên liệu: {categories: [...], foods: [{id, name, category}]}"""
    return jsonify(_load(FOODS_PATH, {"categories": [], "foods": []}))


@app.get("/api/fridge")
def api_fridge_get():
    return jsonify(_load(FRIDGE_PATH, {"items": []}))


@app.post("/api/fridge")
def api_fridge_set():
    body = request.get_json(force=True, silent=True) or {}
    items = body.get("items") or []
    # Chỉ nhận tên có trong database (chống rác)
    valid = {f["name"] for f in _load(FOODS_PATH, {}).get("foods", [])}
    items = [i for i in items if i in valid]
    _save(FRIDGE_PATH, {"items": items, "updated_at": _now_iso()})
    return jsonify({"ok": True, "items": items})


# ---------- tìm món (quét reels, lazy + cache) ----------
@app.post("/api/search")
def api_search():
    body = request.get_json(force=True, silent=True) or {}
    keyword = (body.get("keyword") or "").strip()
    tastes = body.get("tastes") or []
    servings = (body.get("servings") or "").strip()
    rescan = bool(body.get("rescan"))
    if not keyword:
        return jsonify({"error": "Vui lòng nhập từ khóa món ăn."}), 400

    key = _cache_key("search", keyword, ",".join(sorted(tastes)), servings)
    if not rescan:
        hit = _cache_get(key)
        if hit:
            return jsonify({"cached": True,
                            "results": hit["results"],
                            "note": hit.get("note", "")})
    try:
        bundle = scanner.scan_reels(keyword, tastes=tastes, servings=servings)
    except Exception as exc:  # không bao giờ để scanner làm sập API
        bundle = {"results": [], "note": f"Lỗi khi quét: {exc}"}
    data = bundle.to_dict() if hasattr(bundle, "to_dict") else bundle
    # Không cache kết quả rỗng (tránh khóa nhầm khi bị chặn tạm thời)
    if data.get("results"):
        _cache_set(key, data)
    return jsonify({"cached": False, **data})


# ---------- gợi ý món từ tủ lạnh ----------
@app.get("/api/suggestions")
def api_suggestions():
    fridge = set(_load(FRIDGE_PATH, {}).get("items", []))
    recipes = _load(RECIPES_PATH, [])
    ready, near = [], []
    for r in recipes:
        ingredients = r.get("ingredients", [])
        have = [i for i in ingredients if i in fridge]
        missing = [i for i in ingredients if i not in fridge]
        card = {
            "id": r.get("id"), "name": r.get("name"),
            "description": r.get("description", ""),
            "tastes": r.get("tastes", []),
            "servings": r.get("servings", ""),
            "ingredients": ingredients,
            "have": have, "missing": missing,
            "steps": r.get("steps", []),
        }
        if not missing:
            ready.append(card)
        elif len(missing) <= 3:
            near.append(card)
    near.sort(key=lambda c: (-len(c["have"]), len(c["missing"])))
    return jsonify({"ready": ready, "near": near,
                    "fridge_count": len(fridge)})


# ---------- khám phá: chủ đề đã lưu ----------
@app.get("/api/explore/topics")
def api_topics_list():
    return jsonify({"topics": _load(TOPICS_PATH, [])})


@app.post("/api/explore/topics")
def api_topics_add():
    body = request.get_json(force=True, silent=True) or {}
    topic = (body.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Thiếu tên chủ đề."}), 400
    topics = _load(TOPICS_PATH, [])
    if not any(t["topic"].lower() == topic.lower() for t in topics):
        topics.append({"id": uuid.uuid4().hex[:8], "topic": topic,
                       "created_at": _now_iso()})
        _save(TOPICS_PATH, topics)
    return jsonify({"ok": True, "topics": topics})


@app.delete("/api/explore/topics/<tid>")
def api_topics_delete(tid):
    topics = [t for t in _load(TOPICS_PATH, []) if t["id"] != tid]
    _save(TOPICS_PATH, topics)
    return jsonify({"ok": True, "topics": topics})


@app.post("/api/explore/scan")
def api_explore_scan():
    body = request.get_json(force=True, silent=True) or {}
    topic = (body.get("topic") or "").strip()
    source = (body.get("source") or "all").strip()  # all|facebook|instagram|news
    rescan = bool(body.get("rescan"))
    if not topic:
        return jsonify({"error": "Thiếu chủ đề."}), 400
    if source not in ("all", "facebook", "instagram", "news"):
        source = "all"

    key = _cache_key("explore", topic, source)
    if not rescan:
        hit = _cache_get(key)
        if hit:
            return jsonify({"cached": True,
                            "results": hit["results"],
                            "note": hit.get("note", "")})
    try:
        bundle = scanner.scan_topic(topic, source=source)
    except Exception as exc:
        bundle = {"results": [], "note": f"Lỗi khi quét: {exc}"}
    data = bundle.to_dict() if hasattr(bundle, "to_dict") else bundle
    # Không cache kết quả rỗng (tránh khóa nhầm khi bị chặn tạm thời)
    if data.get("results"):
        _cache_set(key, data)
    return jsonify({"cached": False, **data})


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Tủ Lạnh Nấu Gì chạy tại: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
