"""
종목 점수 계산 엔진 (2단계).

ThemeScorer 결과를 받아 각 테마 내 종목을 평가하고
뉴스 인용이 포함된 이유를 생성한다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.stock import Stock
from app.models.portfolio import PortfolioHolding
from app.models.theme import ThemeStock
from app.services.broker.base import BrokerBase, Quote
from app.services.recommendation.theme_scorer import ThemeScoreResult, VIX_AGGRESSIVENESS

logger = structlog.get_logger()

ACTION_THRESHOLDS = {
    "new_entry": 0.68,
    "add":       0.52,
    "hold":      0.38,
    "reduce":    0.22,
    "exit_watch":0.10,
}

ACTION_LABELS = {
    "new_entry":  "신규진입 추천",
    "add":        "추가매수 추천",
    "hold":       "보유유지",
    "reduce":     "비중축소 검토",
    "exit_watch": "매도검토",
    "exclude":    "제외",
}

VIX_CONTEXT = {
    "low_fear":     "시장 공포지수 낮음 — 상승 여력",
    "normal":       "시장 안정 구간",
    "elevated":     "VIX 상승 중 — 변동성 주의",
    "high_fear":    "VIX 고위험 — 방어적 접근",
    "extreme_fear": "VIX 극단 — 현금 비중 우선",
}


@dataclass
class StockScoreResult:
    stock_id: int
    symbol: str
    name: str
    theme_code: str
    theme_score: float
    trend_score: float
    strength_score: float
    volume_score: float
    volatility_score: float
    quality_score: float
    stock_score: float
    combined_score: float
    action: str
    reason: str
    cited_news: list[dict] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
    is_holding: bool = False
    current_price: int = 0
    bucket: str = "theme"


class StockScorer:
    def __init__(self, db: AsyncSession, broker: BrokerBase) -> None:
        self._db = db
        self._broker = broker

    async def score_top_theme_stocks(
        self,
        top_themes: list[ThemeScoreResult],
        top_n_themes: int = 3,
        top_n_stocks: int = 5,
    ) -> list[StockScoreResult]:
        results = []
        holdings = await self._get_holdings_map()

        for theme_result in top_themes[:top_n_themes]:
            stocks = await self._get_theme_stocks(theme_result.theme_id)
            if not stocks:
                continue

            quotes: dict[str, Quote] = {}
            for stock in stocks:
                try:
                    quotes[stock.symbol] = await self._broker.get_quote(stock.symbol)
                except Exception:
                    pass

            if not quotes:
                continue

            all_change_pcts = [q.change_pct for q in quotes.values()]

            scored = []
            for stock in stocks:
                q = quotes.get(stock.symbol)
                if not q:
                    continue
                result = self._score_stock(stock, q, theme_result, all_change_pcts, holdings)
                scored.append(result)

            scored.sort(key=lambda s: s.combined_score, reverse=True)
            results.extend(scored[:top_n_stocks])

        return results

    async def _get_holdings_map(self) -> dict[int, PortfolioHolding]:
        result = await self._db.execute(select(PortfolioHolding))
        return {h.stock_id: h for h in result.scalars().all()}

    async def _get_theme_stocks(self, theme_id: int) -> list[Stock]:
        result = await self._db.execute(
            select(Stock)
            .join(ThemeStock, Stock.id == ThemeStock.stock_id)
            .where(ThemeStock.theme_id == theme_id, Stock.is_active == True)
        )
        return result.scalars().all()

    def _score_stock(
        self,
        stock: Stock,
        quote: Quote,
        theme: ThemeScoreResult,
        all_change_pcts: list[float],
        holdings: dict[int, PortfolioHolding],
    ) -> StockScoreResult:
        trend     = self._calc_trend(quote)
        strength  = self._calc_strength(quote.change_pct, all_change_pcts)
        volume    = self._calc_volume(quote)
        volatility = self._calc_volatility(quote)
        quality   = self._calc_quality(stock)

        stock_score = round(min(max(
            0.30 * trend + 0.25 * strength + 0.20 * volume + 0.15 * volatility + 0.10 * quality,
            0.0), 1.0), 4)

        combined = round(0.60 * theme.total_score + 0.40 * stock_score, 4)

        is_holding = stock.id in holdings
        action = self._determine_action(combined, is_holding)

        # 버킷 결정
        bucket = "theme"
        if stock.stock_type == "etf":
            bucket = "etf"
        elif stock.dividend_yield and stock.dividend_yield >= 3.0:
            bucket = "dividend"

        reason, cited_news = self._build_reason(stock, quote, theme, combined, action)

        return StockScoreResult(
            stock_id=stock.id,
            symbol=stock.symbol,
            name=stock.name,
            theme_code=theme.theme_code,
            theme_score=theme.total_score,
            trend_score=trend,
            strength_score=strength,
            volume_score=volume,
            volatility_score=volatility,
            quality_score=quality,
            stock_score=stock_score,
            combined_score=combined,
            action=action,
            reason=reason,
            cited_news=cited_news,
            detail={"change_pct": quote.change_pct, "vix_signal": theme.vix_signal},
            is_holding=is_holding,
            current_price=quote.current_price,
            bucket=bucket,
        )

    def _build_reason(
        self,
        stock: Stock,
        quote: Quote,
        theme: ThemeScoreResult,
        combined: float,
        action: str,
    ) -> tuple[str, list[dict]]:
        """뉴스 인용이 포함된 추천 이유 생성."""
        parts = []

        # 1. 액션 라벨
        label = ACTION_LABELS.get(action, action)

        # 2. 뉴스 인용 (최우선)
        cited = []
        for news in theme.top_news[:2]:
            parts.append(f"📰 {news['title'][:60]}{'...' if len(news['title']) > 60 else ''} ({news['source']})")
            cited.append(news)

        # 3. VIX 컨텍스트
        vix_ctx = VIX_CONTEXT.get(theme.vix_signal, "")
        if vix_ctx:
            parts.append(f"⚡ {vix_ctx}")

        # 4. 기술 지표
        if quote.change_pct > 1.5:
            parts.append(f"당일 +{quote.change_pct:.1f}%")
        elif quote.change_pct < -1.5:
            parts.append(f"당일 {quote.change_pct:.1f}%")
        if theme.total_score >= 0.6:
            parts.append(f"테마강도 {theme.total_score:.0%}")
        if stock.dividend_yield and stock.dividend_yield >= 3.0:
            parts.append(f"배당 {stock.dividend_yield:.1f}%")

        reason_body = " · ".join(parts) if parts else f"테마강도 {theme.total_score:.0%}"
        return f"{label} — {reason_body}", cited

    def _calc_trend(self, quote: Quote) -> float:
        return round(min(max((quote.change_pct + 10) / 20, 0.0), 1.0), 4)

    def _calc_strength(self, change_pct: float, all_pcts: list[float]) -> float:
        if len(all_pcts) < 2:
            return 0.5
        rank = sum(1 for p in all_pcts if p <= change_pct)
        return round(rank / len(all_pcts), 4)

    def _calc_volume(self, quote: Quote) -> float:
        amount = quote.current_price * quote.volume
        return round(min(amount / 5_000_000_000, 1.0), 4)

    def _calc_volatility(self, quote: Quote) -> float:
        if quote.prev_close <= 0:
            return 0.5
        daily_range = (quote.high - quote.low) / quote.prev_close
        return round(1.0 - min(daily_range / 0.10, 1.0), 4)

    def _calc_quality(self, stock: Stock) -> float:
        score = 0.5
        if stock.dividend_yield and stock.dividend_yield > 0:
            score += min(stock.dividend_yield / 10.0, 0.3)
        if stock.pbr and stock.pbr < 1.0:
            score += 0.2
        return round(min(score, 1.0), 4)

    def _determine_action(self, combined: float, is_holding: bool) -> str:
        if combined >= ACTION_THRESHOLDS["new_entry"]:
            return "add" if is_holding else "new_entry"
        elif combined >= ACTION_THRESHOLDS["add"]:
            return "hold" if is_holding else "new_entry"
        elif combined >= ACTION_THRESHOLDS["hold"]:
            return "hold"
        elif combined >= ACTION_THRESHOLDS["reduce"]:
            return "reduce"
        elif combined >= ACTION_THRESHOLDS["exit_watch"]:
            return "exit_watch"
        else:
            return "exclude"
