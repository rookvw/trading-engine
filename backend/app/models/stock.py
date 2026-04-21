from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, Integer, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(10), nullable=False)  # KOSPI | KOSDAQ | ETF
    sector: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(50))

    # 주요 재무/배당 정보 (주기적 갱신)
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    per: Mapped[float | None] = mapped_column(Float)
    pbr: Mapped[float | None] = mapped_column(Float)
    dividend_yield: Mapped[float | None] = mapped_column(Float)
    dividend_per_share: Mapped[int | None] = mapped_column(Integer)

    # 분류
    stock_type: Mapped[str] = mapped_column(
        String(20), default="theme"
        # theme | etf | dividend | watchlist
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text)

    last_price: Mapped[int | None] = mapped_column(Integer)        # 최근 현재가
    price_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    themes: Mapped[list["ThemeStock"]] = relationship("ThemeStock", back_populates="stock")
    holding: Mapped["PortfolioHolding | None"] = relationship(
        "PortfolioHolding", back_populates="stock", uselist=False
    )
