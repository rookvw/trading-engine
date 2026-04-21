"""
뉴스 크롤러 + 시장 지표 수집.

동작하는 소스:
  - Google News RSS (한국 경제/증시 + S&P편입 키워드)
  - Yahoo Finance RSS (미국 시장 헤드라인)
  - Yahoo Finance Chart API (VIX, KOSPI, SP500, NASDAQ, USD/KRW)
  - DART OpenAPI (전자공시 — API키 필요)
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any
import structlog

try:
    import httpx
    import feedparser
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.news import NewsItem, MarketIndicator
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# ── S2 트리거 키워드 ────────────────────────────────────────
S2_KEYWORDS = [
    "S&P 500 addition", "added to S&P 500", "S&P inclusion", "S&P 500 index",
    "KOSPI200 편입", "코스피200 편입", "지수 편입", "S&P500 편입",
    "index addition", "index rebalancing", "Russell 2000 addition",
    "IPO", "기업공개", "상장", "코스닥 상장",
]

# ── Google News RSS 소스 ──────────────────────────────────
GOOGLE_NEWS_QUERIES = [
    # 한국 거시경제/증시
    {"query": "한국 주식시장 경제", "strategy_tags": ["s1", "s2"], "category": "macro"},
    {"query": "코스피 코스닥 증시", "strategy_tags": ["s1"], "category": "macro"},
    # S2 전용 — 지수편입/IPO
    {"query": "S&P 500 inclusion addition index", "strategy_tags": ["s2"], "category": "index_inclusion"},
    {"query": "KOSPI200 코스피200 편입", "strategy_tags": ["s2"], "category": "index_inclusion"},
    {"query": "IPO 기업공개 상장", "strategy_tags": ["s2"], "category": "index_inclusion"},
    # 글로벌 매크로
    {"query": "Federal Reserve interest rate inflation", "strategy_tags": ["s1"], "category": "macro"},
    {"query": "VIX volatility stock market", "strategy_tags": ["s1"], "category": "macro"},
]

# ── Yahoo Finance RSS ─────────────────────────────────────
YAHOO_RSS_SOURCES = [
    {
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY&region=US&lang=en-US",
        "source": "yahoo_finance",
        "strategy_tags": ["s1"],
        "category": "macro",
    },
    {
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
        "source": "yahoo_finance",
        "strategy_tags": ["s1", "s2"],
        "category": "macro",
    },
]


class NewsCrawler:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def crawl_all(self) -> int:
        """전체 소스 크롤링. 새 아이템 수 반환."""
        if not HAS_DEPS:
            return 0

        total = 0

        # Google News RSS (병렬)
        tasks = [self._crawl_google_news(q) for q in GOOGLE_NEWS_QUERIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, int):
                total += r
            else:
                logger.warning("google_news_error", error=str(r))

        # Yahoo Finance RSS
        for src in YAHOO_RSS_SOURCES:
            try:
                total += await self._crawl_rss_url(src["url"], src["source"], src["strategy_tags"], src["category"])
            except Exception as e:
                logger.warning("yahoo_rss_error", error=str(e))

        logger.info("crawl_all_done", new_items=total)
        return total

    async def _crawl_google_news(self, cfg: dict[str, Any]) -> int:
        """Google News RSS 검색."""
        from urllib.parse import quote as urlquote
        query = urlquote(cfg["query"])
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        return await self._crawl_rss_url(
            url, "google_news", cfg["strategy_tags"], cfg["category"]
        )

    async def _crawl_rss_url(
        self,
        url: str,
        source: str,
        strategy_tags: list[str],
        category: str,
    ) -> int:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        }
        async with httpx.AsyncClient(timeout=12, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return 0

        feed = feedparser.parse(resp.text)
        count = 0

        for entry in feed.entries[:15]:
            url_item = entry.get("link", "")
            if not url_item:
                continue

            # 중복 확인
            existing = await self._db.execute(
                select(NewsItem).where(NewsItem.url == url_item)
            )
            if existing.scalar_one_or_none():
                continue

            title = entry.get("title", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            if summary:
                # HTML 태그 제거
                import re
                summary = re.sub(r"<[^>]+>", "", summary)[:800]

            published = self._parse_date(entry.get("published", ""))
            if not published:
                published = datetime.utcnow()

            # S2 키워드 감지
            text = f"{title} {summary}".lower()
            is_s2 = any(kw.lower() in text for kw in S2_KEYWORDS)
            tags = list(strategy_tags)
            if is_s2 and "s2" not in tags:
                tags.append("s2")

            item_category = "index_inclusion" if (is_s2 and category != "macro") else category
            importance = 4 if is_s2 else (3 if source == "dart" else 2)

            item = NewsItem(
                title=title,
                summary=summary or None,
                url=url_item,
                source=source,
                published_at=published,
                strategy_tags=tags,
                category=item_category,
                importance=importance,
                is_actionable=is_s2,
            )
            self._db.add(item)
            count += 1

        if count:
            await self._db.commit()
            logger.info("rss_crawled", source=source, new_items=count)

        return count

    async def crawl_dart(self, dart_api_key: str) -> int:
        """DART 전자공시 (무료 API키 필요: opendart.fss.or.kr)."""
        if not HAS_DEPS or not dart_api_key:
            return 0

        today = datetime.now().strftime("%Y%m%d")
        url = (
            f"https://opendart.fss.or.kr/api/list.json"
            f"?crtfc_key={dart_api_key}&bgn_de={today}&end_de={today}&page_count=20"
        )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()

            count = 0
            for item in data.get("list", []):
                corp_name = item.get("corp_name", "")
                report_nm = item.get("report_nm", "")
                rcept_no = item.get("rcept_no", "")
                rcept_dt = item.get("rcept_dt", "")
                dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

                existing = await self._db.execute(
                    select(NewsItem).where(NewsItem.url == dart_url)
                )
                if existing.scalar_one_or_none():
                    continue

                published = datetime.strptime(rcept_dt, "%Y%m%d") if rcept_dt else datetime.utcnow()

                news = NewsItem(
                    title=f"[공시] {corp_name} — {report_nm}",
                    url=dart_url,
                    source="dart",
                    published_at=published,
                    strategy_tags=["s1"],
                    category="disclosure",
                    importance=3,
                    is_actionable=True,
                    dart_corp_code=item.get("corp_code"),
                    dart_report_type=report_nm,
                )
                self._db.add(news)
                count += 1

            if count:
                await self._db.commit()
                logger.info("dart_crawled", new_items=count)
            return count

        except Exception as e:
            logger.error("dart_crawl_failed", error=str(e))
            return 0

    def _parse_date(self, date_str: str) -> datetime | None:
        if not date_str:
            return None
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ]:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo:
                    return dt.replace(tzinfo=None)
                return dt
            except ValueError:
                continue
        return None


class MarketIndicatorService:
    """VIX, KOSPI, SP500, NASDAQ, USD/KRW 수집."""

    VIX_SIGNAL_MAP = [
        (15, "low_fear"),
        (20, "normal"),
        (30, "elevated"),
        (40, "high_fear"),
        (float("inf"), "extreme_fear"),
    ]

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def fetch_all(self) -> dict[str, float]:
        if not HAS_DEPS:
            return {}

        tickers = {
            "VIX":     "^VIX",
            "SP500":   "^GSPC",
            "NASDAQ":  "^IXIC",
            "KOSPI":   "^KS11",
            "USD_KRW": "KRW=X",
        }

        results = {}
        tasks = [(name, ticker) for name, ticker in tickers.items()]
        fetched = await asyncio.gather(
            *[self._yahoo_quote(ticker) for _, ticker in tasks],
            return_exceptions=True
        )

        for (name, _), result in zip(tasks, fetched):
            if isinstance(result, Exception):
                logger.warning("indicator_fetch_failed", name=name, error=str(result))
                continue
            value, change_pct = result
            if value is None:
                continue

            signal = None
            if name == "VIX":
                for threshold, sig in self.VIX_SIGNAL_MAP:
                    if value < threshold:
                        signal = sig
                        break

            indicator = MarketIndicator(
                name=name,
                value=value,
                change_pct=change_pct,
                signal=signal,
            )
            self._db.add(indicator)
            results[name] = value

        if results:
            await self._db.commit()
            logger.info("indicators_fetched", count=len(results))

        return results

    async def get_latest(self) -> dict[str, dict]:
        from sqlalchemy import func
        subq = (
            select(
                MarketIndicator.name,
                func.max(MarketIndicator.recorded_at).label("latest")
            )
            .group_by(MarketIndicator.name)
            .subquery()
        )
        result = await self._db.execute(
            select(MarketIndicator).join(
                subq,
                (MarketIndicator.name == subq.c.name) &
                (MarketIndicator.recorded_at == subq.c.latest)
            )
        )
        return {
            row.name: {
                "value": row.value,
                "change_pct": row.change_pct,
                "signal": row.signal,
                "recorded_at": row.recorded_at.isoformat(),
            }
            for row in result.scalars().all()
        }

    async def _yahoo_quote(self, ticker: str) -> tuple[float | None, float | None]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            resp = await client.get(url)
            data = resp.json()

        chart = data.get("chart", {}).get("result", [{}])[0]
        meta = chart.get("meta", {})
        current = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")

        if current is None:
            return None, None

        change_pct = None
        if prev_close and prev_close > 0:
            change_pct = round((current - prev_close) / prev_close * 100, 2)

        return round(float(current), 2), change_pct
