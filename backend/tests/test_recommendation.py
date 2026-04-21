"""
추천 엔진 단위 테스트 (실주문/실계좌 없음).
broker를 stub으로 대체해 로직만 검증.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.broker.base import Quote
from app.services.recommendation.theme_scorer import ThemeScorer
from app.services.recommendation.stock_scorer import StockScorer, StockScoreResult


def make_quote(symbol: str, change_pct: float, volume: int = 500_000) -> Quote:
    price = 50000
    prev = int(price / (1 + change_pct / 100))
    return Quote(
        symbol=symbol,
        name=f"테스트_{symbol}",
        current_price=price,
        prev_close=prev,
        change=price - prev,
        change_pct=change_pct,
        volume=volume,
        bid=price - 50,
        ask=price + 50,
        high=int(price * 1.03),
        low=int(price * 0.97),
        open=prev,
    )


class StubBroker:
    async def get_quote(self, symbol: str) -> Quote:
        return make_quote(symbol, change_pct=2.5, volume=1_000_000)

    async def get_balance(self, account_number: str):
        from app.services.broker.base import Balance
        return Balance(
            account_number=account_number,
            total_assets=100_000_000,
            cash_balance=30_000_000,
            stock_value=70_000_000,
            total_pnl=5_000_000,
            total_pnl_pct=5.0,
        )


def test_theme_scorer_momentum():
    """모멘텀 점수 정규화 로직 검증."""
    from app.services.recommendation.theme_scorer import ThemeScorer
    scorer = ThemeScorer(db=MagicMock(), broker=StubBroker())

    quotes = [make_quote("A", 5.0), make_quote("B", 3.0), make_quote("C", -1.0)]
    score = scorer._calc_momentum(quotes, {"momentum_period_short": 5})
    assert 0.0 <= score <= 1.0

    # 전체 상승 → 높은 점수
    up_quotes = [make_quote("A", 8.0), make_quote("B", 6.0)]
    up_score = scorer._calc_momentum(up_quotes, {})
    down_quotes = [make_quote("A", -8.0), make_quote("B", -6.0)]
    down_score = scorer._calc_momentum(down_quotes, {})
    assert up_score > down_score


def test_stock_scorer_action_thresholds():
    """combined_score에 따른 액션 결정 검증."""
    scorer = StockScorer(db=MagicMock(), broker=StubBroker())

    assert scorer._determine_action(0.80, is_holding=False) == "new_entry"
    assert scorer._determine_action(0.80, is_holding=True) == "add"
    assert scorer._determine_action(0.45, is_holding=True) == "hold"
    assert scorer._determine_action(0.20, is_holding=True) == "reduce"
    assert scorer._determine_action(0.05, is_holding=True) == "exit_watch"


def test_stock_scorer_breadth():
    scorer = StockScorer(db=MagicMock(), broker=StubBroker())
    quotes = [make_quote("A", 2.0), make_quote("B", 1.0), make_quote("C", -1.0)]
    assert scorer._calc_breadth(quotes) == pytest.approx(2 / 3, rel=0.01)


@pytest.mark.asyncio
async def test_broker_stub_quote():
    broker = StubBroker()
    q = await broker.get_quote("005930")
    assert q.change_pct == 2.5
    assert q.volume == 1_000_000
