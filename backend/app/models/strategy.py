from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import String, Float, DateTime, Date, ForeignKey, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    rule_version: Mapped[str] = mapped_column(String(20), default="v1")
    strategy_type: Mapped[str] = mapped_column(String(30), default="theme_momentum")
    strategy_number: Mapped[int] = mapped_column(Integer, default=1)  # 1 | 2 | 3
    top_themes: Mapped[list] = mapped_column(JSON)
    market_note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[RecommendationItem]] = relationship(
        "RecommendationItem", back_populates="recommendation"
    )


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    theme_id: Mapped[int | None] = mapped_column(ForeignKey("themes.id"))

    action: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    sub_strategy: Mapped[str | None] = mapped_column(String(20))  # long_term | active

    theme_score: Mapped[float | None] = mapped_column(Float)
    stock_score: Mapped[float | None] = mapped_column(Float)
    score_detail: Mapped[dict | None] = mapped_column(JSON)

    reason: Mapped[str | None] = mapped_column(Text)
    target_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    price_at_recommendation: Mapped[float | None] = mapped_column(Float)

    was_executed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_note: Mapped[str | None] = mapped_column(Text)

    recommendation: Mapped[Recommendation] = relationship("Recommendation", back_populates="items")
    stock: Mapped["Stock"] = relationship("Stock")
    performance: Mapped["PerformanceRecord | None"] = relationship(
        "PerformanceRecord", back_populates="recommendation_item", uselist=False
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"))
    recommendation_item_id: Mapped[int | None] = mapped_column(ForeignKey("recommendation_items.id"))

    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)

    broker_order_id: Mapped[str | None] = mapped_column(String(50))
    traded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stock: Mapped["Stock"] = relationship("Stock")


class PerformanceRecord(Base):
    __tablename__ = "performance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_item_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation_items.id"), unique=True, nullable=False
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    strategy_number: Mapped[int] = mapped_column(Integer, default=1)  # 1 | 2 | 3

    entry_date: Mapped[date | None] = mapped_column(Date)
    entry_price: Mapped[float | None] = mapped_column(Float)
    entry_quantity: Mapped[int | None] = mapped_column(Integer)

    exit_date: Mapped[date | None] = mapped_column(Date)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_quantity: Mapped[int | None] = mapped_column(Integer)

    holding_days: Mapped[int | None] = mapped_column(Integer)
    realized_pnl: Mapped[float | None] = mapped_column(Float)
    realized_pnl_pct: Mapped[float | None] = mapped_column(Float)
    max_gain_pct: Mapped[float | None] = mapped_column(Float)
    max_loss_pct: Mapped[float | None] = mapped_column(Float)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    post_review: Mapped[str | None] = mapped_column(Text)
    score_at_recommendation: Mapped[float | None] = mapped_column(Float)
    rule_version: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    recommendation_item: Mapped[RecommendationItem] = relationship(
        "RecommendationItem", back_populates="performance"
    )
    stock: Mapped["Stock"] = relationship("Stock")


class StrategyRule(Base):
    __tablename__ = "strategy_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    strategy_number: Mapped[int] = mapped_column(Integer, default=1)
    strategy_type: Mapped[str] = mapped_column(String(30), default="theme_momentum")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IndexInclusionEvent(Base):
    __tablename__ = "index_inclusion_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_name: Mapped[str] = mapped_column(String(30), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)

    announcement_date: Mapped[date] = mapped_column(Date, nullable=False)
    inclusion_date: Mapped[date] = mapped_column(Date, nullable=False)
    removal_symbol: Mapped[str | None] = mapped_column(String(20))

    status: Mapped[str] = mapped_column(String(20), default="announced")
    source_note: Mapped[str | None] = mapped_column(Text)
    news_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id"))  # 감지된 뉴스 연결

    signal_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    recommended_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
