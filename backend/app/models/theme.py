from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        # active | etf | dividend | watchlist
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    stocks: Mapped[list[ThemeStock]] = relationship("ThemeStock", back_populates="theme")
    scores: Mapped[list[ThemeScore]] = relationship(
        "ThemeScore", back_populates="theme", order_by="ThemeScore.scored_at.desc()"
    )


class ThemeStock(Base):
    __tablename__ = "theme_stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id"), nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)  # 대표 종목 여부
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    theme: Mapped[Theme] = relationship("Theme", back_populates="stocks")
    stock: Mapped["Stock"] = relationship("Stock", back_populates="themes")


class ThemeScore(Base):
    """테마 점수 이력 - 추천 엔진이 계산한 시점마다 저장"""

    __tablename__ = "theme_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id"), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # 점수 구성 요소
    momentum_score: Mapped[float] = mapped_column(Float, default=0.0)
    volume_score: Mapped[float] = mapped_column(Float, default=0.0)
    breadth_score: Mapped[float] = mapped_column(Float, default=0.0)   # 테마 내 상승 종목 비율
    news_score: Mapped[float] = mapped_column(Float, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)

    rank: Mapped[int | None] = mapped_column(Integer)   # 당일 순위
    rule_version: Mapped[str] = mapped_column(String(20), default="v1")

    theme: Mapped[Theme] = relationship("Theme", back_populates="scores")
