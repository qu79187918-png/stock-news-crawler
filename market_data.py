import datetime as dt
import logging
from functools import lru_cache

import requests


LOGGER = logging.getLogger(__name__)
TWSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


def build_stock_market_data(code: str) -> dict:
    return {
        "price": find_twse_row("price", code),
        "institutional": find_twse_row("institutional", code),
        "valuation": find_twse_row("valuation", code),
        "margin": find_twse_row("margin", code),
        "large_small_orders": {
            "status": "資料源待接入",
            "note": "公開免費資料未穩定提供個股大小單拆分；目前先以法人、融資融券與成交量替代觀察資金方向。",
        },
    }


def find_twse_row(kind: str, code: str) -> dict:
    for date in recent_dates(days=10):
        payload = fetch_twse_payload(kind, date)
        row = extract_row(payload, code)
        if row:
            row["date"] = date
            row["status"] = "ok"
            return row

    return {"status": "無資料", "date": "", "note": "近 10 日未取得公開資料，可能遇到假日、休市或資料格式異動。"}


@lru_cache(maxsize=64)
def fetch_twse_payload(kind: str, date: str) -> dict:
    urls = {
        "price": ("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX", {"date": date, "type": "ALLBUT0999", "response": "json"}),
        "institutional": ("https://www.twse.com.tw/rwd/zh/fund/T86", {"date": date, "selectType": "ALLBUT0999", "response": "json"}),
        "valuation": ("https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d", {"date": date, "response": "json"}),
        "margin": ("https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN", {"date": date, "selectType": "All", "response": "json"}),
    }
    url, params = urls[kind]

    try:
        response = requests.get(url, params=params, headers=TWSE_HEADERS, timeout=15, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        LOGGER.warning("Failed to fetch TWSE %s data for %s: %s", kind, date, exc)
        return {}


def extract_row(payload: dict, code: str) -> dict:
    candidates = []
    if isinstance(payload.get("data"), list):
        candidates.append((payload.get("fields", []), payload.get("data", [])))

    for table in payload.get("tables", []) or []:
        candidates.append((table.get("fields", []), table.get("data", [])))

    for fields, rows in candidates:
        if not fields or not rows:
            continue
        for row in rows:
            if not row:
                continue
            normalized = dict(zip(fields, row))
            if str(normalized.get("證券代號", "")).strip() == code:
                return simplify_row(normalized)

    return {}


def simplify_row(row: dict) -> dict:
    wanted = [
        "證券代號",
        "證券名稱",
        "收盤價",
        "漲跌價差",
        "成交股數",
        "成交金額",
        "外資買賣超股數",
        "投信買賣超股數",
        "自營商買賣超股數",
        "三大法人買賣超股數",
        "本益比",
        "殖利率(%)",
        "股價淨值比",
        "融資買進",
        "融資賣出",
        "融資餘額",
        "融券買進",
        "融券賣出",
        "融券餘額",
    ]
    return {key: clean_value(row.get(key, "")) for key in wanted if key in row}


def clean_value(value) -> str:
    return str(value).replace(",", "").strip()


def recent_dates(days: int) -> list[str]:
    today = dt.date.today()
    return [(today - dt.timedelta(days=offset)).strftime("%Y%m%d") for offset in range(days)]
