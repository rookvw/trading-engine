"""
Kiwoom REST API 어댑터 (macOS/Linux 네이티브 동작)

확인된 사항 (openapi.kiwoom.com 기준):
  - Base URL: https://api.kiwoom.com
  - 인증: OAuth2 client_credentials (appkey + secretkey)
  - 토큰 유효시간: 24시간
  - Rate limit: 초당 20회
  - 실시간: wss://api.kiwoom.com:10000

⚠ 아래 경로/필드명은 공식 문서 확인 후 수정 필요:
  - 토큰 발급 경로: /oauth2/token  (문서 코드명: au10001)
  - 계좌 잔고 경로: /api/dostk/acnt  (문서 확인 필요)
  - 현재가 경로: /api/dostk/stkinfo  (문서 확인 필요)
  - 주문 경로: /api/dostk/ordr  (문서 확인 필요)
  각 경로는 openapi.kiwoom.com > API 가이드에서 직접 확인하세요.
"""

from __future__ import annotations
import asyncio
import time
from datetime import datetime, timedelta
from typing import Any
import structlog
import httpx

from app.config import get_settings
from app.services.broker.base import (
    BrokerBase, AccountInfo, Balance, Position, Quote,
    OrderRequest, OrderResult, OrderStatus,
)

logger = structlog.get_logger()
settings = get_settings()


