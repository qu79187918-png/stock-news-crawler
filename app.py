import json
import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from crawler import fetch_latest_news
from main import CSV_PATH, write_csv
from parser import enrich_news_item


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
JSON_PATH = OUTPUT_DIR / "news.json"

app = Flask(__name__)


def load_news() -> list[dict]:
    if not JSON_PATH.exists():
        return []

    try:
        with JSON_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_news(news_items: list[dict]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with JSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(news_items, file, ensure_ascii=False, indent=2)
    write_csv(news_items, CSV_PATH)


def refresh_news(limit: int = 30) -> list[dict]:
    news_items = fetch_latest_news(limit=limit)
    enriched_items = [enrich_news_item(item) for item in news_items]
    save_news(enriched_items)
    return enriched_items


def filter_news(news_items: list[dict], keyword: str, category: str) -> list[dict]:
    keyword = keyword.strip().lower()
    category = category.strip()

    results = []
    for item in news_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        related_stocks = item.get("related_stocks", [])
        categories = item.get("categories", [])
        searchable_text = " ".join(
            [
                title,
                summary,
                " ".join(stock.get("name", "") for stock in related_stocks),
                " ".join(stock.get("code", "") for stock in related_stocks),
            ]
        ).lower()

        if keyword and keyword not in searchable_text:
            continue
        if category and category not in categories:
            continue

        results.append(item)

    return results


@app.route("/")
def index():
    keyword = request.args.get("q", "")
    category = request.args.get("category", "")
    news_items = load_news()
    if not news_items:
        news_items = refresh_news(limit=30)
    filtered_items = filter_news(news_items, keyword, category)

    all_categories = sorted(
        {category for item in news_items for category in item.get("categories", [])}
    )

    return render_template(
        "index.html",
        news_items=filtered_items,
        total_count=len(news_items),
        keyword=keyword,
        selected_category=category,
        categories=all_categories,
    )


@app.route("/refresh")
def refresh():
    limit = request.args.get("limit", default=30, type=int)
    refresh_news(limit=limit)
    return redirect(url_for("index"))


@app.route("/api/news")
def api_news():
    keyword = request.args.get("q", "")
    category = request.args.get("category", "")
    news_items = filter_news(load_news(), keyword, category)
    return jsonify(news_items)


@app.route("/download/csv")
def download_csv():
    if not JSON_PATH.exists():
        refresh_news(limit=30)
    return send_file(CSV_PATH, as_attachment=True, download_name="stock_news.csv")


@app.route("/download/json")
def download_json():
    if not JSON_PATH.exists():
        refresh_news(limit=30)
    return send_file(JSON_PATH, as_attachment=True, download_name="stock_news.json")


@app.route("/health")
def health():
    return {"status": "ok", "items": len(load_news())}


if __name__ == "__main__":
    if not load_news():
        refresh_news(limit=30)

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
