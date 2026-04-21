"use client";
import { useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, type PerformanceRecord } from "@/lib/api";
import clsx from "clsx";

type Stats = {
  total_trades: number;
  win_rate?: number;
  avg_return_pct?: number;
  avg_holding_days?: number;
  by_rule_version?: { version: string; count: number; avg_return_pct: number; win_rate: number }[];
  message?: string;
};
type RecSummary = { id: number; run_at: string; rule_version: string; top_themes: string[]; strategy_number?: number };
type StrategyRule = { id: number; version: string; is_active: boolean; description?: string };
type InclusionEvent = {
  id: number; index_name: string; symbol: string; stock_name: string;
  market: string; announcement_date: string; inclusion_date: string;
  days_remaining: number; status: string; signal_generated: boolean; source_note?: string;
};

const TABS = [
  { id: "settings", label: "전략 설정" },
  { id: "perf",     label: "성과" },
  { id: "recs",     label: "추천 이력" },
  { id: "s2",       label: "S2 편입" },
] as const;
type TabId = typeof TABS[number]["id"];

const STRATEGY_META: Record<number, { name: string; color: string; desc: string }> = {
  1: { name: "전략 1", color: "#A855F7", desc: "테마 모멘텀 + VIX/뉴스 기반 AI 추천" },
  2: { name: "전략 2", color: "#E879F9", desc: "S&P500/KOSPI200 편입 발표 → 패시브 수급 선점" },
  3: { name: "전략 3", color: "#6B6B9A", desc: "준비중" },
};

export default function StrategyPage() {
  const [tab, setTab] = useState<TabId>("settings");

  return (
    <div className="space-y-4">
      <div className="pt-2">
        <p className="text-xs text-muted tracking-widest uppercase mb-0.5">Strategy Lab</p>
        <h1 className="text-xl font-bold text-text">전략 관리</h1>
      </div>

      <div className="flex gap-1 p-1 rounded-2xl" style={{ background: "#0E0E1A", border: "1px solid #252540" }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              "flex-1 py-2 rounded-xl text-xs font-semibold transition-all duration-200 relative",
              tab === t.id ? "text-white" : "text-muted hover:text-text"
            )}
          >
            {tab === t.id && (
              <motion.div
                layoutId="strategy-tab-bg"
                className="absolute inset-0 rounded-xl"
                style={{ background: "linear-gradient(135deg, #A855F7, #EC4899)" }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span className="relative z-10">{t.label}</span>
          </button>
        ))}
      </div>

      <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
        {tab === "settings" && <SettingsTab />}
        {tab === "perf"     && <PerfTab />}
        {tab === "recs"     && <RecsTab />}
        {tab === "s2"       && <S2Tab />}
      </motion.div>
    </div>
  );
}

// ── 전략 설정 탭 ──────────────────────────────────────────
function SettingsTab() {
  return (
    <div className="space-y-3">
      {/* S1 설정 */}
      <S1SettingsCard />
      {/* S2 설명 */}
      <div className="card border-nmagenta/20">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-nmagenta" style={{ boxShadow: "0 0 6px #E879F9" }} />
          <p className="font-semibold text-text">전략 2 — 지수 편입 속도</p>
        </div>
        <p className="text-xs text-muted mb-3">
          S&P500/KOSPI200 편입 발표 뉴스를 가장 빠르게 감지 → 패시브 펀드 매수 전 선점.
          뉴스 크롤러가 15분마다 자동 감지합니다.
        </p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <InfoRow label="크롤 주기" value="15분" />
          <InfoRow label="타겟 지수" value="S&P500 / KOSPI200" />
          <InfoRow label="매수 시점" value="발표 즉시" />
          <InfoRow label="최대 보유" value="편입일 전날 청산" />
        </div>
        <button
          onClick={() => api.post("/api/v1/strategy/recommend/run-inclusion", {})}
          className="btn-ghost text-xs py-2 w-full mt-3"
        >
          S2 신호 즉시 스캔
        </button>
      </div>

      {/* S3 */}
      <div className="card opacity-50 border-border/30">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full bg-muted" />
          <p className="font-semibold text-muted">전략 3 — 준비중</p>
        </div>
        <p className="text-xs text-muted/50">아직 정의되지 않은 전략 슬롯</p>
      </div>
    </div>
  );
}

