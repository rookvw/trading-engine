from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NewsItem(Base):
    """
    뉴스 아이템. RSS 크롤러 + 수동 입력 통합.

    소스:
      - investing.com RSS (S&P 편입, 글로벌 매크로)
      - 네이버 뉴스 RSS (종목명 검색)
      - DART 전자공시 (기업 내부 공시)
      - 수동 입력
    """
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 기본 정보
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # investing.com | naver | dart | manual | reuters | bloomberg

    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    crawled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 분류
    strategy_tags: Mapped[list] = mapped_column(JSON, default=list)
    # ["s1", "s2", "s3"] — 어느 전략에 관련된 뉴스인지
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    # ["005930", "AAPL"] — 관련 종목 코드
    category: Mapped[str] = mapped_column(String(30), default="general")
    # general | index_inclusion | ipo | earnings | macro | disclosure

    # 감성 분석
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    # -1.0 (매우부정) ~ +1.0 (매우긍정)
    sentiment_label: Mapped[str | None] = mapped_column(String(20))
    # bullish | bearish | neutral

    # 중요도
    importance: Mapped[int] = mapped_column(Integer, default=2)
    # 1=낮음, 2=보통, 3=높음, 4=긴급 (S&P편입같은 경우)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)
    # 전략 실행으로 이어진 뉴스인지

    # DART 전용 필드
    dart_corp_code: Mapped[str | None] = mapped_column(String(20))
    dart_report_type: Mapped[str | None] = mapped_column(String(100))


class MarketIndicator(Base):
    """
    시장 지표 스냅샷.
    VIX, 국내/미국 시장 지수, 환율 등.
    """
    __tablename__ = "market_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # VIX | KOSPI | SP500 | NASDAQ | USD_KRW | US10Y

    value: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float | None] = mapped_column(Float)   # 전일 대비 변화율
    change_abs: Mapped[float | None] = mapped_column(Float)   # 절대 변화값

    signal: Mapped[str | None] = mapped_column(String(20))
    # VIX기준: low_fear(<15) | normal(15-20) | elevated(20-30) | high_fear(>30) | extreme_fear(>40)

    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    source: Mapped[str] = mapped_column(String(30), default="yahoo_finance")
