import argparse
import csv
import json
import logging
from pathlib import Path

from crawler import fetch_latest_news
from parser import enrich_news_item


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CSV_PATH = OUTPUT_DIR / "news.csv"
JSON_PATH = OUTPUT_DIR / "news.json"


def main() -> None:
    args = parse_args()
    setup_logging()

    OUTPUT_DIR.mkdir(exist_ok=True)

    news_items = fetch_latest_news(limit=args.limit)
    enriched_items = [enrich_news_item(item) for item in news_items]

    write_json(enriched_items, JSON_PATH)
    write_csv(enriched_items, CSV_PATH)

    print(f"Done. Exported {len(enriched_items)} news items.")
    print(f"CSV: {CSV_PATH}")
    print(f"JSON: {JSON_PATH}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple Taiwan stock news crawler")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of news items")
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def write_json(news_items: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(news_items, file, ensure_ascii=False, indent=2)


def write_csv(news_items: list[dict], path: Path) -> None:
    fieldnames = ["title", "time", "source", "link", "summary", "related_stocks", "categories"]

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for item in news_items:
            row = item.copy()
            row["related_stocks"] = json.dumps(row.get("related_stocks", []), ensure_ascii=False)
            row["categories"] = json.dumps(row.get("categories", []), ensure_ascii=False)
            writer.writerow(row)


if __name__ == "__main__":
    main()
