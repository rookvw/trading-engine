"use client";
import { useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, type Holding, type Allocation } from "@/lib/api";
import clsx from "clsx";

type PortfolioData = {
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
  allocations: Allocation[];
  overweight_warnings: string[];
  holdings: Holding[];
};

const BUCKET_LABEL: Record<string, string> = { etf: "ETF", dividend: "배당", theme: "테마" };
const BUCKET_COLOR: Record<string, string> = { etf: "#A855F7", dividend: "#34D399", theme: "#E879F9" };

const STRATEGY_LABEL: Record<number, string> = { 1: "전략 1 — 테마모멘텀", 2: "전략 2 — 지수편입", 3: "전략 3 — 보류" };
const STRATEGY_COLOR: Record<number, string> = { 1: "#A855F7", 2: "#E879F9", 3: "#6B6B9A" };

const STATUS_LABEL: Record<string, string> = {
  new_entry: "신규", adding: "추가중", holding: "보유",
  reducing: "축소", exit_watch: "매도검토", excluded: "제외",
};
const STATUS_COLOR: Record<string, string> = {
  new_entry:  "bg-npurple/20 text-npurple border-npurple/30",
  adding:     "bg-ngreen/20 text-ngreen border-ngreen/30",
  holding:    "bg-elevated text-muted border-border",
  reducing:   "bg-nyellow/20 text-nyellow border-nyellow/30",
  exit_watch: "bg-nrose/20 text-nrose border-nrose/30",
  excluded:   "bg-elevated text-muted/50 border-border",
};

type ViewMode = "bucket" | "strategy";

