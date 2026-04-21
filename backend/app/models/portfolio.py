from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import String, Float, DateTime, Date, ForeignKey, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False, unique=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl_pct: Mapped[float | None] = mapped_column(Float)

    # 포트폴리오 분류
    bucket: Mapped[str] = mapped_column(String(20), nullable=False)  # etf | dividend | theme
    strategy_number: Mapped[int] = mapped_column(Integer, default=1)  # 1 | 2 | 3
    sub_strategy: Mapped[str | None] = mapped_column(String(20))      # long_term | active (S1용)
    target_weight: Mapped[float | None] = mapped_column(Float)
    current_weight: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String(30), default="holding")
    entry_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)

    synced_from_broker: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    stock: Mapped["Stock"] = relationship("Stock", back_populates="holding")
