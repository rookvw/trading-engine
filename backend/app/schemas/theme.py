from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ThemeScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    theme_id: int
    scored_at: datetime
    momentum_score: float
    volume_score: float
    breadth_score: float
    news_score: float
    trend_score: float
    total_score: float
    rank: int | None
    rule_version: str


class StockBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    market: str
    last_price: int | None


class ThemeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    category: str
    is_active: bool


class ThemeWithScore(ThemeOut):
    latest_score: ThemeScoreOut | None = None
    top_stocks: list[StockBrief] = []
