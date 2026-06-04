from collections import Counter, defaultdict


POSITIVE_KEYWORDS = [
    "大漲",
    "創高",
    "新高",
    "看好",
    "利多",
    "成長",
    "旺",
    "強攻",
    "買超",
    "目標價",
]

NEGATIVE_KEYWORDS = [
    "大跌",
    "重挫",
    "利空",
    "衰退",
    "賣超",
    "下修",
    "虧損",
    "警告",
    "崩盤",
    "處置",
]


def build_market_brief(news_items: list[dict]) -> dict:
    category_counter = Counter()
    stock_counter = Counter()
    industry_counter = Counter()
    sentiment_points = 0

    for item in news_items:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        sentiment_points += score_text(text)

        for category in item.get("categories", []):
            category_counter[category] += 1

        for stock in item.get("related_stocks", []):
            stock_counter[(stock.get("code", ""), stock.get("name", ""))] += 1
            if stock.get("industry"):
                industry_counter[stock["industry"]] += 1

    market_view = "觀望"
    if sentiment_points >= 3:
        market_view = "偏多"
    elif sentiment_points <= -3:
        market_view = "偏空"

    top_categories = [name for name, _ in category_counter.most_common(3)]
    top_stocks = [
        {"code": code, "name": name, "mentions": mentions}
        for (code, name), mentions in stock_counter.most_common(5)
    ]

    return {
        "market_view": market_view,
        "sentiment_score": sentiment_points,
        "top_categories": top_categories,
        "top_industries": [name for name, _ in industry_counter.most_common(3)],
        "top_stocks": top_stocks,
        "commentary": make_commentary(market_view, top_categories, top_stocks),
    }


def build_stock_radar(news_items: list[dict]) -> list[dict]:
    stats = defaultdict(lambda: {"mentions": 0, "score": 0, "industries": Counter(), "latest_news": []})

    for item in news_items:
        item_score = score_text(f"{item.get('title', '')} {item.get('summary', '')}")
        for stock in item.get("related_stocks", []):
            code = stock.get("code", "")
            name = stock.get("name", "")
            key = (code, name)
            stats[key]["mentions"] += 1
            stats[key]["score"] += item_score
            if stock.get("industry"):
                stats[key]["industries"][stock["industry"]] += 1
            if len(stats[key]["latest_news"]) < 3:
                stats[key]["latest_news"].append(
                    {
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "time": item.get("time", ""),
                    }
                )

    radar = []
    for (code, name), data in stats.items():
        view = "觀望"
        if data["score"] > 0:
            view = "偏多觀察"
        elif data["score"] < 0:
            view = "偏空觀察"

        radar.append(
            {
                "code": code,
                "name": name,
                "mentions": data["mentions"],
                "sentiment_score": data["score"],
                "view": view,
                "industry": data["industries"].most_common(1)[0][0] if data["industries"] else "",
                "latest_news": data["latest_news"],
            }
        )

    return sorted(radar, key=lambda item: (item["mentions"], abs(item["sentiment_score"])), reverse=True)


def score_text(text: str) -> int:
    score = 0
    for keyword in POSITIVE_KEYWORDS:
        if keyword in text:
            score += 1
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in text:
            score -= 1
    return score


def make_commentary(market_view: str, categories: list[str], stocks: list[dict]) -> str:
    category_text = "、".join(categories) if categories else "尚無明顯主題"
    stock_text = "、".join(f"{stock['name']}({stock['code']})" for stock in stocks[:3]) if stocks else "尚無集中個股"
    return f"目前新聞面為「{market_view}」，市場焦點集中在 {category_text}；個股新聞熱度以 {stock_text} 較值得追蹤。"