class TokenStore:
    """액세스 토큰 캐시 (24시간 유효)."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: datetime | None = None

    @property
    def is_valid(self) -> bool:
        if not self._token or not self._expires_at:
            return False
        return datetime.utcnow() < self._expires_at - timedelta(minutes=5)

    def set(self, token: str, expires_in_seconds: int) -> None:
        self._token = token
        self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

    @property
    def token(self) -> str | None:
        return self._token if self.is_valid else None


class RateLimiter:
    """초당 20회 제한 준수."""

    def __init__(self, calls_per_second: int = 18) -> None:  # 여유분 확보
        self._calls_per_second = calls_per_second
        self._calls: list[float] = []

    async def acquire(self) -> None:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < 1.0]
        if len(self._calls) >= self._calls_per_second:
            wait = 1.0 - (now - self._calls[0])
            if wait > 0:
                await asyncio.sleep(wait)
        self._calls.append(time.monotonic())


class KiwoomBrokerAdapter(BrokerBase):
    """
    Kiwoom REST API 구현체.
    macOS/Linux에서 직접 실행 가능.

    사용 전:
    1. openapi.kiwoom.com에서 앱 등록
    2. appkey, secretkey 발급
    3. .env에 KIWOOM_APP_KEY, KIWOOM_APP_SECRET 설정
    """

    def __init__(self) -> None:
        self._base_url = settings.kiwoom_base_url
        self._app_key = settings.kiwoom_app_key
        self._app_secret = settings.kiwoom_app_secret
        self._account = settings.kiwoom_account_number
        self._token_store = TokenStore()
        self._rate_limiter = RateLimiter()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                headers={"Content-Type": "application/json; charset=UTF-8"},
            )
        return self._client

    async def _get_token(self) -> str:
        if self._token_store.is_valid:
            return self._token_store.token  # type: ignore

        client = await self._get_client()
        # ⚠ 경로 확인 필요: openapi.kiwoom.com > 인증 > 토큰발급(au10001)
        response = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "secretkey": self._app_secret,
            },
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("token") or data.get("access_token")
        expires_in = data.get("expires_in", 86400)   # 기본 24시간
        if not token:
            raise RuntimeError(f"Token not found in response: {list(data.keys())}")

        self._token_store.set(token, expires_in)
        logger.info("kiwoom_token_refreshed", expires_in=expires_in)
        return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        await self._rate_limiter.acquire()

        token = await self._get_token()
        client = await self._get_client()

        headers = {
            "Authorization": f"Bearer {token}",
            "appkey": self._app_key,
        }

        response = await client.request(
            method,
            path,
            json=json,
            params=params,
            headers=headers,
        )

        if response.status_code == 401:
            # 토큰 만료 → 재발급 후 1회 재시도
            self._token_store._token = None
            token = await self._get_token()
            headers["Authorization"] = f"Bearer {token}"
            response = await client.request(method, path, json=json, params=params, headers=headers)

        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────
    # 계좌 정보
    # ─────────────────────────────────────────

    async def get_accounts(self) -> list[AccountInfo]:
        """
        ⚠ 경로 확인 필요: openapi.kiwoom.com > 계좌 > 계좌목록조회
        """
        data = await self._request("GET", "/api/dostk/acnt/accounts")
        accounts = data.get("acnt_list", [data])
        return [
            AccountInfo(
                account_number=a.get("acnt_no", self._account),
                account_name=a.get("acnt_nm", ""),
                account_type=a.get("acnt_tp", ""),
            )
            for a in accounts
        ]

    async def get_balance(self, account_number: str) -> Balance:
        """
        ⚠ 경로/필드명 확인 필요: openapi.kiwoom.com > 계좌 > 계좌평가잔고내역
        참고 코드명: kt00018 (계좌평가잔고내역요청)
        """
        data = await self._request(
            "POST",
            "/api/dostk/acnt",
            json={
                "acnt_no": account_number,
                "qry_tp": "1",   # ⚠ 파라미터 확인 필요
            },
        )
        return Balance(
            account_number=account_number,
            total_assets=float(data.get("tot_asst_amt", 0)),
            cash_balance=float(data.get("dnpst_amt", 0)),
            stock_value=float(data.get("stkeval_amt", 0)),
            total_pnl=float(data.get("evlt_pfls_amt", 0)),
            total_pnl_pct=float(data.get("evlt_pfls_rt", 0)),
        )

    async def get_positions(self, account_number: str) -> list[Position]:
        """
        ⚠ 경로/필드명 확인 필요: openapi.kiwoom.com > 계좌 > 계좌평가잔고내역
        """
        data = await self._request(
            "POST",
            "/api/dostk/acnt",
            json={"acnt_no": account_number, "qry_tp": "2"},
        )
        items = data.get("acnt_eval_list", [])
        positions = []
        for item in items:
            qty = int(item.get("hold_qty", 0))
            if qty <= 0:
                continue
            positions.append(
                Position(
                    symbol=item.get("stk_cd", ""),
                    name=item.get("stk_nm", ""),
                    quantity=qty,
                    avg_price=float(item.get("pchs_avg_pric", 0)),
                    current_price=float(item.get("cur_pric", 0)),
                    current_value=float(item.get("evlt_amt", 0)),
                    unrealized_pnl=float(item.get("evlt_pfls_amt", 0)),
                    unrealized_pnl_pct=float(item.get("evlt_pfls_rt", 0)),
                )
            )
        return positions

    # ─────────────────────────────────────────
    # 시세
    # ─────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Quote:
        """
        ⚠ 경로/필드명 확인 필요: openapi.kiwoom.com > 시세 > 주식현재가시세
        참고 코드명: ka10001
        """
        data = await self._request(
            "POST",
            "/api/dostk/stkinfo",
            json={"stk_cd": symbol},
        )
        output = data.get("output", data)
        return Quote(
            symbol=symbol,
            name=output.get("stk_nm", ""),
            current_price=int(output.get("cur_pric", 0)),
            prev_close=int(output.get("base_pric", 0)),
            change=int(output.get("pred_pre", 0)),
            change_pct=float(output.get("flu_rt", 0)),
            volume=int(output.get("acml_vol", 0)),
            bid=int(output.get("buy_pric", 0)),
            ask=int(output.get("sel_pric", 0)),
            high=int(output.get("high_pric", 0)),
            low=int(output.get("low_pric", 0)),
            open=int(output.get("open_pric", 0)),
        )

    # ─────────────────────────────────────────
    # 주문
    # ─────────────────────────────────────────

    async def preview_order(self, request: OrderRequest) -> dict[str, Any]:
        """주문 가능 여부 사전 확인 (실제 전송 없음)."""
        quote = await self.get_quote(request.symbol)
        balance = await self.get_balance(request.account_number)

        price = request.price or quote.current_price
        estimated_amount = price * request.quantity

        warnings = []
        if request.action == "buy":
            if estimated_amount > balance.cash_balance:
                warnings.append(f"예수금 부족: 필요 {estimated_amount:,.0f}원, 보유 {balance.cash_balance:,.0f}원")
            if estimated_amount > settings.order_max_amount_krw:
                warnings.append(f"단일 주문 한도 초과: {estimated_amount:,.0f}원 > {settings.order_max_amount_krw:,.0f}원")

        return {
            "symbol": request.symbol,
            "action": request.action,
            "quantity": request.quantity,
            "price": price,
            "estimated_amount": estimated_amount,
            "current_price": quote.current_price,
            "cash_balance": balance.cash_balance,
            "warnings": warnings,
            "can_execute": len(warnings) == 0,
        }

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """
        실주문 전송.
        ⚠ 반드시 kill switch(ORDER_EXECUTION_ENABLED=true) 통과 후 호출.

        경로/필드명 확인 필요: openapi.kiwoom.com > 주문 > 주식주문(현금)
        참고 코드명: kt10000
        """
        if not settings.order_execution_enabled:
            raise RuntimeError(
                "ORDER_EXECUTION_ENABLED=false. "
                ".env에서 kill switch를 활성화해야 실주문이 가능합니다."
            )

        # ⚠ 아래 필드명은 공식 문서 확인 후 수정 필요
        order_type_code = "00" if request.order_type == "market" else "03"
        action_code = "1" if request.action == "buy" else "2"

        try:
            data = await self._request(
                "POST",
                "/api/dostk/ordr",
                json={
                    "acnt_no": request.account_number,
                    "stk_cd": request.symbol,
                    "ord_qty": str(request.quantity),
                    "ord_pric": str(request.price or 0),
                    "buy_sell_tp": action_code,
                    "ord_tp": order_type_code,
                    # ⚠ 추가 필수 파라미터 확인 필요
                },
            )
            broker_order_id = str(
                data.get("ord_no") or data.get("order_no") or data.get("odno", "")
            )
            logger.info(
                "order_placed",
                symbol=request.symbol,
                action=request.action,
                quantity=request.quantity,
                broker_order_id=broker_order_id,
            )
            return OrderResult(
                success=True,
                broker_order_id=broker_order_id,
                message="주문 전송 완료",
                raw_response=data,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "order_failed",
                symbol=request.symbol,
                status_code=e.response.status_code,
                body=e.response.text[:200],
            )
            return OrderResult(
                success=False,
                broker_order_id=None,
                message=f"주문 실패: {e.response.text[:200]}",
            )

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """
        ⚠ 경로 확인 필요: openapi.kiwoom.com > 주문 > 미체결내역
        """
        data = await self._request(
            "POST",
            "/api/dostk/ordr/status",
            json={"ord_no": broker_order_id, "acnt_no": self._account},
        )
        item = data.get("output", data)
        return OrderStatus(
            broker_order_id=broker_order_id,
            symbol=item.get("stk_cd", ""),
            action="buy" if item.get("buy_sell_tp") == "1" else "sell",
            ordered_quantity=int(item.get("ord_qty", 0)),
            filled_quantity=int(item.get("exec_qty", 0)),
            remaining_quantity=int(item.get("unexec_qty", 0)),
            avg_filled_price=float(item.get("avg_exec_pric", 0)) or None,
            status=item.get("ord_stat_nm", "unknown"),
            created_at=None,
        )

    async def cancel_order(self, broker_order_id: str, account_number: str) -> bool:
        """
        ⚠ 경로 확인 필요: openapi.kiwoom.com > 주문 > 주식주문취소
        """
        try:
            await self._request(
                "POST",
                "/api/dostk/ordr/cancel",
                json={"ord_no": broker_order_id, "acnt_no": account_number},
            )
            logger.info("order_cancelled", broker_order_id=broker_order_id)
            return True
        except Exception as e:
            logger.error("cancel_failed", broker_order_id=broker_order_id, error=str(e))
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
