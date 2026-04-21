"""
테마 점수 계산 엔진.

점수 구성:
  - momentum  (0.30): 당일 등락률 기반
  - volume    (0.15): 거래량 강도
  - breadth   (0.20): 상승 종목 비율
  - news      (0.25): 관련 뉴스 수 + 중요도 (DB에서 실시간)
  - trend     (0.10): 전일비 추세
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.models.theme import Theme, ThemeScore, ThemeStock
from app.models.stock import Stock
from app.models.strategy import StrategyRule
from app.models.news import NewsItem, MarketIndicator
from app.services.broker.base import BrokerBase, Quote

logger = structlog.get_logger()

DEFAULT_WEIGHTS = {
    "momentum": 0.30,
    "volume":   0.15,
    "breadth":  0.20,
    "news":     0.25,
    "trend":    0.10,
}

# VIX 레벨에 따른 추천 공격성 조절 계수
VIX_AGGRESSIVENESS = {
    "low_fear":     1.15,  # 시장 안정 → 공격적
    "normal":       1.00,
    "elevated":     0.85,  # 주의
    "high_fear":    0.65,  # 방어적
    "extreme_fear": 0.40,  # 현금 비중 확대
}


@dataclass
class ThemeScoreResult:
    theme_id: int
    theme_code: str
    theme_name: str
    momentum_score: float
    volume_score: float
    breadth_score: float
    news_score: float
    trend_score: float
    total_score: float
    vix_signal: str = "normal"
    vix_adjusted: bool = False
    top_news: list[dict] = field(default_factory=list)  # 추천 근거 뉴스
    detail: dict[str, Any] = field(default_factory=dict)


class ThemeScorer:
    def __init__(self, db: AsyncSession, broker: BrokerBase) -> None:
        self._db = db
        self._broker = broker
        self._vix_signal: str = "normal"
        self._vix_value: float | None = None

    async def _load_vix(self) -> None:
        """DB에서 최신 VIX 신호 로드."""
        from sqlalchemy import func
        subq = (
            select(func.max(MarketIndicator.recorded_at))
            .where(MarketIndicator.name == "VIX")
            .scalar_subquery()
        )
        result = await self._db.execute(
            select(MarketIndicator).where(
                and_(MarketIndicator.name == "VIX", MarketIndicator.recorded_at == subq)
            )
        )
        row = result.scalar_one_or_none()
        if row:
            self._vix_signal = row.signal or "normal"
            self._vix_value = row.value

    async def _get_active_weights(self) -> dict[str, Any]:
        result = await self._db.execute(
            select(StrategyRule)
            .where(StrategyRule.is_active == True)
            .order_by(desc(StrategyRule.activated_at))
            .limit(1)
        )
        rule = result.scalar_one_or_none()
        if rule and rule.parameters:
            return {**DEFAULT_WEIGHTS, **rule.parameters}
        return DEFAULT_WEIGHTS

    async def score_all_themes(self) -> list[ThemeScoreResult]:
        await self._load_vix()
        weights = await self._get_active_weights()
        aggressiveness = VIX_AGGRESSIVENESS.get(self._vix_signal, 1.0)

        result = await self._db.execute(
            select(Theme).where(Theme.is_active == True)
        )
        themes = result.scalars().all()

        scores = []
        for theme in themes:
            try:
                score = await self._score_theme(theme, weights)
                # VIX 조절 적용
                raw = score.total_score
                adjusted = round(min(max(raw * aggressiveness, 0.0), 1.0), 4)
                score.total_score = adjusted
                score.vix_signal = self._vix_signal
                score.vix_adjusted = aggressiveness != 1.0
                scores.append(score)
            except Exception as e:
                logger.warning("theme_score_error", theme=theme.code, error=str(e))

        scores.sort(key=lambda s: s.total_score, reverse=True)
        return scores

    async def _score_theme(self, theme: Theme, weights: dict[str, Any]) -> ThemeScoreResult:
        result = await self._db.execute(
            select(Stock)
            .join(ThemeStock, Stock.id == ThemeStock.stock_id)
            .where(ThemeStock.theme_id == theme.id, Stock.is_active == True)
        )
        stocks = result.scalars().all()

        if not stocks:
            return self._zero_score(theme)

        quotes: list[Quote] = []
        for stock in stocks:
            try:
                q = await self._broker.get_quote(stock.symbol)
                quotes.append(q)
            except Exception:
                pass

        if not quotes:
            return self._zero_score(theme)

        news_score, top_news = await self._calc_news(theme, stocks)

        total = (
            weights["momentum"] * self._calc_momentum(quotes)
            + weights["volume"]   * self._calc_volume(quotes)
            + weights["breadth"]  * self._calc_breadth(quotes)
            + weights["news"]     * news_score
            + weights["trend"]    * self._calc_trend(quotes)
        )

        return ThemeScoreResult(
            theme_id=theme.id,
            theme_code=theme.code,
            theme_name=theme.name,
            momentum_score=round(self._calc_momentum(quotes), 4),
            volume_score=round(self._calc_volume(quotes), 4),
            breadth_score=round(self._calc_breadth(quotes), 4),
            news_score=round(news_score, 4),
            trend_score=round(self._calc_trend(quotes), 4),
            total_score=round(min(max(total, 0.0), 1.0), 4),
            top_news=top_news,
            detail={"stock_count": len(stocks), "quote_count": len(quotes)},
        )

    async def _calc_news(
        self, theme: Theme, stocks: list[Stock]
    ) -> tuple[float, list[dict]]:
        """
        DB에서 최근 24시간 뉴스를 조회해 점수화.
        - 테마 코드 / 종목명으로 관련 뉴스 검색
        - importance * 시간가중치로 점수 계산
        """
        since = datetime.utcnow() - timedelta(hours=24)

        # 종목 이름 + 테마 이름으로 뉴스 검색 (LIKE 사용)
        keywords = [theme.name] + [s.name for s in stocks[:5]]

        from sqlalchemy import or_
        conditions = [NewsItem.published_at >= since]
        keyword_conditions = [
            NewsItem.title.ilike(f"%{kw}%")
            for kw in keywords if len(kw) >= 2
        ]
        if keyword_conditions:
            conditions.append(or_(*keyword_conditions))
        else:
            return 0.0, []

        result = await self._db.execute(
            select(NewsItem)
            .where(and_(*conditions))
            .order_by(NewsItem.importance.desc(), NewsItem.published_at.desc())
            .limit(10)
        )
        news_items = result.scalars().all()

        if not news_items:
            return 0.0, []

        # 점수 계산: importance(1-4) × 시간가중치(최근일수록 높음)
        now = datetime.utcnow()
        score_sum = 0.0
        for item in news_items:
            hours_ago = (now - item.published_at).total_seconds() / 3600
            time_weight = max(0.1, 1.0 - hours_ago / 24)
            score_sum += (item.importance / 4.0) * time_weight

        # 10개 만점 기준으로 정규화
        news_score = min(score_sum / 3.0, 1.0)

        top_news = [
            {
                "title": item.title,
                "source": item.source,
                "importance": item.importance,
                "published_at": item.published_at.isoformat(),
                "url": item.url,
                "is_actionable": item.is_actionable,
            }
            for item in news_items[:3]
        ]

        return round(news_score, 4), top_news

    def _calc_momentum(self, quotes: list[Quote]) -> float:
        if not quotes:
            return 0.0
        avg = sum(q.change_pct for q in quotes) / len(quotes)
        return round(min(max((avg + 10) / 20, 0.0), 1.0), 4)

    def _calc_volume(self, quotes: list[Quote]) -> float:
        if not quotes:
            return 0.0
        amounts = [q.current_price * q.volume for q in quotes if q.volume > 0]
        if not amounts:
            return 0.0
        return round(min(sum(amounts) / len(amounts) / 10_000_000_000, 1.0), 4)

    def _calc_breadth(self, quotes: list[Quote]) -> float:
        if not quotes:
            return 0.0
        up = sum(1 for q in quotes if q.change_pct > 0)
        return round(up / len(quotes), 4)

    def _calc_trend(self, quotes: list[Quote]) -> float:
        if not quotes:
            return 0.0
        scores = []
        for q in quotes:
            if q.prev_close > 0:
                ratio = q.current_price / q.prev_close
                scores.append(min(max((ratio - 0.95) / 0.10, 0.0), 1.0))
        return round(sum(scores) / len(scores), 4) if scores else 0.0

    def _zero_score(self, theme: Theme) -> ThemeScoreResult:
        return ThemeScoreResult(
            theme_id=theme.id,
            theme_code=theme.code,
            theme_name=theme.name,
            momentum_score=0.0,
            volume_score=0.0,
            breadth_score=0.0,
            news_score=0.0,
            trend_score=0.0,
            total_score=0.0,
        )

    async def persist_scores(self, scores: list[ThemeScoreResult], rule_version: str = "v1") -> None:
        now = datetime.utcnow()
        for rank, score in enumerate(scores, start=1):
            self._db.add(ThemeScore(
                theme_id=score.theme_id,
                scored_at=now,
                momentum_score=score.momentum_score,
                volume_score=score.volume_score,
                breadth_score=score.breadth_score,
                news_score=score.news_score,
                trend_score=score.trend_score,
                total_score=score.total_score,
                rank=rank,
                rule_version=rule_version,
            ))
        await self._db.commit()
