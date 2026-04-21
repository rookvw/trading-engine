from datetime import datetime
from pydantic import BaseModel
from app.schemas.theme import ThemeWithScore
from app.schemas.portfolio import AllocationOut


class ActionItem(BaseModel):
    stock_id: int
    symbol: str
    name: str
    action: str
    reason: str
    priority: int
    is_holding: bool   # 이미 보유 중인지


class DashboardOut(BaseModel):
    generated_at: datetime
    top_themes: list[ThemeWithScore]        # 오늘 상위 3 테마
    today_actions: list[ActionItem]         # 오늘의 액션 요약
    allocations: list[AllocationOut]        # ETF/배당/테마 현재 비중
    total_portfolio_value: float
    total_pnl_pct: float
    overweight_warnings: list[str]
    order_execution_enabled: bool           # kill switch 상태 노출