export default function PortfolioPage() {
  const { data, isLoading, mutate } = useSWR<PortfolioData>(
    "/api/v1/portfolio/",
    (url: string) => api.get<PortfolioData>(url),
    { refreshInterval: 30_000 }
  );
  const [view, setView] = useState<ViewMode>("strategy");

  const syncPortfolio = async () => {
    await api.post("/api/v1/portfolio/sync", {});
    mutate();
  };

  if (isLoading) return <Skeleton />;
  if (!data) return null;

  const pnl = data.total_pnl_pct ?? 0;

  const byBucket: Record<string, Holding[]> = {};
  const byStrategy: Record<number, Holding[]> = {};
  for (const h of data.holdings) {
    const b = h.bucket in BUCKET_LABEL ? h.bucket : "theme";
    (byBucket[b] ??= []).push(h);
    const s = (h as Holding & { strategy_number?: number }).strategy_number ?? 1;
    (byStrategy[s] ??= []).push(h);
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between pt-2">
        <div>
          <p className="text-xs text-muted tracking-widest uppercase mb-0.5">Portfolio</p>
          <p className="text-3xl font-bold font-mono text-text">
            ₩{(data.total_value / 1_000_000).toFixed(2)}M
          </p>
          {pnl !== 0 && (
            <p className={clsx("text-sm font-mono mt-0.5", pnl >= 0 ? "stat-up" : "stat-down")}>
              {pnl >= 0 ? "▲" : "▼"} {Math.abs(pnl).toFixed(2)}%
              {data.total_pnl != null && (
                <span className="text-xs ml-1">
                  ({data.total_pnl >= 0 ? "+" : ""}₩{(data.total_pnl / 10_000).toFixed(0)}만)
                </span>
              )}
            </p>
          )}
        </div>
        <button onClick={syncPortfolio} className="btn-ghost text-xs py-2 px-3">
          ⟳ 동기화
        </button>
      </div>

      {/* Allocation bar */}
      {data.total_value > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card">
          <p className="section-label">버킷 비중</p>
          <div className="flex h-2 rounded-full overflow-hidden gap-0.5">
            {data.allocations.map((a) => (
              <motion.div
                key={a.bucket}
                initial={{ flex: 0 }}
                animate={{ flex: a.current_pct }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                style={{ backgroundColor: BUCKET_COLOR[a.bucket] ?? "#A855F7",
                  boxShadow: `0 0 6px ${BUCKET_COLOR[a.bucket] ?? "#A855F7"}60` }}
              />
            ))}
          </div>
          <div className="flex justify-between mt-2">
            {data.allocations.map((a) => (
              <div key={a.bucket} className="text-center">
                <p className="text-[10px] text-muted">{BUCKET_LABEL[a.bucket] ?? a.bucket}</p>
                <p className="text-xs font-mono font-bold" style={{ color: BUCKET_COLOR[a.bucket] }}>
                  {a.current_pct.toFixed(0)}%
                </p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* View toggle */}
      <div className="flex gap-1 p-1 rounded-2xl" style={{ background: "#0E0E1A", border: "1px solid #252540" }}>
        {(["strategy", "bucket"] as ViewMode[]).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={clsx("flex-1 py-2 rounded-xl text-sm font-semibold transition-all duration-200 relative",
              view === v ? "text-void" : "text-muted hover:text-text"
            )}
          >
            {view === v && (
              <motion.div
                layoutId="portfolio-tab"
                className="absolute inset-0 rounded-xl"
                style={{ background: "linear-gradient(135deg, #A855F7, #EC4899)" }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span className="relative z-10">{v === "strategy" ? "전략별" : "버킷별"}</span>
          </button>
        ))}
      </div>

      {/* Holdings */}
      {view === "strategy" ? (
        <>
          {([1, 2, 3] as const).map((sn) => {
            const holdings = byStrategy[sn] ?? [];
            if (holdings.length === 0) return null;
            return (
              <div key={sn}>
                <div className="flex items-center gap-2 mb-2 px-1">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: STRATEGY_COLOR[sn], boxShadow: `0 0 4px ${STRATEGY_COLOR[sn]}` }} />
                  <p className="section-label mb-0">{STRATEGY_LABEL[sn]}</p>
                </div>
                <div className="space-y-2">
                  {holdings.map((h, i) => <HoldingCard key={h.id} h={h} index={i} />)}
                </div>
              </div>
            );
          })}
          {data.holdings.length === 0 && <EmptyState />}
        </>
      ) : (
        <>
          {Object.entries(byBucket).map(([bucket, holdings]) => (
            <div key={bucket}>
              <div className="flex items-center gap-2 mb-2 px-1">
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: BUCKET_COLOR[bucket], boxShadow: `0 0 4px ${BUCKET_COLOR[bucket]}` }} />
                <p className="section-label mb-0">{BUCKET_LABEL[bucket] ?? bucket}</p>
              </div>
              <div className="space-y-2">
                {holdings.map((h, i) => <HoldingCard key={h.id} h={h} index={i} />)}
              </div>
            </div>
          ))}
          {data.holdings.length === 0 && <EmptyState />}
        </>
      )}
    </div>
  );
}

function HoldingCard({ h, index }: { h: Holding; index: number }) {
  const pnl = h.unrealized_pnl_pct;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className="card hover:border-npurple/20 transition-colors"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={clsx("badge border", STATUS_COLOR[h.status] ?? "bg-elevated text-muted border-border")}>
            {STATUS_LABEL[h.status] ?? h.status}
          </span>
          <span className="font-semibold text-text text-sm">{h.name}</span>
          <span className="text-xs text-muted font-mono">{h.symbol}</span>
        </div>
        {pnl != null && (
          <span className={clsx("text-sm font-mono font-bold", pnl >= 0 ? "stat-up" : "stat-down")}>
            {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="flex gap-4 mt-2 text-xs text-muted font-mono">
        <span>{h.quantity.toLocaleString()}주</span>
        <span>평균 ₩{h.avg_price.toLocaleString()}</span>
        {h.current_price && <span>현재 ₩{h.current_price.toLocaleString()}</span>}
        {h.current_value && <span className="ml-auto text-text">₩{(h.current_value / 10_000).toFixed(0)}만</span>}
      </div>
    </motion.div>
  );
}

function EmptyState() {
  return (
    <div className="card text-center py-10">
      <p className="text-muted text-sm">보유 종목 없음</p>
      <p className="text-xs text-muted/50 mt-1">동기화 버튼으로 계좌를 불러오세요</p>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-4 pt-2">
      <div className="h-20 bg-card rounded-2xl animate-pulse" />
      {[...Array(4)].map((_, i) => <div key={i} className="card h-16 animate-pulse" />)}
    </div>
  );
}
