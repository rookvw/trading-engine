"use client";
import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import clsx from "clsx";

type MarketIndicator = { value: number; change_pct: number | null; signal: string | null };
type CitedNews = { title: string; source: string; importance: number; published_at: string; url: string | null; is_actionable: boolean };
type Signal = {
  symbol: string; name: string; action: string;
  sub_strategy: string | null; reason: string;
  cited_news?: CitedNews[]; current_price?: number; bucket?: string;
};
type Strategy = {
  number: number; name: string; description: string; status: string;
  daily_pct: number | null; monthly_pct: number | null; yearly_pct: number | null;
  open_positions: number; active_events: number | null; latest_signal: Signal[] | null;
  news_count: number; last_run: string | null;
};
type NewsItem = {
  id: number; title: string; source: string; published_at: string;
  strategy_tags: string[]; category: string; importance: number;
  sentiment_label: string | null; is_actionable: boolean; url: string | null;
};
type Portfolio = {
  total_value: number; total_pnl_pct: number | null;
  allocations: { bucket: string; label: string; target_pct: number; current_pct: number; current_value: number }[];
  by_strategy: Record<string, { value: number; count: number }>;
};
type DashboardData = {
  generated_at: string;
  order_execution_enabled: boolean;
  market_indicators: Record<string, MarketIndicator>;
  strategies: Strategy[];
  news_feed: NewsItem[];
  portfolio: Portfolio;
};

const VIX_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  low_fear:     { label: "저공포", color: "#34D399", bg: "rgba(52,211,153,0.15)" },
  normal:       { label: "안정",   color: "#A855F7", bg: "rgba(168,85,247,0.15)" },
  elevated:     { label: "주의",   color: "#FCD34D", bg: "rgba(252,211,77,0.15)" },
  high_fear:    { label: "위험",   color: "#FB7185", bg: "rgba(251,113,133,0.15)" },
  extreme_fear: { label: "극공포", color: "#EF4444", bg: "rgba(239,68,68,0.15)" },
};
const ACTION_COLOR: Record<string, string> = {
  new_entry: "bg-npurple/20 text-npurple border-npurple/35",
  add:       "bg-nviolet/20 text-nviolet border-nviolet/35",
  hold:      "bg-elevated text-muted border-border",
  reduce:    "bg-nyellow/20 text-nyellow border-nyellow/30",
  exit_watch:"bg-nrose/20 text-nrose border-nrose/30",
};
const ACTION_LABEL: Record<string, string> = {
  new_entry: "신규진입", add: "추가매수", hold: "보유", reduce: "비중축소", exit_watch: "매도검토",
};
const SOURCE_SHORT: Record<string, string> = {
  google_news: "G뉴스", yahoo_finance: "Yahoo", dart: "DART", naver: "네이버", manual: "수동",
};

