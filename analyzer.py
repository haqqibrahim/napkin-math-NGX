"""Napkin Math analyzer for NGX stocks.

Evaluates 8 key financial metrics and generates Buy/Hold/Sell recommendations
based on the Napkin Math framework.
"""

from models import NapkinMetric, NapkinResult, Recommendation, Signal, StockFinancials


def _pct_change(current: float | None, previous: float | None) -> float | None:
    """Calculate percentage change from previous to current."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def _fmt_naira(value: float | None) -> str:
    """Format a value in Naira (billions/millions)."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000_000:
        return f"{'−' if value < 0 else ''}₦{abs_val / 1_000_000_000_000:.2f}T"
    if abs_val >= 1_000_000_000:
        return f"{'−' if value < 0 else ''}₦{abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{'−' if value < 0 else ''}₦{abs_val / 1_000_000:.2f}M"
    return f"{'−' if value < 0 else ''}₦{abs_val:,.2f}"


def _evaluate_revenue(fin: StockFinancials) -> NapkinMetric:
    yoy = _pct_change(fin.revenue, fin.prev_revenue)
    if yoy is not None and yoy >= 10:
        signal = Signal.GREEN
        explanation = f"Revenue grew {yoy:.1f}% YoY — strong growth above 10% threshold"
    elif yoy is not None and yoy > 0:
        signal = Signal.YELLOW
        explanation = f"Revenue grew {yoy:.1f}% YoY — positive but below the 10-15% ideal"
    elif yoy is not None:
        signal = Signal.RED
        explanation = f"Revenue declined {yoy:.1f}% YoY — flat or declining revenue is a red flag"
    else:
        signal = Signal.YELLOW
        explanation = "Insufficient data to calculate YoY revenue change"

    return NapkinMetric(
        name="Revenue",
        current_value=fin.revenue,
        previous_value=fin.prev_revenue,
        yoy_change=yoy,
        signal=signal,
        explanation=explanation,
        format_type="currency",
    )


def _evaluate_pat(fin: StockFinancials) -> NapkinMetric:
    yoy = _pct_change(fin.pat, fin.prev_pat)
    if fin.pat is not None and fin.pat < 0:
        signal = Signal.RED
        explanation = f"Net loss of {_fmt_naira(fin.pat)} — company is not profitable"
    elif yoy is not None and yoy > 0:
        signal = Signal.GREEN
        explanation = f"Profit After Tax grew {yoy:.1f}% YoY — profitability is improving"
    elif yoy is not None and yoy > -10:
        signal = Signal.YELLOW
        explanation = f"PAT changed {yoy:.1f}% YoY — relatively flat"
    elif yoy is not None:
        signal = Signal.RED
        explanation = f"PAT declined {yoy:.1f}% YoY — consistent profit decline is a warning"
    else:
        signal = Signal.YELLOW
        explanation = "Insufficient data to calculate PAT trend"

    return NapkinMetric(
        name="Profit After Tax",
        current_value=fin.pat,
        previous_value=fin.prev_pat,
        yoy_change=yoy,
        signal=signal,
        explanation=explanation,
        format_type="currency",
    )


def _evaluate_eps(fin: StockFinancials) -> NapkinMetric:
    yoy = _pct_change(fin.eps, fin.prev_eps)
    if fin.eps is not None and fin.eps < 0:
        signal = Signal.RED
        explanation = f"Negative EPS (₦{fin.eps:.2f}) — company is losing money per share"
    elif yoy is not None and yoy > 0:
        signal = Signal.GREEN
        explanation = f"EPS increased {yoy:.1f}% YoY — earnings per share growing"
    elif yoy is not None and yoy > -5:
        signal = Signal.YELLOW
        explanation = f"EPS roughly flat ({yoy:.1f}% YoY)"
    elif yoy is not None:
        signal = Signal.RED
        explanation = f"EPS fell {yoy:.1f}% YoY — declining earnings is a red flag"
    else:
        signal = Signal.YELLOW
        explanation = "Insufficient data to evaluate EPS trend"

    return NapkinMetric(
        name="Earnings Per Share (EPS)",
        current_value=fin.eps,
        previous_value=fin.prev_eps,
        yoy_change=yoy,
        signal=signal,
        explanation=explanation,
        format_type="number",
    )


