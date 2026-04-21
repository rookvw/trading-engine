"""
포트폴리오 관리자.
- Kiwoom 잔고 동기화
- ETF 20 / 배당 30 / 테마 50 비중 계산
- 과대비중 경고
- 급락 시 추가매수 제안
"""

from __future__ import annotations
from datetime import datetime
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.stock import Stock
from app.models.portfolio import PortfolioHolding
from app.services.broker.base import BrokerBase, Position

logger = structlog.get_logger()

BUCKET_TARGETS = {
    "etf": 20.0,
    "dividend": 30.0,
    "theme": 50.0,
}

OVERWEIGHT_THRESHOLD = 5.0   # 목표 대비 ±5% 이상이면 경고


class PortfolioManager:
    def __init__(self, db: AsyncSession, broker: BrokerBase) -> None:
        self._db = db
        self._broker = broker

    async def sync_from_broker(self, account_number: str) -> list[PortfolioHolding]:
        """Kiwoom 잔고를 DB 포지션과 동기화."""
        positions: list[Position] = await self._broker.get_positions(account_number)
        now = datetime.utcnow()

        synced = []
        for pos in positions:
            # 종목 조회 또는 생성
            stock = await self._get_or_create_stock(pos)

            # 보유 포지션 업데이트 또는 생성
            result = await self._db.execute(
                select(PortfolioHolding).where(PortfolioHolding.stock_id == stock.id)
            )
            holding = result.scalar_one_or_none()

            if holding is None:
                holding = PortfolioHolding(
                    stock_id=stock.id,
                    bucket=stock.stock_type,
                    synced_from_broker=True,
                )
                self._db.add(holding)

            holding.quantity = pos.quantity
            holding.avg_price = pos.avg_price
            holding.current_price = pos.current_price
            holding.current_value = pos.current_value
            holding.unrealized_pnl = pos.unrealized_pnl
            holding.unrealized_pnl_pct = pos.unrealized_pnl_pct
            holding.synced_from_broker = True
            holding.last_synced_at = now
            synced.append(holding)

        await self._db.commit()

        # 비중 재계산
        await self._recalculate_weights()

        logger.info("portfolio_synced", count=len(synced))
        return synced

    async def _get_or_create_stock(self, pos: Position) -> Stock:
        result = await self._db.execute(
            select(Stock).where(Stock.symbol == pos.symbol)
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            stock = Stock(
                symbol=pos.symbol,
                name=pos.name,
                market="KOSPI",
                stock_type="theme",
            )
            self._db.add(stock)
            await self._db.flush()
        return stock

    async def _recalculate_weights(self) -> None:
        result = await self._db.execute(select(PortfolioHolding))
        holdings = result.scalars().all()

        total_value = sum(
            (h.current_value or (h.quantity * h.avg_price)) for h in holdings
        )
        if total_value <= 0:
            return

        for h in holdings:
            val = h.current_value or (h.quantity * h.avg_price)
            h.current_weight = round(val / total_value * 100, 2)
            h.target_weight = BUCKET_TARGETS.get(h.bucket, 0)

        await self._db.commit()

    async def get_allocation_summary(self) -> dict:
        result = await self._db.execute(select(PortfolioHolding))
        holdings = result.scalars().all()

        total_value = sum(
            (h.current_value or (h.quantity * h.avg_price)) for h in holdings
        )
        total_cost = sum(h.quantity * h.avg_price for h in holdings)
        total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0.0

        buckets: dict[str, float] = {"etf": 0.0, "dividend": 0.0, "theme": 0.0}
        for h in holdings:
            val = h.current_value or (h.quantity * h.avg_price)
            bucket = h.bucket if h.bucket in buckets else "theme"
            buckets[bucket] += val

        allocations = []
        overweight = []
        for bucket, target_pct in BUCKET_TARGETS.items():
            val = buckets.get(bucket, 0.0)
            current_pct = (val / total_value * 100) if total_value > 0 else 0.0
            deviation = current_pct - target_pct
            allocations.append({
                "bucket": bucket,
                "label": {"etf": "ETF", "dividend": "배당", "theme": "테마주"}[bucket],
                "target_pct": target_pct,
                "current_pct": round(current_pct, 2),
                "current_value": round(val, 0),
                "deviation": round(deviation, 2),
            })
            if abs(deviation) > OVERWEIGHT_THRESHOLD:
                label = {"etf": "ETF", "dividend": "배당", "theme": "테마주"}[bucket]
                direction = "과대" if deviation > 0 else "과소"
                overweight.append(f"{label} {direction}비중 ({deviation:+.1f}%)")

        return {
            "total_value": total_value,
            "total_pnl_pct": round(total_pnl_pct, 2),
            "allocations": allocations,
            "overweight_warnings": overweight,
        }
