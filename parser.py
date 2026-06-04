from stock_mapping import CATEGORY_KEYWORDS
from stock_universe import load_listed_stocks


NEWS_TYPE_KEYWORDS = {
    "盤勢": ["盤中", "盤後", "開盤", "收盤", "台股大盤", "加權指數", "漲點", "跌點"],
    "營收": ["營收", "月增", "年增", "年減", "業績"],
    "財報": ["EPS", "獲利", "毛利率", "淨利", "財報", "每股盈餘"],
    "法說": ["法說", "展望", "法人說明會"],
    "外資": ["外資", "投信", "自營商", "三大法人", "買超", "賣超"],
    "產品": ["新品", "量產", "出貨", "訂單", "供應鏈", "客製化", "晶片"],
    "公告": ["公告", "股東會", "除息", "除權", "增資", "處置"],
    "國際": ["美股", "日股", "韓股", "美元", "聯準會", "Fed", "NVIDIA", "輝達"],
}


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


def classify_news_type(title: str, summary: str) -> list[str]:
    text = f"{title or ''} {summary or ''}"
    types = []

    for news_type, keywords in NEWS_TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            types.append(news_type)

    return types or ["一般新聞"]


def enrich_news_item(news_item: dict) -> dict:
    title = news_item.get("title", "")
    summary = news_item.get("summary", "")

    news_item["related_stocks"] = find_related_stocks(title, summary)
    news_item["categories"] = classify_news(title, summary)
    news_item["news_types"] = classify_news_type(title, summary)
    return news_item
