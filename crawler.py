import html
import logging
import os
import re
import time
import warnings
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from requests.exceptions import SSLError

requests.packages.urllib3.disable_warnings()
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


LOGGER = logging.getLogger(__name__)

RSS_SOURCES = [
    {
        "name": "Yahoo \u80a1\u5e02",
        "url": "https://tw.stock.yahoo.com/rss?category=tw-market",
        "category": "台股",
    },
]

CNYES_API_URL = "https://api.cnyes.com/media/api/v1/newslist/category/{slug}"
CNYES_CATEGORIES = [
    {"slug": "tw_stock", "name": "鉅亨台股"},
    {"slug": "tw_premarket", "name": "鉅亨台股盤前"},
    {"slug": "tw_quo", "name": "鉅亨台股盤勢"},
    {"slug": "tw_bull", "name": "鉅亨台股公告"},
    {"slug": "stock_report", "name": "鉅亨專家觀點"},
    {"slug": "tech", "name": "鉅亨科技"},
    {"slug": "headline", "name": "鉅亨頭條"},
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}
_SSL_FALLBACK_NOTIFIED = False
FETCH_ARTICLE_DETAILS = os.environ.get("FETCH_ARTICLE_DETAILS", "false").lower() == "true"


def fetch_latest_news(limit: int = 100) -> list[dict]:
    news_items = []

    for source in RSS_SOURCES:
        try:
            rss_items = _fetch_rss_items(source)
            news_items.extend(rss_items)
        except Exception as exc:
            LOGGER.warning("Failed to fetch %s RSS: %s", source["name"], exc)

    for category in CNYES_CATEGORIES:
        try:
            news_items.extend(_fetch_cnyes_category(category, per_category_limit=30))
        except Exception as exc:
            LOGGER.warning("Failed to fetch %s API: %s", category["name"], exc)

    deduped_items = _deduplicate_by_link(news_items)
    deduped_items.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
    return _limit_by_source(deduped_items, limit)


def _fetch_rss_items(source: dict) -> list[dict]:
    response = _get_url(source["url"])
    response.raise_for_status()

    root = ET.fromstring(response.content)
    channel_items = [
        element
        for element in root.iter()
        if _local_name(element.tag) in {"item", "entry"}
    ]
    results = []

    for item in channel_items:
        try:
            title = _get_text(item, "title")
            link = _get_link(item)
            published_at = _normalize_time(
                _get_text(item, "pubDate")
                or _get_text(item, "published")
                or _get_text(item, "updated")
            )
            rss_summary = _clean_text(_get_text(item, "description"))
            article_summary = _fetch_article_summary(link) if FETCH_ARTICLE_DETAILS else ""

            results.append(
                {
                    "title": title,
                    "time": published_at,
                    "timestamp": _time_to_timestamp(published_at),
                    "source": source["name"],
                    "source_category": source.get("category", ""),
                    "link": link,
                    "summary": article_summary or rss_summary,
                }
            )
        except Exception as exc:
            LOGGER.warning("Failed to parse one news item: %s", exc)
            continue

    return results


def _fetch_cnyes_category(category: dict, per_category_limit: int) -> list[dict]:
    params = {
        "page": 1,
        "limit": per_category_limit,
        "startAt": int(time.time()) - 86400 * 45,
        "endAt": int(time.time()),
    }
    url = CNYES_API_URL.format(slug=category["slug"])
    response = _get_url(url, params=params)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("items", {}).get("data", [])
    results = []

    for row in rows:
        try:
            news_id = row.get("newsId")
            title = _clean_text(row.get("title", ""))
            summary = _clean_text(row.get("content", ""))
            published_at = _timestamp_to_iso(row.get("publishAt"))
            link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else ""
            source_category = _cnyes_category_name(row, category["name"])

            results.append(
                {
                    "title": title,
                    "time": published_at,
                    "timestamp": int(row.get("publishAt") or 0),
                    "source": "鉅亨網",
                    "source_category": source_category,
                    "link": link,
                    "summary": summary,
                }
            )
        except Exception as exc:
            LOGGER.warning("Failed to parse one Cnyes news item: %s", exc)
            continue

    return results


def _fetch_article_summary(url: str) -> str:
    if not url:
        return ""

    try:
        response = _get_url(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        meta_description = soup.find("meta", attrs={"name": "description"})
        if meta_description and meta_description.get("content"):
            return _clean_text(meta_description["content"])

        paragraphs = [
            _clean_text(paragraph.get_text(" "))
            for paragraph in soup.find_all("p")
        ]
        paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) >= 20]
        return _truncate_text(" ".join(paragraphs), max_length=220)
    except Exception as exc:
        LOGGER.warning("Failed to fetch article summary: %s, url=%s", exc, url)
        return ""


def _get_url(url: str, params: dict | None = None) -> requests.Response:
    global _SSL_FALLBACK_NOTIFIED

    try:
        return requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=15)
    except SSLError:
        if not _SSL_FALLBACK_NOTIFIED:
            LOGGER.warning("SSL verify failed. Retrying public news requests without certificate verification.")
            _SSL_FALLBACK_NOTIFIED = True
        return requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=15, verify=False)


def _get_text(item: ET.Element, tag_name: str) -> str:
    element = _find_child(item, tag_name)
    if element is None:
        return ""
    return _clean_text("".join(element.itertext()))


def _get_link(item: ET.Element) -> str:
    link = _find_child(item, "link")
    if link is None:
        return ""
    return _clean_text(link.attrib.get("href") or "".join(link.itertext()))


def _find_child(item: ET.Element, tag_name: str) -> ET.Element | None:
    for child in item:
        if _local_name(child.tag) == tag_name:
            return child
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_time(value: str) -> str:
    if not value:
        return ""

    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value


def _time_to_timestamp(value: str) -> int:
    if not value:
        return 0
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        try:
            return int(value)
        except Exception:
            return 0


def _timestamp_to_iso(value) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(int(value)))
    except Exception:
        return ""


def _cnyes_category_name(row: dict, fallback: str) -> str:
    categories = row.get("category") or []
    if categories and isinstance(categories, list):
        names = [item.get("name", "") for item in categories if item.get("name")]
        if names:
            return "、".join(names)
    if row.get("categoryName"):
        return str(row["categoryName"])
    return fallback


def _clean_text(value: str) -> str:
    text = html.unescape(value or "")
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length].rstrip() + "..."


def _deduplicate_by_link(news_items: list[dict]) -> list[dict]:
    seen_links = set()
    deduped = []

    for item in news_items:
        link = item.get("link", "")
        if link in seen_links:
            continue
        seen_links.add(link)
        deduped.append(item)

    return deduped


def _limit_by_source(news_items: list[dict], limit: int) -> list[dict]:
    max_per_source = max(20, int(limit * 0.8))
    source_counts = {}
    selected = []
    skipped = []

    for item in news_items:
        source = item.get("source", "")
        count = source_counts.get(source, 0)
        if count < max_per_source:
            selected.append(item)
            source_counts[source] = count + 1
        else:
            skipped.append(item)

        if len(selected) >= limit:
            return selected

    for item in skipped:
        selected.append(item)
        if len(selected) >= limit:
            break

    return selected
