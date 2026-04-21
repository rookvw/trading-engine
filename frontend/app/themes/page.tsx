"use client";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, type Theme } from "@/lib/api";
import clsx from "clsx";

type ThemeItem = Theme & {
  latest_score: number | null;
  rank: number | null;
  scored_at: string | null;
};

export default function ThemesPage() {
  const { data, isLoading, mutate } = useSWR<ThemeItem[]>(
    "/api/v1/themes/",
    (url: string) => api.get<ThemeItem[]>(url),
    { refreshInterval: 120_000 }
  );

  const runScoring = async () => {
    await api.post("/api/v1/themes/score/run", {});
    mutate();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pt-2">
        <div>
          <p className="text-xs text-muted tracking-widest uppercase mb-0.5">Theme Engine</p>
          <h1 className="text-xl font-bold text-text">테마 분석</h1>
        </div>
        <button onClick={runScoring} className="btn-primary text-xs py-2 px-4">
          ⟳ 점수 갱신
        </button>
      </div>

      {isLoading && <ThemeSkeleton />}

      <div className="space-y-2">
        {(data ?? [])
          .sort((a, b) => (b.latest_score ?? -1) - (a.latest_score ?? -1))
          .map((theme, i) => (
            <ThemeCard key={theme.id} theme={theme} index={i} />
          ))}
      </div>
    </div>
  );
}

function ThemeCard({ theme, index }: { theme: ThemeItem; index: number }) {
  const score = theme.latest_score;
  const pct = score != null ? Math.round(score * 100) : null;
  const color = pct == null ? "#6B6B9A" : pct >= 70 ? "#A855F7" : pct >= 40 ? "#E879F9" : "#FB7185";
  const borderClass = pct == null ? "" : pct >= 70 ? "hover:border-npurple/40" : pct >= 40 ? "hover:border-nmagenta/40" : "hover:border-nrose/30";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={clsx("card transition-colors cursor-default", borderClass)}
    >
      <div className="flex items-center gap-3">
        {/* Rank */}
        <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-bold text-muted border border-border flex-shrink-0">
          {theme.rank ?? index + 1}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-text">{theme.name}</span>
            <span className="text-xs text-muted font-mono">{theme.code}</span>
          </div>
          {theme.description && (
            <p className="text-xs text-muted mt-0.5 truncate">{theme.description}</p>
          )}
          {theme.scored_at && (
            <p className="text-[10px] text-muted/50 mt-0.5">
              {new Date(theme.scored_at).toLocaleString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            </p>
          )}
        </div>

        {/* Score */}
        <div className="flex-shrink-0 text-right">
          {pct != null ? (
            <>
              <p className="text-2xl font-mono font-bold" style={{ color, textShadow: `0 0 10px ${color}80` }}>
                {pct}
              </p>
              <ScoreBar pct={pct} color={color} />
            </>
          ) : (
            <span className="text-xs text-muted">미측정</span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function ScoreBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="w-16 h-1 bg-void rounded-full overflow-hidden mt-1">
      <motion.div
        className="h-full rounded-full"
        style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      />
    </div>
  );
}

function ThemeSkeleton() {
  return (
    <div className="space-y-2">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="card h-16 animate-pulse bg-card" />
      ))}
    </div>
  );
}