def _evaluate_dps(fin: StockFinancials) -> NapkinMetric:
    if fin.dps is None or fin.dps == 0:
        if fin.prev_dps is not None and fin.prev_dps > 0:
            signal = Signal.RED
            explanation = "Dividend was cut or skipped — previously paid a dividend"
        else:
            signal = Signal.YELLOW
            explanation = "No dividend paid — not necessarily bad for growth stocks"
        return NapkinMetric(
            name="Dividend Per Share (DPS)",
            current_value=fin.dps,
            previous_value=fin.prev_dps,
            yoy_change=None,
            signal=signal,
            explanation=explanation,
            format_type="number",
        )

    yoy = _pct_change(fin.dps, fin.prev_dps)
    if yoy is not None and yoy > 0:
        signal = Signal.GREEN
        explanation = f"DPS increased {yoy:.1f}% YoY — dividend is growing"
    elif yoy is not None and yoy >= -5:
        signal = Signal.GREEN
        explanation = f"DPS stable ({yoy:.1f}% YoY) — consistent dividend"
    elif yoy is not None:
        signal = Signal.RED
        explanation = f"DPS declined {yoy:.1f}% YoY — dividend cut is a warning sign"
    else:
        signal = Signal.GREEN
        explanation = f"Paying dividend of ₦{fin.dps:.2f} per share"

    return NapkinMetric(
        name="Dividend Per Share (DPS)",
        current_value=fin.dps,
        previous_value=fin.prev_dps,
        yoy_change=yoy,
        signal=signal,
        explanation=explanation,
        format_type="number",
    )


def _evaluate_payout_ratio(fin: StockFinancials) -> NapkinMetric:
    if fin.eps is None or fin.eps <= 0 or fin.dps is None:
        return NapkinMetric(
            name="Payout Ratio",
            signal=Signal.YELLOW,
            explanation="Cannot calculate — EPS is zero/negative or no dividend",
            format_type="percent",
        )

    ratio = (fin.dps / fin.eps) * 100

    if 30 <= ratio <= 70:
        signal = Signal.GREEN
        explanation = f"Payout ratio of {ratio:.0f}% is in the healthy 30-70% range"
    elif ratio < 30:
        signal = Signal.YELLOW
        explanation = f"Payout ratio of {ratio:.0f}% is low — company retains most earnings"
    elif ratio <= 100:
        signal = Signal.YELLOW
        explanation = f"Payout ratio of {ratio:.0f}% is high — approaching sustainability limits"
    else:
        signal = Signal.RED
        explanation = f"Payout ratio of {ratio:.0f}% exceeds 100% — unsustainable, paying more than earned"

    return NapkinMetric(
        name="Payout Ratio",
        current_value=ratio,
        signal=signal,
        explanation=explanation,
        format_type="percent",
    )


def _evaluate_debt_to_equity(fin: StockFinancials) -> NapkinMetric:
    if fin.total_debt is None or fin.shareholder_equity is None or fin.shareholder_equity == 0:
        return NapkinMetric(
            name="Debt-to-Equity",
            signal=Signal.YELLOW,
            explanation="Insufficient data to calculate D/E ratio",
            format_type="ratio",
        )

    ratio = fin.total_debt / fin.shareholder_equity

    if fin.shareholder_equity < 0:
        signal = Signal.RED
        explanation = f"Negative equity — company's liabilities exceed assets. D/E: {ratio:.2f}×"
    elif ratio < 1.0:
        signal = Signal.GREEN
        explanation = f"D/E of {ratio:.2f}× is conservative — debt well below equity"
    elif ratio <= 1.5:
        signal = Signal.GREEN
        explanation = f"D/E of {ratio:.2f}× is within the healthy range (below 1.5×)"
    elif ratio <= 2.0:
        signal = Signal.YELLOW
        explanation = f"D/E of {ratio:.2f}× is moderate — approaching the 2.0× warning level"
    else:
        signal = Signal.RED
        explanation = f"D/E of {ratio:.2f}× exceeds 2.0× — high debt burden is a red flag"

    return NapkinMetric(
        name="Debt-to-Equity",
        current_value=ratio,
        signal=signal,
        explanation=explanation,
        format_type="ratio",
    )


