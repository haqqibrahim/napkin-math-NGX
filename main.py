"""Napkin Math NGX Stock Analyzer — FastAPI application."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analyzer import analyze_stock
from models import NapkinResult
from ngx_tickers import ALL_TICKERS, TOP_30, search_tickers
from scraper import fetch_stock_financials

app = FastAPI(title="Napkin Math NGX")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def format_naira(value: float | None) -> str:
    """Format a number as Naira with appropriate suffix."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    sign = "\u2212" if value < 0 else ""
    if abs_val >= 1_000_000_000_000:
        return f"{sign}\u20a6{abs_val / 1_000_000_000_000:.2f}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}\u20a6{abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}\u20a6{abs_val / 1_000_000:.2f}M"
    return f"{sign}\u20a6{abs_val:,.2f}"


# Make format_naira available in all templates
templates.env.globals["format_naira"] = format_naira


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    top_stocks = [(ticker, ALL_TICKERS.get(ticker, ticker)) for ticker in TOP_30]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "top_stocks": top_stocks,
    })


@app.get("/analyze/{ticker}", response_class=HTMLResponse)
async def analyze(request: Request, ticker: str):
    ticker = ticker.upper().strip()

    if ticker not in ALL_TICKERS:
        # Allow free-text tickers not in our list — try to fetch anyway
        pass

    financials = await fetch_stock_financials(ticker)
    if financials is None:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": f"Could not fetch data for {ticker}",
            "message": f"We couldn't retrieve financial data for '{ticker}'. "
                       "This could mean the ticker is invalid, the data source is temporarily "
                       "unavailable, or this company doesn't have financial statements published yet.",
        }, status_code=404)

    result = analyze_stock(financials)
    return templates.TemplateResponse("analysis.html", {
        "request": request,
        "result": result,
    })


@app.get("/compare", response_class=HTMLResponse)
async def compare(request: Request, tickers: str = Query(default="")):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    ticker_list = ticker_list[:3]  # Max 3

    results: list[NapkinResult] = []

    if ticker_list:
        # Fetch all stocks concurrently
        financials_list = await asyncio.gather(
            *[fetch_stock_financials(t) for t in ticker_list]
        )
        for fin in financials_list:
            if fin is not None:
                results.append(analyze_stock(fin))

    return templates.TemplateResponse("compare.html", {
        "request": request,
        "results": results,
    })


@app.get("/api/search")
async def api_search(q: str = Query(default="", min_length=1)):
    results = search_tickers(q)
    return JSONResponse(content=results)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