function S1SettingsCard() {
  const { data: rules, mutate } = useSWR<StrategyRule[]>(
    "/api/v1/strategy/rules",
    (url: string) => api.get<StrategyRule[]>(url)
  );
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    version: "", description: "",
    momentum: "0.30", volume: "0.15", breadth: "0.20", news: "0.25", trend: "0.10",
  });

  const createRule = async () => {
    const total = ["momentum","volume","breadth","news","trend"]
      .reduce((s, k) => s + parseFloat((form as Record<string,string>)[k] || "0"), 0);
    if (Math.abs(total - 1.0) > 0.01) {
      alert(`가중치 합계가 1.0이어야 합니다. 현재: ${total.toFixed(2)}`);
      return;
    }
    await api.post("/api/v1/strategy/rules", {
      version: form.version,
      description: form.description,
      parameters: {
        momentum: parseFloat(form.momentum),
        volume: parseFloat(form.volume),
        breadth: parseFloat(form.breadth),
        news: parseFloat(form.news),
        trend: parseFloat(form.trend),
      },
    });
    mutate();
    setShowForm(false);
  };

  const activeRule = rules?.find(r => r.is_active);

  return (
    <div className="card border-npurple/20">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-npurple" style={{ boxShadow: "0 0 6px #A855F7" }} />
          <p className="font-semibold text-text">전략 1 — 테마 모멘텀</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-ghost text-[10px] py-1 px-2.5">
          {showForm ? "취소" : "+ 새 규칙"}
        </button>
      </div>

      {/* 포트폴리오 비중 안내 */}
      <div className="flex gap-2 mb-3">
        {[["50%", "고위험 테마주", "#A855F7"], ["30%", "고배당 고위험", "#E879F9"], ["20%", "ETF", "#34D399"]].map(([pct, label, color]) => (
          <div key={label} className="flex-1 rounded-xl p-2 text-center" style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
            <p className="text-sm font-bold font-mono" style={{ color }}>{pct}</p>
            <p className="text-[9px] text-muted mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* 현재 활성 가중치 */}
      {activeRule && (
        <div className="bg-void rounded-xl p-2.5 mb-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="badge bg-ngreen/20 text-ngreen border border-ngreen/30 text-[9px]">ACTIVE</span>
            <span className="text-xs font-mono text-npurple">{activeRule.version}</span>
          </div>
          {activeRule.description && <p className="text-[10px] text-muted">{activeRule.description}</p>}
        </div>
      )}

      {/* 점수 팩터 설명 */}
      <div className="grid grid-cols-2 gap-1.5 text-[10px] mb-3">
        <FactorRow label="📰 뉴스" desc="관련 뉴스 수 + 중요도" pct="25%" color="#A855F7" />
        <FactorRow label="📈 모멘텀" desc="당일 등락률" pct="30%" color="#E879F9" />
        <FactorRow label="📊 종목 폭" desc="테마 내 상승 비율" pct="20%" color="#34D399" />
        <FactorRow label="💧 거래량" desc="거래량 강도" pct="15%" color="#FCD34D" />
        <FactorRow label="📉 추세" desc="전일비 방향성" pct="10%" color="#6B6B9A" />
      </div>

      {/* 새 규칙 폼 */}
      {showForm && (
        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="mt-2 pt-3 border-t border-border space-y-2">
          <p className="section-label">새 가중치 규칙</p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: "version", label: "버전명", ph: "v1.1", full: true },
              { key: "description", label: "설명", ph: "변경 내용", full: true },
              { key: "news", label: "뉴스 (권장 0.25)" },
              { key: "momentum", label: "모멘텀 (권장 0.30)" },
              { key: "breadth", label: "종목폭 (권장 0.20)" },
              { key: "volume", label: "거래량 (권장 0.15)" },
              { key: "trend", label: "추세 (권장 0.10)" },
            ].map(({ key, label, ph, full }) => (
              <div key={key} className={full ? "col-span-2" : ""}>
                <p className="text-[10px] text-muted mb-1">{label}</p>
                <input
                  value={(form as Record<string, string>)[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  placeholder={ph}
                  className="w-full bg-void border border-border rounded-xl px-3 py-2 text-xs text-text placeholder:text-muted focus:border-npurple/50 outline-none font-mono"
                />
              </div>
            ))}
          </div>
          <button onClick={createRule} className="btn-primary w-full text-sm mt-1">활성화</button>
        </motion.div>
      )}

      {/* 규칙 이력 */}
      {rules && rules.length > 1 && (
        <div className="mt-3 pt-3 border-t border-border space-y-1.5">
          <p className="section-label">이전 규칙</p>
          {rules.filter(r => !r.is_active).slice(0, 3).map(r => (
            <div key={r.id} className="flex items-center gap-2 text-xs">
              <span className="font-mono text-muted">{r.version}</span>
              {r.description && <span className="text-muted/50 truncate">{r.description}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FactorRow({ label, desc, pct, color }: { label: string; desc: string; pct: string; color: string }) {
  return (
    <div className="flex items-center gap-2 bg-void rounded-lg p-2">
      <div className="w-1 h-8 rounded-full flex-shrink-0" style={{ background: color }} />
      <div className="min-w-0">
        <div className="flex items-center gap-1">
          <span className="text-text font-medium">{label}</span>
          <span className="font-mono font-bold text-[10px]" style={{ color }}>{pct}</span>
        </div>
        <span className="text-muted/60 text-[9px]">{desc}</span>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between bg-void rounded-lg px-2.5 py-1.5">
      <span className="text-muted">{label}</span>
      <span className="text-text font-mono font-semibold text-[11px]">{value}</span>
    </div>
  );
}

// ── 성과 탭 ──────────────────────────────────────────────
function PerfTab() {
  const { data: stats } = useSWR<Stats>("/api/v1/strategy/performance", (url: string) => api.get<Stats>(url));
  const { data: records } = useSWR<PerformanceRecord[]>(
    "/api/v1/strategy/performance/records?closed_only=false",
    (url: string) => api.get<PerformanceRecord[]>(url)
  );

  return (
    <div className="space-y-3">
      {stats && stats.total_trades > 0 ? (
        <div className="card">
          <p className="section-label">전체 성과</p>
          <div className="grid grid-cols-3 gap-3">
            <StatTile label="총 거래" value={`${stats.total_trades}건`} />
            <StatTile label="승률" value={`${stats.win_rate?.toFixed(1)}%`} good={(stats.win_rate ?? 0) >= 50} />
            <StatTile label="평균수익" value={`${(stats.avg_return_pct ?? 0) >= 0 ? "+" : ""}${stats.avg_return_pct?.toFixed(2)}%`} good={(stats.avg_return_pct ?? 0) >= 0} />
          </div>
          {stats.avg_holding_days != null && (
            <p className="text-xs text-muted text-center mt-3">평균 보유 {stats.avg_holding_days.toFixed(0)}일</p>
          )}
        </div>
      ) : (
        <div className="card text-center py-8">
          <p className="text-muted text-sm">{stats?.message ?? "종료된 포지션 없음"}</p>
        </div>
      )}
      {(records ?? []).map((r, i) => <PerformanceCard key={r.id} r={r} index={i} />)}
    </div>
  );
}

function StatTile({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="bg-void rounded-xl p-3 text-center">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className={clsx("text-lg font-mono font-bold",
        good === undefined ? "text-text" : good ? "text-ngreen" : "text-nrose"
      )}>
        {value}
      </p>
    </div>
  );
}

function PerformanceCard({ r, index }: { r: PerformanceRecord; index: number }) {
  const [open, setOpen] = useState(false);
  const [review, setReview] = useState(r.post_review ?? "");
  const pct = r.realized_pnl_pct;

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} className="card">
      <div className="flex items-start justify-between cursor-pointer" onClick={() => setOpen(!open)}>
        <div>
          <p className="font-semibold text-text text-sm">{r.name} <span className="text-xs text-muted font-mono">{r.symbol}</span></p>
          <p className="text-xs text-muted mt-0.5">{r.entry_date} → {r.exit_date ?? "보유중"}{r.holding_days != null && ` (${r.holding_days}일)`}</p>
        </div>
        {pct != null ? (
          <p className={clsx("font-mono font-bold", pct >= 0 ? "stat-up" : "stat-down")}>
            {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
          </p>
        ) : (
          <span className="badge bg-elevated text-muted border border-border">미청산</span>
        )}
      </div>
      {open && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-3 pt-3 border-t border-border space-y-2">
          {r.rule_version && <p className="text-xs text-muted">규칙: <span className="font-mono text-npurple">{r.rule_version}</span></p>}
          <textarea
            className="w-full text-sm rounded-xl p-3 resize-none bg-void border border-border text-text placeholder:text-muted focus:border-npurple/50 outline-none"
            rows={3} placeholder="회고 메모..." value={review}
            onChange={(e) => setReview(e.target.value)}
          />
          <button onClick={() => api.patch(`/api/v1/strategy/performance/${r.id}/review`, { post_review: review })} className="btn-primary text-sm w-full py-2">저장</button>
        </motion.div>
      )}
    </motion.div>
  );
}

// ── 추천 이력 탭 ─────────────────────────────────────────
function RecsTab() {
  const { data } = useSWR<RecSummary[]>("/api/v1/strategy/recommendations?limit=20", (url: string) => api.get<RecSummary[]>(url));

  return (
    <div className="space-y-2">
      {(data ?? []).map((r, i) => (
        <motion.div key={r.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="card">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-npurple bg-npurple/10 border border-npurple/20 px-2 py-0.5 rounded-lg">{r.rule_version}</span>
              {r.strategy_number != null && (
                <span className="text-[10px] font-bold text-nmagenta">S{r.strategy_number}</span>
              )}
            </div>
            <span className="text-xs text-muted font-mono">{r.run_at.slice(0, 16)}</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {(r.top_themes ?? []).map((t) => (
              <span key={t} className="badge bg-npurple/15 text-npurple border border-npurple/25 text-xs">{t}</span>
            ))}
          </div>
        </motion.div>
      ))}
      {(!data || data.length === 0) && <div className="card text-center py-8 text-muted text-sm">추천 이력 없음</div>}
    </div>
  );
}

// ── S2 편입 이벤트 탭 ────────────────────────────────────
function S2Tab() {
  const { data, mutate } = useSWR<InclusionEvent[]>(
    "/api/v1/strategy/inclusion-events",
    (url: string) => api.get<InclusionEvent[]>(url)
  );
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    index_name: "SP500", symbol: "", stock_name: "", market: "US",
    announcement_date: "", inclusion_date: "", source_note: "",
  });

  const addEvent = async () => {
    await api.post("/api/v1/strategy/inclusion-events", form);
    mutate();
    setShowAdd(false);
  };

  const STATUS_COLOR: Record<string, string> = {
    announced:  "bg-nmagenta/20 text-nmagenta border-nmagenta/30",
    executed:   "bg-ngreen/20 text-ngreen border-ngreen/30",
    cancelled:  "bg-nrose/20 text-nrose border-nrose/30",
    monitoring: "bg-nyellow/20 text-nyellow border-nyellow/30",
  };

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <p className="text-xs text-muted">S&P500/KOSPI200 편입 이벤트</p>
        <button onClick={() => setShowAdd(!showAdd)} className="btn-ghost text-xs py-1.5 px-3">
          {showAdd ? "취소" : "+ 수동 등록"}
        </button>
      </div>

      {showAdd && (
        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="card border-nmagenta/20">
          <p className="section-label">편입 이벤트 등록</p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: "index_name", label: "지수", ph: "SP500" },
              { key: "market", label: "시장", ph: "US/KR" },
              { key: "symbol", label: "종목 코드", ph: "AAPL" },
              { key: "stock_name", label: "종목명", ph: "Apple Inc." },
              { key: "announcement_date", label: "발표일", ph: "2026-01-10" },
              { key: "inclusion_date", label: "편입일", ph: "2026-01-17" },
              { key: "source_note", label: "출처", ph: "S&P Dow Jones 공식" },
            ].map(({ key, label, ph }) => (
              <div key={key} className={key === "source_note" ? "col-span-2" : ""}>
                <p className="text-[10px] text-muted mb-1">{label}</p>
                <input
                  value={(form as Record<string, string>)[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  placeholder={ph}
                  className="w-full bg-void border border-border rounded-xl px-3 py-2 text-xs text-text placeholder:text-muted focus:border-nmagenta/50 outline-none font-mono"
                />
              </div>
            ))}
          </div>
          <button onClick={addEvent} className="btn-primary w-full mt-2 text-sm">등록</button>
        </motion.div>
      )}

      {(data ?? []).length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-muted text-sm mb-1">등록된 편입 이벤트 없음</p>
          <p className="text-xs text-muted/50">뉴스 크롤러가 자동 감지하거나 수동 등록</p>
        </div>
      ) : (
        <div className="space-y-2">
          {(data ?? []).map((ev, i) => (
            <motion.div key={ev.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="card border-nmagenta/15">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className={clsx("badge border text-[10px]", STATUS_COLOR[ev.status] ?? "bg-elevated text-muted border-border")}>
                    {ev.status}
                  </span>
                  <span className="text-xs font-bold text-nmagenta">{ev.index_name}</span>
                  <span className="text-xs font-mono text-text">{ev.symbol}</span>
                </div>
                <span className="text-[10px] text-muted">{ev.days_remaining}일 남음</span>
              </div>
              <p className="text-sm font-semibold text-text">{ev.stock_name}</p>
              <div className="flex gap-3 mt-1 text-[10px] text-muted">
                <span>발표 {ev.announcement_date}</span>
                <span>편입 {ev.inclusion_date}</span>
                {ev.source_note && <span className="truncate">{ev.source_note}</span>}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
