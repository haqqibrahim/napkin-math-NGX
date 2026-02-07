"""Scraper for stockanalysis.com NGX financial data.

Extracts JSON data embedded in SvelteKit page source for income statement,
balance sheet, and cash flow statement pages.
"""

import asyncio
import json
import re
import time

import httpx

from models import StockFinancials
from ngx_tickers import ALL_TICKERS

# In-memory cache: {ticker: (StockFinancials, timestamp)}
_cache: dict[str, tuple[StockFinancials, float]] = {}
CACHE_TTL = 3600  # 1 hour

BASE_URL = "https://stockanalysis.com/quote/ngx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _extract_financial_data(html: str) -> dict | None:
    """Extract the financialData JSON object from SvelteKit page source."""
    # The data is embedded in a SvelteKit init script as part of a data array.
    # Look for the financialData object which contains arrays of financial metrics.
    pattern = r'financialData:\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
    match = re.search(pattern, html)
    if not match:
        return None

    raw = "{" + match.group(1) + "}"

    # The JS object uses unquoted keys — convert to valid JSON
    # Add quotes around keys
    json_str = re.sub(r'(?<=[{,])(\w+):', r'"\1":', raw)
    # Handle JS number literals like .28293 → 0.28293
    json_str = re.sub(r'(?<=[:,\[])\.(\d)', r'0.\1', json_str)
    # Handle negative decimals like -.123
    json_str = re.sub(r'(?<=[:,\[])-\.(\d)', r'-0.\1', json_str)
    # Handle null values (sometimes appears as bare null in JS)
    json_str = json_str.replace(":null", ":null")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: try a more aggressive extraction approach
        return _extract_financial_data_fallback(html)


def _extract_financial_data_fallback(html: str) -> dict | None:
    """Fallback extraction using a broader regex pattern."""
    # Try to find the data block containing financialData
    # Look for the pattern within the SvelteKit data array
    pattern = r'"financialData":\s*(\{[^<]+?\})\s*[,}]'
    match = re.search(pattern, html)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Another fallback: extract individual arrays
    result = {}
    fields = [
        "datekey", "fiscalYear", "revenue", "netinc", "epsBasic", "dps",
        "payoutratio", "debt", "equity", "ncfo",
    ]
    for field in fields:
        pattern = rf'"{field}":\s*\[([^\]]*)\]|{field}:\s*\[([^\]]*)\]'
        match = re.search(pattern, html)
        if match:
            raw_array = match.group(1) or match.group(2)
            try:
                # Parse the array values
                values = []
                for item in raw_array.split(","):
                    item = item.strip().strip('"')
                    if item == "null" or item == "":
                        values.append(None)
                    elif item.startswith("."):
                        values.append(float("0" + item))
                    else:
                        try:
                            values.append(float(item) if "." in item else int(item))
                        except ValueError:
                            values.append(item)  # String value like date
                result[field] = values
            except Exception:
                continue

    return result if result else None


