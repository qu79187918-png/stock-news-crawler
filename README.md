# Taiwan Stock News Website

A simple Python crawler and mobile-friendly web app for Taiwan stock news.

## Features

- Fetch latest Taiwan stock news from Yahoo Stock RSS.
- Store news title, time, source, link, and summary.
- Mark related stocks such as TSMC `2330`, Hon Hai `2317`, MediaTek `2454`.
- Load all listed Taiwan stocks from TWSE/MOPS open data.
- Show an analyst-style market brief and stock radar.
- Classify news by keywords: AI, semiconductor, defense, shipping, construction, finance, biotech.
- Export CSV and JSON.
- Provide a mobile-friendly web page with search, category filters, refresh, and download buttons.

## Run Locally

```powershell
cd stock-news-crawler
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Run Crawler Only

```powershell
.venv\Scripts\python.exe main.py --limit 20
```

Outputs:

- `output/news.csv`
- `output/news.json`

## Deploy to Render

1. Upload this repository to GitHub.
2. Open Render and create a new Web Service.
3. Connect this GitHub repository.
4. Use these settings:
   - Runtime: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Deploy.

## Routes

| Route | Description |
| --- | --- |
| `/` | Web search page |
| `/refresh` | Fetch latest news |
| `/refresh-stocks` | Refresh listed stock universe |
| `/api/news` | JSON API |
| `/api/analysis` | Analyst brief and stock radar API |
| `/download/csv` | Download CSV |
| `/download/json` | Download JSON |
| `/health` | Health check |