export default function Dashboard() {
  const { data, isLoading, mutate } = useSWR<DashboardData>(
    "/api/v1/dashboard/",
    (url: string) => api.get<DashboardData>(url),
    { refreshInterval: 30_000 }
  );
  const [runningAI, setRunningAI] = useState(false);
  const [crawling, setCrawling] = useState(false);

  const runAI = async () => {
    setRunningAI(true);
    try {
      await api.post("/api/v1/strategy/recommend/run", {});
      await mutate();
    } finally {
      setRunningAI(false);
    }
  };

  const refreshAll = async () => {
    setCrawling(true);
    try {
      await Promise.all([
        api.post("/api/v1/dashboard/news/crawl", {}),
        api.post("/api/v1/dashboard/indicators/refresh", {}),
      ]);
      await mutate();
    } finally {
      setCrawling(false);
    }
  };

  if (isLoading) return <Skeleton />;
  if (!data) return null;

  const vix = data.market_indicators["VIX"];
  const vixCfg = VIX_CONFIG[vix?.signal ?? "normal"] ?? VIX_CONFIG.normal;
  const s1 = data.strategies.find(s => s.number === 1);
  const s2 = data.strategies.find(s => s.number === 2);
  const pnl = data.portfolio.total_pnl_pct ?? 0;
  const hasSignals = !!(s1?.latest_signal?.length);

  return (
    <div className="space-y-4">
      {/* ── 헤더 ─────────────────────────────────── */}
      <div className="flex items-center justify-between pt-2">
        <div>
          <p className="text-[10px] text-muted tracking-widest uppercase">Trading Engine</p>
          <div className="flex items-baseline gap-3 mt-0.5">
            <p className="text-2xl font-bold font-mono text-text">
              ₩{data.portfolio.total_value > 0 ? (data.portfolio.total_value / 1_000_000).toFixed(1) : "—"}M
            </p>
            {pnl !== 0 && (
              <span className={clsx("text-sm font-mono font-bold", pnl >= 0 ? "stat-up" : "stat-down")}>
                {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={refreshAll}
            disabled={crawling}
            className="btn-ghost text-xs py-1.5 px-3"
          >
            {crawling ? <Spinner /> : "⟳"}
          </button>
          <button
            onClick={runAI}
            disabled={runningAI}
            className="btn-primary text-xs py-1.5 px-4"
          >
            {runningAI ? <span className="flex items-center gap-1.5"><Spinner />분석중</span> : "AI 분석"}
          </button>
        </div>
      </div>

      {/* ── 시장 지표 칩 ──────────────────────────── */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
        {/* VIX 강조 */}
        {vix && (
          <div
            className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-bold"
            style={{ background: vixCfg.bg, borderColor: vixCfg.color + "50", color: vixCfg.color }}
          >
            <span className="text-[10px] font-normal text-muted">VIX</span>
            <span>{vix.value.toFixed(1)}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-md" style={{ background: vixCfg.color + "20" }}>
              {vixCfg.label}
            </span>
          </div>
        )}
        {Object.entries(data.market_indicators)
          .filter(([k]) => k !== "VIX")
          .map(([name, ind]) => (
            <MarketChip key={name} name={name} ind={ind} />
          ))}
      </div>

      {/* ── AI 추천 — 전면 노출 ──────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="section-label">AI 추천 — 전략 1</p>
          {s1?.last_run && (
            <span className="text-[10px] text-muted font-mono">
              {new Date(s1.last_run).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>

        {!hasSignals ? (
          <div className="card text-center py-8 border-npurple/10">
            <p className="text-muted text-sm mb-3">AI 분석 결과 없음</p>
            <button onClick={runAI} disabled={runningAI} className="btn-primary text-sm px-6 py-2">
              {runningAI ? "분석중..." : "지금 AI 분석 실행"}
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {s1!.latest_signal!.map((sig, i) => (
              <SignalCard key={sig.symbol} sig={sig} index={i} onApprove={mutate} />
            ))}
          </div>
        )}
      </div>

      {/* ── 전략2 S&P편입/IPO 알림 ───────────────── */}
      {(s2?.active_events ?? 0) > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="card border-nmagenta/30"
          style={{ background: "rgba(232,121,249,0.05)" }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-nmagenta text-base">⚡</span>
            <p className="font-semibold text-nmagenta text-sm">전략2 — 지수편입 이벤트</p>
            <span className="badge bg-nmagenta/20 text-nmagenta border border-nmagenta/30 text-xs ml-auto">
              {s2!.active_events}건
            </span>
          </div>
          <p className="text-xs text-muted">S&P500/KOSPI200 편입 발표 감지 → 주문 페이지에서 확인</p>
        </motion.div>
      )}

      {/* ── 전략 수익률 요약 ─────────────────────── */}
      <div className="grid grid-cols-2 gap-2">
        {[s1, s2].filter(Boolean).map((s) => s && (
          <div key={s.number} className="card">
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-xs font-semibold text-text">전략{s.number}</p>
              <span className="text-[10px] text-muted">{s.news_count}뉴스</span>
            </div>
            <div className="grid grid-cols-3 gap-1 text-center">
              <ReturnMini label="당일" v={s.daily_pct} />
              <ReturnMini label="월간" v={s.monthly_pct} />
              <ReturnMini label="연간" v={s.yearly_pct} />
            </div>
            <p className="text-[10px] text-muted mt-1.5">포지션 {s.open_positions}개</p>
          </div>
        ))}
      </div>

      {/* ── 뉴스 피드 ────────────────────────────── */}
      <div>
        <p className="section-label">최신 뉴스</p>
        <div className="space-y-1.5">
          {data.news_feed.length === 0 ? (
            <div className="card text-center py-6 text-muted text-sm">
              뉴스 없음 — ⟳ 버튼으로 크롤링
            </div>
          ) : (
            data.news_feed.slice(0, 10).map((n) => <NewsCard key={n.id} n={n} />)
          )}
        </div>
      </div>
    </div>
  );
}

// ── Signal Card — AI 추천 카드 ───────────────────────────
function SignalCard({ sig, index, onApprove }: { sig: Signal; index: number; onApprove: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [creating, setCreating] = useState(false);

  const createOrder = async () => {
    setCreating(true);
    try {
      await api.post("/api/v1/orders/", {
        title: `AI추천 — ${sig.name} ${ACTION_LABEL[sig.action] ?? sig.action}`,
        items: [{
          stock_symbol: sig.symbol,
          stock_name: sig.name,
          action: sig.action === "new_entry" || sig.action === "add" ? "buy" : "sell",
          quantity: 1,
          reason: sig.reason,
        }],
      });
      onApprove();
    } catch (e) {
      alert("주문 생성 실패");
    } finally {
      setCreating(false);
    }
  };

  const isBuy = sig.action === "new_entry" || sig.action === "add";

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="card border-npurple/15"
      style={{ background: "rgba(168,85,247,0.04)" }}
    >
      <div className="flex items-start gap-3">
        {/* 액션 배지 */}
        <span className={clsx("badge border flex-shrink-0 mt-0.5", ACTION_COLOR[sig.action] ?? ACTION_COLOR.hold)}>
          {ACTION_LABEL[sig.action] ?? sig.action}
        </span>

        {/* 종목 정보 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-text">{sig.name}</span>
            <span className="text-xs text-muted font-mono">{sig.symbol}</span>
            {sig.current_price && (
              <span className="text-xs text-muted font-mono ml-auto">₩{sig.current_price.toLocaleString()}</span>
            )}
          </div>

          {/* 이유 요약 */}
          <p className="text-xs text-muted mt-1 leading-relaxed line-clamp-2">{sig.reason}</p>

          {/* 인용 뉴스 */}
          {sig.cited_news && sig.cited_news.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] text-npurple mt-1 hover:underline"
            >
              {expanded ? "▲ 뉴스 접기" : `▼ 근거 뉴스 ${sig.cited_news.length}건`}
            </button>
          )}

          <AnimatePresence>
            {expanded && sig.cited_news && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-2 space-y-1.5 overflow-hidden"
              >
                {sig.cited_news.map((cn, i) => (
                  <div key={i} className="flex items-start gap-2 bg-void rounded-xl p-2">
                    <span className="text-[10px] text-npurple font-bold flex-shrink-0 mt-0.5">
                      {SOURCE_SHORT[cn.source] ?? cn.source}
                    </span>
                    <p className="text-[11px] text-muted leading-tight">{cn.title}</p>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* 주문 버튼 */}
      {(isBuy || sig.action === "reduce" || sig.action === "exit_watch") && (
        <div className="mt-2.5 pt-2.5 border-t border-border/50 flex justify-end">
          <button
            onClick={createOrder}
            disabled={creating}
            className={clsx("btn text-xs py-1.5 px-4", isBuy ? "btn-primary" : "btn-danger")}
          >
            {creating ? <Spinner /> : isBuy ? "주문 생성 →" : "매도 주문 →"}
          </button>
        </div>
      )}
    </motion.div>
  );
}

// ── Market Chip ────────────────────────────────────────
function MarketChip({ name, ind }: { name: string; ind: MarketIndicator }) {
  const isUp = (ind.change_pct ?? 0) >= 0;
  return (
    <div className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-border bg-card text-xs font-mono">
      <span className="text-[10px] text-muted">{name}</span>
      <span className="text-text font-bold">
        {name === "USD_KRW" ? ind.value.toFixed(0) : ind.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </span>
      {ind.change_pct != null && (
        <span className={isUp ? "text-ngreen" : "text-nrose"}>
          {isUp ? "+" : ""}{ind.change_pct.toFixed(1)}%
        </span>
      )}
    </div>
  );
}

// ── Return Mini ────────────────────────────────────────
function ReturnMini({ label, v }: { label: string; v: number | null }) {
  return (
    <div>
      <p className="text-[9px] text-muted mb-0.5">{label}</p>
      {v != null ? (
        <p className={clsx("text-xs font-mono font-bold", v >= 0 ? "text-ngreen" : "text-nrose")}>
          {v >= 0 ? "+" : ""}{v.toFixed(1)}%
        </p>
      ) : (
        <p className="text-xs text-muted/40">—</p>
      )}
    </div>
  );
}

// ── News Card ─────────────────────────────────────────
function NewsCard({ n }: { n: NewsItem }) {
  const isS2 = n.strategy_tags?.includes("s2");
  const importanceColors: Record<number, string> = {
    4: "text-nmagenta border-nmagenta/40 bg-nmagenta/10",
    3: "text-npurple border-npurple/30 bg-npurple/10",
    2: "text-muted border-border bg-elevated",
    1: "text-muted/50 border-border/50 bg-elevated/50",
  };
  return (
    <div className={clsx("card py-2.5", isS2 && n.importance >= 3 ? "border-nmagenta/25" : "")}>
      <div className="flex items-start gap-2">
        <div className={clsx("badge border text-[9px] flex-shrink-0 mt-0.5", importanceColors[n.importance] ?? importanceColors[2])}>
          {n.importance === 4 ? "긴급" : n.importance === 3 ? "중요" : "일반"}
        </div>
        <div className="flex-1 min-w-0">
          {n.url ? (
            <a href={n.url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-text leading-snug hover:text-npurple transition-colors line-clamp-2">
              {n.title}
            </a>
          ) : (
            <p className="text-xs text-text leading-snug line-clamp-2">{n.title}</p>
          )}
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] text-muted">{SOURCE_SHORT[n.source] ?? n.source}</span>
            <span className="text-[10px] text-muted/50">
              {new Date(n.published_at).toLocaleString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            </span>
            {isS2 && (
              <span className="badge bg-nmagenta/15 text-nmagenta border border-nmagenta/25 text-[9px]">S2</span>
            )}
            {n.is_actionable && (
              <span className="badge bg-nrose/15 text-nrose border border-nrose/25 text-[9px]">실행가능</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Spinner() {
  return <span className="inline-block w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin" />;
}

function Skeleton() {
  return (
    <div className="space-y-4 pt-4">
      <div className="h-14 bg-card rounded-2xl animate-pulse" />
      <div className="h-8 bg-card rounded-xl animate-pulse" />
      {[...Array(3)].map((_, i) => <div key={i} className="card h-24 animate-pulse" />)}
    </div>
  );
}
