from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class RecommendationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    symbol: str
    name: str
    theme_code: str | None
    theme_name: str | None
    action: str
    priority: int
    theme_score: float | None
    stock_score: float | None
    reason: str | None
    target_price: float | None
    stop_loss: float | None
    price_at_recommendation: float | None
    was_executed: bool


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_at: datetime
    rule_version: str
    top_themes: list
    market_note: str | None
    items: list[RecommendationItemOut] = []


class PerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    symbol: str
    name: str
    entry_date: date | None
    entry_price: float | None
    exit_date: date | None
    exit_price: float | None
    holding_days: int | None
    realized_pnl: float | None
    realized_pnl_pct: float | None
    max_gain_pct: float | None
    max_loss_pct: float | None
    is_closed: bool
    post_review: str | None
    score_at_recommendation: float | None
    rule_version: str | None


class StrategyRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    is_active: bool
    description: str | None
    parameters: dict
    activated_at: datetime | None
    created_at: datetime


class StrategyStats(BaseModel):
    """테마별 / 전체 전략 성과 집계."""

    total_trades: int
    win_rate: float
    avg_return_pct: float
    avg_holding_days: float
    best_trade: PerformanceOut | None
    worst_trade: PerformanceOut | None
    by_theme: list[dict]
    by_rule_version: list[dict]
