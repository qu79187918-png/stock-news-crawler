import csv
import io
import json
import logging
from functools import lru_cache
from pathlib import Path

import requests

from stock_mapping import STOCK_MAPPING


LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LISTED_STOCKS_PATH = OUTPUT_DIR / "listed_stocks.json"
LISTED_COMPANIES_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
INDUSTRY_MAPPING = {
    "01": "水泥工業",
    "02": "食品工業",
    "03": "塑膠工業",
    "04": "紡織纖維",
    "05": "電機機械",
    "06": "電器電纜",
    "07": "化學生技醫療",
    "08": "玻璃陶瓷",
    "09": "造紙工業",
    "10": "鋼鐵工業",
    "11": "橡膠工業",
    "12": "汽車工業",
    "13": "電子工業",
    "14": "建材營造",
    "15": "航運業",
    "16": "觀光餐旅",
    "17": "金融保險",
    "18": "貿易百貨",
    "20": "其他",
    "21": "化學工業",
    "22": "生技醫療",
    "23": "油電燃氣",
    "24": "半導體業",
    "25": "電腦及週邊",
    "26": "光電業",
    "27": "通信網路",
    "28": "電子零組件",
    "29": "電子通路",
    "30": "資訊服務",
    "31": "其他電子",
    "32": "文化創意",
    "33": "農業科技",
    "34": "電子商務",
    "35": "綠能環保",
    "36": "數位雲端",
    "37": "運動休閒",
    "38": "居家生活",
}


@lru_cache(maxsize=1)
def load_listed_stocks() -> list[dict[str, str | list[str]]]:
    cached = _load_cached_stocks()
    if cached:
        return cached

    try:
        stocks = fetch_listed_stocks()
        if stocks:
            _save_cached_stocks(stocks)
            return stocks
    except Exception as exc:
        LOGGER.warning("Failed to load listed stocks from TWSE open data: %s", exc)

    return fallback_stocks()


def refresh_listed_stocks() -> list[dict[str, str | list[str]]]:
    load_listed_stocks.cache_clear()
    try:
        stocks = fetch_listed_stocks()
        if stocks:
            _save_cached_stocks(stocks)
            load_listed_stocks.cache_clear()
            return stocks
    except Exception as exc:
        LOGGER.warning("Failed to refresh listed stocks: %s", exc)

    return load_listed_stocks()


def fetch_listed_stocks() -> list[dict[str, str | list[str]]]:
    response = requests.get(LISTED_COMPANIES_URL, timeout=20, verify=False)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="replace")
    rows = csv.DictReader(io.StringIO(text))

    stocks = []
    for row in rows:
        code = (row.get("公司代號") or "").strip()
        company_name = (row.get("公司名稱") or "").strip()
        short_name = (row.get("公司簡稱") or "").strip()
        industry = (row.get("產業別") or "").strip()
        industry_name = INDUSTRY_MAPPING.get(industry, industry)

        if not code or not short_name:
            continue

        aliases = sorted(
            {
                alias
                for alias in [short_name, company_name]
                if alias and len(alias) >= 2
            },
            key=len,
            reverse=True,
        )
        stocks.append(
            {
                "code": code,
                "name": short_name,
                "company_name": company_name,
                "industry": industry_name,
                "aliases": aliases,
            }
        )

    return stocks


def fallback_stocks() -> list[dict[str, str | list[str]]]:
    return [
        {
            "code": code,
            "name": name,
            "company_name": name,
            "industry": "",
            "aliases": [name],
        }
        for name, code in STOCK_MAPPING.items()
    ]


def _load_cached_stocks() -> list[dict[str, str | list[str]]]:
    if not LISTED_STOCKS_PATH.exists():
        return []

    try:
        with LISTED_STOCKS_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return []


def _save_cached_stocks(stocks: list[dict[str, str | list[str]]]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with LISTED_STOCKS_PATH.open("w", encoding="utf-8") as file:
        json.dump(stocks, file, ensure_ascii=False, indent=2)
