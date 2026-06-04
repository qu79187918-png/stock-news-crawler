import html
import logging
import re
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
    },
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}
_SSL_FALLBACK_NOTIFIED = False


def fetch_latest_news(limit: int = 20) -> list[dict]:
    news_items = []

    for source in RSS_SOURCES:
        try:
            rss_items = _fetch_rss_items(source)
            news_items.extend(rss_items)
        except Exception as exc:
            LOGGER.warning("Failed to fetch %s RSS: %s", source["name"], exc)

    deduped_items = _deduplicate_by_link(news_items)
    return deduped_items[:limit]


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
            article_summary = _fetch_article_summary(link)

            results.append(
                {
                    "title": title,
                    "time": published_at,
                    "source": source["name"],
                    "link": link,
                    "summary": article_summary or rss_summary,
                }
            )
        except Exception as exc:
            LOGGER.warning("Failed to parse one news item: %s", exc)
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


def _get_url(url: str) -> requests.Response:
    global _SSL_FALLBACK_NOTIFIED

    try:
        return requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    except SSLError:
        if not _SSL_FALLBACK_NOTIFIED:
            LOGGER.warning("SSL verify failed. Retrying public news requests without certificate verification.")
            _SSL_FALLBACK_NOTIFIED = True
        return requests.get(url, headers=REQUEST_HEADERS, timeout=15, verify=False)


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