def _safe_get(data: dict, key: str, index: int) -> float | None:
    """Safely get a numeric value from the financial data arrays."""
    arr = data.get(key)
    if not arr or index >= len(arr):
        return None
    val = arr[index]
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_year_label(data: dict, index: int) -> str:
    """Get the fiscal year label for a given index."""
    arr = data.get("fiscalYear") or data.get("datekey", [])
    if arr and index < len(arr):
        val = str(arr[index])
        # If it's a date like "2024-12-31", extract just the year
        if "-" in val and len(val) > 4:
            return val[:4]
        return val
    return ""


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a page with retries."""
    for attempt in range(3):
        try:
            resp = await client.get(url, headers=HEADERS, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 429:
                await asyncio.sleep(5 * (attempt + 1))
                continue
        except httpx.HTTPError:
            if attempt < 2:
                await asyncio.sleep(2)
                continue
    return None


async def fetch_stock_financials(ticker: str) -> StockFinancials | None:
    """Fetch financial data for an NGX stock from stockanalysis.com.

    Scrapes the income statement, balance sheet, and cash flow pages
    to extract the 8 Napkin Math metrics for the latest 2 fiscal years.
    """
    ticker = ticker.upper().strip()

    # Check cache
    if ticker in _cache:
        cached, ts = _cache[ticker]
        if time.time() - ts < CACHE_TTL:
            return cached

    company_name = ALL_TICKERS.get(ticker, ticker)

    income_data = None
    balance_data = None
    cashflow_data = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch income statement
        html = await _fetch_page(client, f"{BASE_URL}/{ticker}/financials/")
        if html:
            income_data = _extract_financial_data(html)

        await asyncio.sleep(1.5)  # Rate limiting

        # Fetch balance sheet
        html = await _fetch_page(client, f"{BASE_URL}/{ticker}/financials/balance-sheet/")
        if html:
            balance_data = _extract_financial_data(html)

        await asyncio.sleep(1.5)

        # Fetch cash flow statement
        html = await _fetch_page(client, f"{BASE_URL}/{ticker}/financials/cash-flow-statement/")
        if html:
            cashflow_data = _extract_financial_data(html)

    if not income_data:
        return None

    # Determine indices for current and previous year
    # Index 0 is usually TTM, index 1 is latest full year, index 2 is previous year
    # We prefer full fiscal years over TTM
    fiscal_years = income_data.get("fiscalYear", [])
    if len(fiscal_years) >= 3:
        # Skip TTM (index 0), use index 1 (latest full year) and index 2 (previous year)
        curr_idx = 1
        prev_idx = 2
    elif len(fiscal_years) >= 2:
        curr_idx = 0
        prev_idx = 1
    else:
        curr_idx = 0
        prev_idx = -1  # No previous year

    financials = StockFinancials(
        ticker=ticker,
        company_name=company_name,
        current_year=_get_year_label(income_data, curr_idx),
        previous_year=_get_year_label(income_data, prev_idx) if prev_idx >= 0 else "",
        # Income statement
        revenue=_safe_get(income_data, "revenue", curr_idx),
        pat=_safe_get(income_data, "netinc", curr_idx),
        eps=_safe_get(income_data, "epsBasic", curr_idx),
        dps=_safe_get(income_data, "dps", curr_idx),
        prev_revenue=_safe_get(income_data, "revenue", prev_idx) if prev_idx >= 0 else None,
        prev_pat=_safe_get(income_data, "netinc", prev_idx) if prev_idx >= 0 else None,
        prev_eps=_safe_get(income_data, "epsBasic", prev_idx) if prev_idx >= 0 else None,
        prev_dps=_safe_get(income_data, "dps", prev_idx) if prev_idx >= 0 else None,
    )

    # Balance sheet
    if balance_data:
        # Balance sheet may have different indexing (no TTM)
        bs_years = balance_data.get("fiscalYear", [])
        bs_curr = 0
        bs_prev = 1 if len(bs_years) >= 2 else -1

        financials.total_debt = _safe_get(balance_data, "debt", bs_curr)
        financials.shareholder_equity = _safe_get(balance_data, "equity", bs_curr)
        if bs_prev >= 0:
            financials.prev_total_debt = _safe_get(balance_data, "debt", bs_prev)
            financials.prev_shareholder_equity = _safe_get(balance_data, "equity", bs_prev)

    # Cash flow statement
    if cashflow_data:
        cf_years = cashflow_data.get("fiscalYear", [])
        if len(cf_years) >= 3:
            cf_curr = 1
            cf_prev = 2
        elif len(cf_years) >= 2:
            cf_curr = 0
            cf_prev = 1
        else:
            cf_curr = 0
            cf_prev = -1

        financials.operating_cash_flow = _safe_get(cashflow_data, "ncfo", cf_curr)
        if cf_prev >= 0:
            financials.prev_operating_cash_flow = _safe_get(cashflow_data, "ncfo", cf_prev)

    # Cache the result
    _cache[ticker] = (financials, time.time())
    return financials


def clear_cache():
    """Clear the in-memory cache."""
    _cache.clear()
