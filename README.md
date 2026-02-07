# Napkin Math — NGX Stock Analyzer

A web app that helps Nigerian Stock Exchange (NGX) investors evaluate stocks using the **Napkin Math** framework. Enter any NGX ticker, and the app automatically fetches financial data and scores it across 8 key metrics to produce a **Buy**, **Hold**, or **Sell** recommendation.

Based on this guide: [Napkin Math and Nigerian Stocks](https://nigerianstocks.com/napkin-math-and-nigerian-stocks-a-beginners-guide-to-reading-reports-without-losing-your-mind/)

## The 8 Metrics

| Metric | Good Sign | Red Flag |
|--------|-----------|----------|
| **Revenue** | Growing 10-15%+ YoY | Flat or declining |
| **Profit After Tax (PAT)** | Growing YoY | Down consistently |
| **Earnings Per Share (EPS)** | Increasing YoY | Falling 2+ quarters |
| **Dividend Per Share (DPS)** | Steady or rising | Cut or skipped |
| **Payout Ratio** (DPS / EPS) | 30-70% range | Above 100% |
| **Debt-to-Equity** | Less than 1.5x | Greater than 2.0x |
| **Return on Equity (ROE)** | Above 15% | Below 8% |
| **Operating Cash Flow** | Positive and growing | Negative 2+ years |

**Decision logic:**
- **BUY** — 4+ green flags, 0-1 red flags
- **HOLD** — mixed signals or insufficient data
- **SELL/AVOID** — 2+ red flags

## Features

- Analyze any of 145+ NGX-listed stocks
- Auto-fetches financial data (income statement, balance sheet, cash flow)
- Color-coded metric cards with YoY comparisons
- Side-by-side comparison of up to 3 stocks
- Search with autocomplete across all NGX tickers
- Top 30 most-traded stocks on the home page
- Mobile responsive

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

## Tech Stack

- **Backend:** Python, FastAPI, Jinja2
- **Frontend:** HTML, Tailwind CSS (CDN)
- **Data:** Web scraping from [stockanalysis.com](https://stockanalysis.com) via httpx + BeautifulSoup
- **State:** In-memory cache (no database)

## Project Structure

```
napkin-math/
├── main.py            # FastAPI app and routes
├── scraper.py         # Fetches financial data from stockanalysis.com
├── analyzer.py        # Napkin Math scoring engine
├── models.py          # Pydantic data models
├── ngx_tickers.py     # 145 NGX tickers + search function
├── requirements.txt
├── static/
│   └── style.css
└── templates/
    ├── base.html      # Shared layout (nav, Tailwind CDN, footer)
    ├── index.html     # Home — search bar + top 30 stock grid
    ├── analysis.html  # Single stock analysis with 8 metric cards
    ├── compare.html   # Side-by-side comparison table
    └── error.html     # Error page
```

## Routes

| Route | Description |
|-------|-------------|
| `GET /` | Home page with search and top 30 stocks |
| `GET /analyze/{ticker}` | Napkin Math analysis for a single stock |
| `GET /compare?tickers=X,Y,Z` | Side-by-side comparison (2-3 stocks) |
| `GET /api/search?q=` | JSON autocomplete endpoint |

## How the Scraper Works

Financial data is pulled from [stockanalysis.com](https://stockanalysis.com/list/nigerian-stock-exchange/), which has complete annual financial statements for all NGX-listed companies. The scraper extracts JSON data embedded in the site's SvelteKit page source (not HTML tables), fetching three pages per stock:

1. `/financials/` — Revenue, Net Income, EPS, DPS
2. `/financials/balance-sheet/` — Total Debt, Shareholder Equity
3. `/financials/cash-flow-statement/` — Operating Cash Flow

Results are cached in memory for 1 hour. A 1.5-second delay is applied between requests to be respectful to the data source.

## Disclaimer

This tool is for **educational purposes only**. It is not financial advice. Always do your own research and consult a licensed financial advisor before making investment decisions. Past performance does not guarantee future results.
