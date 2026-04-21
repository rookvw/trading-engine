from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    symbol: str
    name: str
    market: str
    quantity: int
    avg_price: float
    current_price: float | None
    current_value: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    bucket: str
    target_weight: float | None
    current_weight: float | None
    status: str
    entry_date: date | None
    note: str | None
    last_synced_at: datetime | None


class AllocationOut(BaseModel):
    bucket: str
    label: str
    target_pct: float
    current_pct: float
    current_value: float
    deviation: float   # current - target


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    allocations: list[AllocationOut]
    holdings: list[HoldingOut]
    last_synced_at: datetime | None
    overweight_warning: list[str]   # 과대비중 bucket 목록
