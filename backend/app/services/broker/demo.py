"""
Demo 브로커 — 키움 미연결 시 Yahoo Finance로 실제 시장 데이터 조회.

한국 주식: {symbol}.KS (KOSPI) / {symbol}.KQ (KOSDAQ)
"""
from __future__ import annotations
import random
from datetime import datetime
import structlog

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from app.services.broker.base import (
    BrokerBase, AccountInfo, Balance, Position, Quote,
    OrderRequest, OrderResult, OrderStatus,
)

logger = structlog.get_logger()

YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
}


class DemoBroker(BrokerBase):
    """
    데모/개발용 브로커.
    - get_quote: Yahoo Finance API (실제 시장 데이터)
    - place_order: 시뮬레이션 (실제 주문 없음)
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[Quote, datetime]] = {}

    async def get_accounts(self) -> list[AccountInfo]:
        return [AccountInfo(
            account_number="DEMO-0000",
            account_name="데모 계좌",
            account_type="demo",
        )]

    async def get_balance(self, account_number: str = "DEMO-0000") -> Balance:
        return Balance(
            account_number="DEMO-0000",
            total_assets=100_000_000,
            cash_balance=50_000_000,
            stock_value=50_000_000,
            total_pnl=2_500_000,
            total_pnl_pct=2.5,
        )

    async def get_positions(self, account_number: str = "DEMO-0000") -> list[Position]:
        return []

    async def get_quote(self, symbol: str) -> Quote:
        # 캐시 (60초)
        cached = self._cache.get(symbol)
        if cached:
            quote, ts = cached
            if (datetime.utcnow() - ts).seconds < 60:
                return quote

        quote = await self._yahoo_quote(symbol)
        self._cache[symbol] = (quote, datetime.utcnow())
        return quote

    async def _yahoo_quote(self, symbol: str) -> Quote:
        if not HAS_HTTPX:
            return self._mock_quote(symbol)

        # 한국 주식 suffix 시도 순서
        tickers = [symbol, f"{symbol}.KS", f"{symbol}.KQ"]

        for ticker in tickers:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
                async with httpx.AsyncClient(timeout=8, headers=YAHOO_HEADERS) as client:
                    resp = await client.get(url)
                    data = resp.json()

                result = data.get("chart", {}).get("result")
                if not result:
                    continue

                meta = result[0].get("meta", {})
                current = meta.get("regularMarketPrice")
                prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
                name = meta.get("shortName") or meta.get("longName") or symbol

                if not current:
                    continue

                change = round(current - (prev_close or current), 2)
                change_pct = round(change / (prev_close or current) * 100, 2) if prev_close else 0.0
                volume = meta.get("regularMarketVolume") or 0
                high = meta.get("regularMarketDayHigh") or int(current * 1.02)
                low = meta.get("regularMarketDayLow") or int(current * 0.98)

                return Quote(
                    symbol=symbol,
                    name=name,
                    current_price=int(current),
                    prev_close=int(prev_close or current),
                    change=int(change),
                    change_pct=change_pct,
                    volume=int(volume),
                    bid=int(current * 0.999),
                    ask=int(current * 1.001),
                    high=int(high),
                    low=int(low),
                    open=int(meta.get("regularMarketOpen") or current),
                )

            except Exception as e:
                logger.debug("yahoo_quote_failed", symbol=ticker, error=str(e))
                continue

        return self._mock_quote(symbol)

    def _mock_quote(self, symbol: str) -> Quote:
        """Yahoo 실패 시 임의 데이터."""
        base = 50_000 + (hash(symbol) % 200_000)
        change_pct = round(random.uniform(-3.0, 3.0), 2)
        current = int(base * (1 + change_pct / 100))
        return Quote(
            symbol=symbol,
            name=symbol,
            current_price=current,
            prev_close=base,
            change=current - base,
            change_pct=change_pct,
            volume=random.randint(100_000, 5_000_000),
            bid=current - 100,
            ask=current + 100,
            high=int(current * 1.015),
            low=int(current * 0.985),
            open=int(base * (1 + random.uniform(-0.5, 0.5) / 100)),
        )

    async def place_order(self, order: OrderRequest) -> OrderResult:
        logger.info("demo_order_simulated", symbol=order.symbol, action=order.action, qty=order.quantity)
        return OrderResult(
            success=True,
            broker_order_id=f"DEMO-{random.randint(100000, 999999)}",
            message="데모 모드: 주문 시뮬레이션 완료 (실제 전송 없음)",
        )

    async def preview_order(self, order: OrderRequest) -> dict:
        return {
            "symbol": order.symbol,
            "action": order.action,
            "quantity": order.quantity,
            "estimated_price": order.price,
            "estimated_amount": (order.price or 0) * order.quantity,
            "note": "데모 모드",
        }

    async def cancel_order(self, broker_order_id: str, account_number: str = "DEMO-0000") -> bool:
        return True

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        return OrderStatus(
            broker_order_id=broker_order_id,
            status="filled",
            filled_quantity=0,
            filled_price=None,
        )
