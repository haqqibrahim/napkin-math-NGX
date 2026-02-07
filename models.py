from pydantic import BaseModel
from enum import Enum


class Signal(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Recommendation(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class StockFinancials(BaseModel):
    ticker: str
    company_name: str
    # Current year values
    revenue: float | None = None
    pat: float | None = None  # Profit After Tax (Net Income)
    eps: float | None = None
    dps: float | None = None
    total_debt: float | None = None
    shareholder_equity: float | None = None
    operating_cash_flow: float | None = None
    # Previous year values (for YoY comparison)
    prev_revenue: float | None = None
    prev_pat: float | None = None
    prev_eps: float | None = None
    prev_dps: float | None = None
    prev_total_debt: float | None = None
    prev_shareholder_equity: float | None = None
    prev_operating_cash_flow: float | None = None
    # Fiscal year labels
    current_year: str = ""
    previous_year: str = ""


class NapkinMetric(BaseModel):
    name: str
    current_value: float | None = None
    previous_value: float | None = None
    yoy_change: float | None = None  # percentage
    signal: Signal = Signal.YELLOW
    explanation: str = ""
    format_type: str = "number"  # "number", "currency", "percent", "ratio"


class NapkinResult(BaseModel):
    ticker: str
    company_name: str
    current_year: str = ""
    previous_year: str = ""
    metrics: list[NapkinMetric] = []
    recommendation: Recommendation = Recommendation.HOLD
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    summary: str = ""
