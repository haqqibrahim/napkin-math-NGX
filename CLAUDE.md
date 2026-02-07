# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A FastAPI web app that helps NGX (Nigerian Stock Exchange) investors evaluate stocks using the "Napkin Math" framework — 8 key financial metrics that produce Buy/Hold/Sell recommendations.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload)
python -m uvicorn main:app --reload

# Run directly
python main.py
```

The app runs at http://127.0.0.1:8000.

## Architecture

**Data flow:** User selects stock → `scraper.py` fetches 3 pages from stockanalysis.com → `analyzer.py` evaluates 8 metrics → Jinja2 template renders result.

- **main.py** — FastAPI routes: `/` (home), `/analyze/{ticker}` (single stock), `/compare?tickers=X,Y,Z` (side-by-side), `/api/search?q=` (autocomplete JSON)
- **scraper.py** — Extracts JSON data embedded in SvelteKit page source from stockanalysis.com. Fetches income statement, balance sheet, and cash flow pages. Results cached in-memory for 1 hour.
- **analyzer.py** — Evaluates 8 Napkin Math metrics (Revenue, PAT, EPS, DPS, Payout Ratio, D/E, ROE, Operating Cash Flow) against threshold rules. Each metric gets a green/yellow/red signal. Overall recommendation derived from signal counts.
- **models.py** — Pydantic models: `StockFinancials`, `NapkinMetric`, `NapkinResult`
- **ngx_tickers.py** — Hard-coded dict of ~145 NGX tickers with company names. `TOP_30` list. `search_tickers()` for autocomplete.
- **templates/** — Jinja2 HTML with Tailwind CSS (CDN). `base.html` is the shared layout.

## Key Details

- The scraper parses JSON from `financialData:{...}` objects embedded in stockanalysis.com's SvelteKit page source — not HTML tables. If stockanalysis.com changes their page structure, `_extract_financial_data()` in `scraper.py` will need updating.
- Rate limiting: 1.5 second delay between requests to stockanalysis.com. The scraper fetches 3 pages per stock (~5 seconds total per analysis).
- The `format_naira()` helper in `main.py` is injected into Jinja2 globals and used across templates.
- No database — session-only. Cache is in-memory dict (`_cache` in scraper.py).
