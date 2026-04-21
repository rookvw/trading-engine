"""
초기 테마 + 종목 universe 시드 스크립트.
실행: cd backend && python seed_themes.py
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.theme import Theme, ThemeStock
from app.models.stock import Stock
from app.database import Base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://trader:password@localhost:5432/trading_db")

THEMES = [
    {"code": "ai_infra", "name": "AI 인프라", "description": "AI 서버, HBM, 전력반도체", "category": "active"},
    {"code": "power_grid", "name": "전력망/전력설비", "description": "변압기, 전선, 배전망", "category": "active"},
    {"code": "defense", "name": "방산", "description": "무기체계, K-방산 수출", "category": "active"},
    {"code": "cybersecurity", "name": "사이버보안", "description": "네트워크 보안, 클라우드 보안", "category": "active"},
    {"code": "high_dividend", "name": "고배당", "description": "배당수익률 4% 이상 우량주", "category": "dividend"},
    {"code": "reit", "name": "리츠", "description": "상장 리츠, 부동산 배당", "category": "dividend"},
    {"code": "cyclical", "name": "경기민감", "description": "철강, 화학, 정유, 해운", "category": "active"},
]

# 예시 종목 (실제 종목은 직접 추가/수정)
STOCKS = [
    # AI 인프라
    {"symbol": "000660", "name": "SK하이닉스", "market": "KOSPI", "stock_type": "theme", "theme": "ai_infra", "is_core": True},
    {"symbol": "005930", "name": "삼성전자", "market": "KOSPI", "stock_type": "theme", "theme": "ai_infra", "is_core": True},
    {"symbol": "042700", "name": "한미반도체", "market": "KOSDAQ", "stock_type": "theme", "theme": "ai_infra"},
    # 전력망
    {"symbol": "267260", "name": "LS ELECTRIC", "market": "KOSPI", "stock_type": "theme", "theme": "power_grid", "is_core": True},
    {"symbol": "229640", "name": "LS에코에너지", "market": "KOSPI", "stock_type": "theme", "theme": "power_grid"},
    {"symbol": "001440", "name": "대한전선", "market": "KOSPI", "stock_type": "theme", "theme": "power_grid"},
    # 방산
    {"symbol": "012450", "name": "한화에어로스페이스", "market": "KOSPI", "stock_type": "theme", "theme": "defense", "is_core": True},
    {"symbol": "047810", "name": "한국항공우주", "market": "KOSPI", "stock_type": "theme", "theme": "defense"},
    {"symbol": "064350", "name": "현대로템", "market": "KOSPI", "stock_type": "theme", "theme": "defense"},
    # 사이버보안
    {"symbol": "053800", "name": "안랩", "market": "KOSDAQ", "stock_type": "theme", "theme": "cybersecurity", "is_core": True},
    {"symbol": "039030", "name": "이오테크닉스", "market": "KOSDAQ", "stock_type": "theme", "theme": "cybersecurity"},
    # 고배당
    {"symbol": "017670", "name": "SK텔레콤", "market": "KOSPI", "stock_type": "dividend", "theme": "high_dividend", "is_core": True, "dividend_yield": 6.5},
    {"symbol": "030200", "name": "KT", "market": "KOSPI", "stock_type": "dividend", "theme": "high_dividend", "dividend_yield": 5.8},
    {"symbol": "032640", "name": "LG유플러스", "market": "KOSPI", "stock_type": "dividend", "theme": "high_dividend", "dividend_yield": 5.2},
    # 리츠
    {"symbol": "395400", "name": "SK리츠", "market": "KOSPI", "stock_type": "dividend", "theme": "reit", "is_core": True, "dividend_yield": 7.0},
    {"symbol": "448730", "name": "맥쿼리인프라", "market": "KOSPI", "stock_type": "dividend", "theme": "reit", "dividend_yield": 6.8},
    # ETF
    {"symbol": "069500", "name": "KODEX 200", "market": "ETF", "stock_type": "etf", "theme": None},
    {"symbol": "360750", "name": "TIGER 미국S&P500", "market": "ETF", "stock_type": "etf", "theme": None},
    {"symbol": "133690", "name": "TIGER 미국나스닥100", "market": "ETF", "stock_type": "etf", "theme": None},
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        # 테마 삽입
        theme_map: dict[str, Theme] = {}
        for td in THEMES:
            t = Theme(
                code=td["code"],
                name=td["name"],
                description=td["description"],
                category=td["category"],
            )
            db.add(t)
            theme_map[td["code"]] = t
        await db.flush()

        # 종목 삽입
        for sd in STOCKS:
            s = Stock(
                symbol=sd["symbol"],
                name=sd["name"],
                market=sd["market"],
                stock_type=sd["stock_type"],
                dividend_yield=sd.get("dividend_yield"),
            )
            db.add(s)
            await db.flush()

            if sd.get("theme") and sd["theme"] in theme_map:
                ts = ThemeStock(
                    theme_id=theme_map[sd["theme"]].id,
                    stock_id=s.id,
                    is_core=sd.get("is_core", False),
                )
                db.add(ts)

        await db.commit()
        print(f"시드 완료: 테마 {len(THEMES)}개, 종목 {len(STOCKS)}개")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
