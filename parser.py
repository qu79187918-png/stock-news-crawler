from stock_mapping import CATEGORY_KEYWORDS
from stock_universe import load_listed_stocks


def find_related_stocks(title: str, summary: str) -> list[dict[str, str]]:
    text = f"{title or ''} {summary or ''}"
    related = []
    seen_codes = set()

    for stock in load_listed_stocks():
        aliases = stock.get("aliases", [])
        if any(alias and alias in text for alias in aliases):
            code = str(stock.get("code", ""))
            if code in seen_codes:
                continue
            seen_codes.add(code)
            related.append(
                {
                    "name": str(stock.get("name", "")),
                    "code": code,
                    "industry": str(stock.get("industry", "")),
                }
            )

    return related


def classify_news(title: str, summary: str) -> list[str]:
    text = f"{title or ''} {summary or ''}"
    categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            categories.append(category)

    return categories


def enrich_news_item(news_item: dict) -> dict:
    title = news_item.get("title", "")
    summary = news_item.get("summary", "")

    news_item["related_stocks"] = find_related_stocks(title, summary)
    news_item["categories"] = classify_news(title, summary)
    return news_item