def _evaluate_roe(fin: StockFinancials) -> NapkinMetric:
    if fin.pat is None or fin.shareholder_equity is None or fin.shareholder_equity <= 0:
        return NapkinMetric(
            name="Return on Equity (ROE)",
            signal=Signal.YELLOW,
            explanation="Cannot calculate ROE — missing data or negative equity",
            format_type="percent",
        )

    roe = (fin.pat / fin.shareholder_equity) * 100

    if roe >= 15:
        signal = Signal.GREEN
        explanation = f"ROE of {roe:.1f}% is above the 15% threshold — strong returns"
    elif roe >= 8:
        signal = Signal.YELLOW
        explanation = f"ROE of {roe:.1f}% is moderate — between 8-15%"
    elif roe >= 0:
        signal = Signal.RED
        explanation = f"ROE of {roe:.1f}% is below 8% — poor return on equity"
    else:
        signal = Signal.RED
        explanation = f"Negative ROE ({roe:.1f}%) — company is destroying shareholder value"

    return NapkinMetric(
        name="Return on Equity (ROE)",
        current_value=roe,
        signal=signal,
        explanation=explanation,
        format_type="percent",
    )


def _evaluate_operating_cashflow(fin: StockFinancials) -> NapkinMetric:
    yoy = _pct_change(fin.operating_cash_flow, fin.prev_operating_cash_flow)

    if fin.operating_cash_flow is None:
        return NapkinMetric(
            name="Operating Cash Flow",
            signal=Signal.YELLOW,
            explanation="No operating cash flow data available",
            format_type="currency",
        )

    if fin.operating_cash_flow < 0:
        signal = Signal.RED
        explanation = f"Negative operating cash flow ({_fmt_naira(fin.operating_cash_flow)}) — business is burning cash"
    elif yoy is not None and yoy > 0:
        signal = Signal.GREEN
        explanation = f"Operating cash flow grew {yoy:.1f}% YoY — positive and growing"
    elif yoy is not None and yoy > -10:
        signal = Signal.YELLOW
        explanation = f"Operating cash flow changed {yoy:.1f}% YoY — still positive but declining slightly"
    elif yoy is not None:
        signal = Signal.YELLOW
        explanation = f"Operating cash flow declined {yoy:.1f}% YoY — still positive but shrinking"
    else:
        signal = Signal.GREEN
        explanation = f"Positive operating cash flow of {_fmt_naira(fin.operating_cash_flow)}"

    return NapkinMetric(
        name="Operating Cash Flow",
        current_value=fin.operating_cash_flow,
        previous_value=fin.prev_operating_cash_flow,
        yoy_change=yoy,
        signal=signal,
        explanation=explanation,
        format_type="currency",
    )


def analyze_stock(fin: StockFinancials) -> NapkinResult:
    """Run the full Napkin Math analysis on a stock's financials.

    Returns a NapkinResult with all 8 metrics evaluated and an overall
    Buy/Hold/Sell recommendation.
    """
    metrics = [
        _evaluate_revenue(fin),
        _evaluate_pat(fin),
        _evaluate_eps(fin),
        _evaluate_dps(fin),
        _evaluate_payout_ratio(fin),
        _evaluate_debt_to_equity(fin),
        _evaluate_roe(fin),
        _evaluate_operating_cashflow(fin),
    ]

    green_count = sum(1 for m in metrics if m.signal == Signal.GREEN)
    yellow_count = sum(1 for m in metrics if m.signal == Signal.YELLOW)
    red_count = sum(1 for m in metrics if m.signal == Signal.RED)

    # Decision framework
    if red_count >= 2:
        recommendation = Recommendation.SELL
        summary = f"SELL/AVOID — {red_count} red flags detected. Multiple warning signs suggest caution."
    elif green_count >= 6 and red_count == 0:
        recommendation = Recommendation.BUY
        summary = f"BUY — {green_count}/8 metrics look strong with no red flags. Fundamentals are solid."
    elif green_count >= 4 and red_count <= 1:
        recommendation = Recommendation.BUY
        summary = f"BUY — {green_count}/8 green signals with only {red_count} concern(s). Generally positive outlook."
    elif red_count == 1:
        recommendation = Recommendation.HOLD
        summary = f"HOLD — Mixed signals with {green_count} green and {red_count} red. Watch the flagged metric closely."
    else:
        recommendation = Recommendation.HOLD
        summary = f"HOLD — {green_count} green, {yellow_count} neutral, {red_count} red. Insufficient strong signals either way."

    return NapkinResult(
        ticker=fin.ticker,
        company_name=fin.company_name,
        current_year=fin.current_year,
        previous_year=fin.previous_year,
        metrics=metrics,
        recommendation=recommendation,
        green_count=green_count,
        yellow_count=yellow_count,
        red_count=red_count,
        summary=summary,
    )
