from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_broker_dep
from app.services.broker.base import BrokerBase
from app.services.portfolio.manager import PortfolioManager, BUCKET_TARGETS
from app.models.portfolio import PortfolioHolding
from app.models.stock import Stock
from app.config import get_settings

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
settings = get_settings()


@router.get("/")
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """포트폴리오 전체 현황."""
    result = await db.execute(
        select(PortfolioHolding, Stock)
        .join(Stock, PortfolioHolding.stock_id == Stock.id)
        .order_by(PortfolioHolding.bucket, PortfolioHolding.current_value.desc())
    )
    holdings_raw = result.all()

    pm = PortfolioManager(db, broker)
    allocation = await pm.get_allocation_summary()

    total_cost = sum(h.avg_price * h.quantity for h, _ in holdings_raw)
    total_value = allocation["total_value"]
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    holdings = []
    for h, s in holdings_raw:
        holdings.append({
            "id": h.id,
            "stock_id": s.id,
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market,
            "quantity": h.quantity,
            "avg_price": h.avg_price,
            "current_price": h.current_price,
            "current_value": h.current_value,
            "unrealized_pnl": h.unrealized_pnl,
            "unrealized_pnl_pct": h.unrealized_pnl_pct,
            "bucket": h.bucket,
            "target_weight": BUCKET_TARGETS.get(h.bucket),
            "current_weight": h.current_weight,
            "status": h.status,
            "entry_date": h.entry_date.isoformat() if h.entry_date else None,
            "note": h.note,
            "last_synced_at": h.last_synced_at.isoformat() if h.last_synced_at else None,
        })

    return {
        "total_value": round(total_value, 0),
        "total_cost": round(total_cost, 0),
        "total_pnl": round(total_pnl, 0),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "allocations": allocation["allocations"],
        "overweight_warnings": allocation["overweight_warnings"],
        "holdings": holdings,
    }


@router.post("/sync")
async def sync_portfolio(
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """Kiwoom 잔고 동기화."""
    pm = PortfolioManager(db, broker)
    holdings = await pm.sync_from_broker(settings.kiwoom_account_number)
    return {"synced_count": len(holdings), "message": "포트폴리오 동기화 완료"}


@router.patch("/{holding_id}/status")
async def update_holding_status(
    holding_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """보유 종목 상태 변경 (holding / reducing / exit_watch 등)."""
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    valid_statuses = {"new_entry", "adding", "holding", "reducing", "exit_watch", "excluded"}
    new_status = payload.get("status")
    if new_status and new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {valid_statuses}")

    if new_status:
        holding.status = new_status
    if "note" in payload:
        holding.note = payload["note"]
    if "bucket" in payload:
        holding.bucket = payload["bucket"]

    await db.commit()
    return {"id": holding_id, "status": holding.status}
