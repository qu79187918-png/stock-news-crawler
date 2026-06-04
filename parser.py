from stock_mapping import CATEGORY_KEYWORDS, STOCK_MAPPING


def find_related_stocks(title: str, summary: str) -> list[dict[str, str]]:
    text = f"{title or ''} {summary or ''}"
    related = []

    for company_name, stock_code in STOCK_MAPPING.items():
        if company_name in text:
            related.append({"name": company_name, "code": stock_code})

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
