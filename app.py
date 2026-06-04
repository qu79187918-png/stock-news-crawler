import json
import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from analyst import build_favorite_reports, build_market_brief, build_stock_radar
from crawler import fetch_latest_news
from favorites import add_favorite, load_favorites, remove_favorite
from main import CSV_PATH, write_csv
from parser import enrich_news_item
from stock_universe import load_listed_stocks, refresh_listed_stocks


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


def refresh_news(limit: int = 100) -> list[dict]:
    news_items = fetch_latest_news(limit=limit)
    enriched_items = [enrich_news_item(item) for item in news_items]
    save_news(enriched_items)
    return enriched_items


def filter_news(news_items: list[dict], keyword: str, category: str, source: str, news_type: str) -> list[dict]:
    keyword = keyword.strip().lower()
    category = category.strip()
    source = source.strip()
    news_type = news_type.strip()

    results = []
    for item in news_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        related_stocks = item.get("related_stocks", [])
        categories = item.get("categories", [])
        news_types = item.get("news_types", [])
        searchable_text = " ".join(
            [
                title,
                summary,
                item.get("source", ""),
                item.get("source_category", ""),
                " ".join(news_types),
                " ".join(stock.get("name", "") for stock in related_stocks),
                " ".join(stock.get("code", "") for stock in related_stocks),
            ]
        ).lower()

        if keyword and keyword not in searchable_text:
            continue
        if category and category not in categories:
            continue
        if source and source != item.get("source", ""):
            continue
        if news_type and news_type not in news_types:
            continue

        results.append(item)

    return results


@app.route("/")
def index():
    keyword = request.args.get("q", "")
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    news_type = request.args.get("news_type", "")
    news_items = load_news()
    if not news_items:
        news_items = refresh_news(limit=100)
    filtered_items = filter_news(news_items, keyword, category, source, news_type)

    all_categories = sorted(
        {category for item in news_items for category in item.get("categories", [])}
    )
    all_sources = sorted({item.get("source", "") for item in news_items if item.get("source")})
    all_news_types = sorted({news_type for item in news_items for news_type in item.get("news_types", [])})
    market_brief = build_market_brief(news_items)
    stock_radar = build_stock_radar(news_items)
    favorites = load_favorites()
    favorite_reports = build_favorite_reports(favorites, news_items)

    return render_template(
        "index.html",
        news_items=filtered_items,
        total_count=len(news_items),
        keyword=keyword,
        selected_category=category,
        selected_source=source,
        selected_news_type=news_type,
        categories=all_categories,
        sources=all_sources,
        news_types=all_news_types,
        market_brief=market_brief,
        stock_radar=stock_radar[:10],
        stock_count=len(load_listed_stocks()),
        favorites=favorites,
        favorite_reports=favorite_reports,
    )


@app.route("/refresh")
def refresh():
    limit = request.args.get("limit", default=100, type=int)
    refresh_news(limit=limit)
    return redirect(url_for("index"))


@app.route("/refresh-stocks")
def refresh_stocks():
    refresh_listed_stocks()
    return redirect(url_for("index"))


@app.route("/favorites", methods=["POST"])
def add_favorite_route():
    query = request.form.get("stock", "")
    add_favorite(query)
    return redirect(url_for("index"))


@app.route("/favorites/remove/<code>", methods=["POST"])
def remove_favorite_route(code: str):
    remove_favorite(code)
    return redirect(url_for("index"))


@app.route("/api/news")
def api_news():
    keyword = request.args.get("q", "")
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    news_type = request.args.get("news_type", "")
    news_items = filter_news(load_news(), keyword, category, source, news_type)
    return jsonify(news_items)


@app.route("/api/analysis")
def api_analysis():
    news_items = load_news()
    return jsonify(
        {
            "market_brief": build_market_brief(news_items),
            "stock_radar": build_stock_radar(news_items),
            "stock_count": len(load_listed_stocks()),
        }
    )


@app.route("/api/favorites")
def api_favorites():
    news_items = load_news()
    favorites = load_favorites()
    return jsonify(
        {
            "favorites": favorites,
            "reports": build_favorite_reports(favorites, news_items),
        }
    )


@app.route("/download/csv")
def download_csv():
    if not JSON_PATH.exists():
        refresh_news(limit=100)
    return send_file(CSV_PATH, as_attachment=True, download_name="stock_news.csv")


@app.route("/download/json")
def download_json():
    if not JSON_PATH.exists():
        refresh_news(limit=100)
    return send_file(JSON_PATH, as_attachment=True, download_name="stock_news.json")


@app.route("/health")
def health():
    return {"status": "ok", "items": len(load_news()), "stocks": len(load_listed_stocks())}


if __name__ == "__main__":
    if not load_news():
        refresh_news(limit=100)

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
