import json
from pathlib import Path

from stock_universe import load_listed_stocks


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
FAVORITES_PATH = OUTPUT_DIR / "favorites.json"


def load_favorites() -> list[dict]:
    if not FAVORITES_PATH.exists():
        return []

    try:
        with FAVORITES_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return []


def save_favorites(favorites: list[dict]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with FAVORITES_PATH.open("w", encoding="utf-8") as file:
        json.dump(favorites, file, ensure_ascii=False, indent=2)


def find_stock(query: str) -> dict | None:
    query = query.strip()
    if not query:
        return None

    stocks = load_listed_stocks()
    for stock in stocks:
        if query == stock.get("code") or query == stock.get("name"):
            return stock

    for stock in stocks:
        aliases = stock.get("aliases", [])
        if any(query in alias for alias in aliases):
            return stock

    return None


def add_favorite(query: str) -> dict | None:
    stock = find_stock(query)
    if not stock:
        return None

    favorites = load_favorites()
    if any(item.get("code") == stock.get("code") for item in favorites):
        return stock

    favorites.append(
        {
            "code": stock.get("code", ""),
            "name": stock.get("name", ""),
            "company_name": stock.get("company_name", ""),
            "industry": stock.get("industry", ""),
        }
    )
    save_favorites(favorites)
    return stock


def remove_favorite(code: str) -> None:
    favorites = [item for item in load_favorites() if item.get("code") != code]
    save_favorites(favorites)
