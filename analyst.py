from collections import Counter, defaultdict

from market_data import build_stock_market_data


POSITIVE_KEYWORDS = [
    "大漲",
    "創高",
    "新高",
    "看好",
    "利多",
    "成長",
    "強攻",
    "買超",
    "目標價",
    "優於預期",
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
    news_type_counter = Counter()
    sentiment_points = 0

    for item in news_items:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        sentiment_points += score_text(text)

        for category in item.get("categories", []):
            category_counter[category] += 1
        for news_type in item.get("news_types", []):
            news_type_counter[news_type] += 1
        for stock in item.get("related_stocks", []):
            stock_counter[(stock.get("code", ""), stock.get("name", ""))] += 1
            if stock.get("industry"):
                industry_counter[stock["industry"]] += 1

    market_view = market_view_from_score(sentiment_points)
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
        "top_news_types": [name for name, _ in news_type_counter.most_common(5)],
        "top_stocks": top_stocks,
        "commentary": make_market_commentary(market_view, top_categories, top_stocks, news_type_counter),
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
        radar.append(
            {
                "code": code,
                "name": name,
                "mentions": data["mentions"],
                "sentiment_score": data["score"],
                "view": stock_view_from_score(data["score"]),
                "industry": data["industries"].most_common(1)[0][0] if data["industries"] else "",
                "latest_news": data["latest_news"],
            }
        )

    return sorted(radar, key=lambda item: (item["mentions"], abs(item["sentiment_score"])), reverse=True)


def build_favorite_reports(favorites: list[dict], news_items: list[dict]) -> list[dict]:
    reports = []
    for stock in favorites:
        code = stock.get("code", "")
        stock_news = [
            item
            for item in news_items
            if any(related.get("code") == code for related in item.get("related_stocks", []))
        ]
        market_data = build_stock_market_data(code)
        score = sum(score_text(f"{item.get('title', '')} {item.get('summary', '')}") for item in stock_news)
        news_type_counter = Counter(news_type for item in stock_news for news_type in item.get("news_types", []))
        category_counter = Counter(category for item in stock_news for category in item.get("categories", []))

        reports.append(
            {
                "stock": stock,
                "view": stock_view_from_score(score),
                "confidence": confidence_label(stock_news, market_data),
                "sentiment_score": score,
                "news_count": len(stock_news),
                "latest_news": stock_news[:5],
                "top_news_types": [name for name, _ in news_type_counter.most_common(4)],
                "top_categories": [name for name, _ in category_counter.most_common(4)],
                "market_data": market_data,
                "thesis": build_stock_thesis(stock, stock_news, market_data, score, news_type_counter),
                "evidence": build_evidence(stock_news, market_data),
                "risks": build_risks(stock_news, market_data),
            }
        )

    return reports


def score_text(text: str) -> int:
    score = 0
    for keyword in POSITIVE_KEYWORDS:
        if keyword in text:
            score += 1
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in text:
            score -= 1
    return score


def market_view_from_score(score: int) -> str:
    if score >= 3:
        return "偏多"
    if score <= -3:
        return "偏空"
    return "觀望"


def stock_view_from_score(score: int) -> str:
    if score >= 2:
        return "偏多觀察"
    if score <= -2:
        return "風險觀察"
    return "中性觀察"


def confidence_label(stock_news: list[dict], market_data: dict) -> str:
    data_points = sum(1 for item in market_data.values() if isinstance(item, dict) and item.get("status") == "ok")
    if len(stock_news) >= 3 and data_points >= 2:
        return "中高"
    if stock_news or data_points:
        return "中"
    return "低"


def build_stock_thesis(stock: dict, stock_news: list[dict], market_data: dict, score: int, news_type_counter: Counter) -> str:
    name = stock.get("name", "")
    view = stock_view_from_score(score)
    main_types = "、".join(name for name, _ in news_type_counter.most_common(3)) or "一般新聞"
    institutional = market_data.get("institutional", {})
    institutional_note = ""
    if institutional.get("status") == "ok":
        net_buy = institutional.get("三大法人買賣超股數") or institutional.get("外資買賣超股數") or ""
        if net_buy:
            institutional_note = f"法人買賣超資料顯示近期籌碼數字為 {net_buy} 股，需搭配成交量解讀。"
    else:
        institutional_note = "法人資料目前未取得，籌碼判讀需保守。"

    return f"{name} 目前新聞面判讀為「{view}」，主要觸發題材集中在 {main_types}。{institutional_note} 本報告屬新聞與公開資料整理，非買賣建議。"


def build_evidence(stock_news: list[dict], market_data: dict) -> list[str]:
    evidence = []
    if stock_news:
        evidence.append(f"近期相關新聞 {len(stock_news)} 則，代表市場資訊流有一定討論度。")
        evidence.append(f"最新重點新聞：{stock_news[0].get('title', '')}")
    else:
        evidence.append("目前最新新聞池中沒有明顯相關新聞，短線題材熱度偏低。")

    price = market_data.get("price", {})
    if price.get("status") == "ok":
        evidence.append(f"最近交易資料：收盤價 {price.get('收盤價', '-')}，漲跌價差 {price.get('漲跌價差', '-')}。")

    institutional = market_data.get("institutional", {})
    if institutional.get("status") == "ok":
        evidence.append(
            "法人籌碼：外資 {foreign}、投信 {trust}、自營商 {dealer}。".format(
                foreign=institutional.get("外資買賣超股數", "-"),
                trust=institutional.get("投信買賣超股數", "-"),
                dealer=institutional.get("自營商買賣超股數", "-"),
            )
        )

    valuation = market_data.get("valuation", {})
    if valuation.get("status") == "ok":
        evidence.append(
            "估值資料：本益比 {pe}、殖利率 {yield_}%、股價淨值比 {pb}。".format(
                pe=valuation.get("本益比", "-"),
                yield_=valuation.get("殖利率(%)", "-"),
                pb=valuation.get("股價淨值比", "-"),
            )
        )

    margin = market_data.get("margin", {})
    if margin.get("status") == "ok":
        evidence.append(f"融資融券：融資餘額 {margin.get('融資餘額', '-')}，融券餘額 {margin.get('融券餘額', '-')}。")

    return evidence


def build_risks(stock_news: list[dict], market_data: dict) -> list[str]:
    risks = []
    if not stock_news:
        risks.append("新聞資料不足，分析可信度較低。")
    if market_data.get("large_small_orders", {}).get("status") != "ok":
        risks.append("大小單資料尚未接入，短線主力資金判讀不完整。")
    if market_data.get("institutional", {}).get("status") != "ok":
        risks.append("法人買賣超資料未取得，籌碼面需要等待資料補齊。")
    return risks or ["目前主要風險來自大盤波動與題材退燒，仍需搭配個人風險控管。"]


def make_market_commentary(market_view: str, categories: list[str], stocks: list[dict], news_type_counter: Counter) -> str:
    category_text = "、".join(categories) if categories else "尚無明顯題材"
    stock_text = "、".join(f"{stock['name']}({stock['code']})" for stock in stocks[:3]) if stocks else "尚無集中個股"
    type_text = "、".join(name for name, _ in news_type_counter.most_common(3)) or "一般新聞"
    return f"目前全市場新聞面為「{market_view}」，新聞類型以 {type_text} 為主，題材集中在 {category_text}；個股熱度以 {stock_text} 較值得追蹤。"
