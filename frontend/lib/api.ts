async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status} ${err}`);
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => req<T>(path),
  post: <T>(path: string, body: unknown) =>
    req<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    req<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
};

// ── Type helpers ─────────────────────────────
export type Allocation = {
  bucket: string;
  label: string;
  target_pct: number;
  current_pct: number;
  current_value: number;
  deviation: number;
};

export type ActionItem = {
  stock_id: number;
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority: number;
  is_holding: boolean;
};

export type ThemeScore = {
  total_score: number;
  rank: number | null;
  scored_at: string | null;
};

export type Theme = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  latest_score: ThemeScore | null;
};

export type Holding = {
  id: number;
  stock_id: number;
  symbol: string;
  name: string;
  market: string;
  quantity: number;
  avg_price: number;
  current_price: number | null;
  current_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  bucket: string;
  target_weight: number | null;
  current_weight: number | null;
  status: string;
  entry_date: string | null;
};

export type OrderItem = {
  id: number;
  symbol: string;
  name: string;
  action: string;
  quantity: number;
  price: number | null;
  amount: number | null;
  reason: string | null;
  priority: number;
  status: string;
};

export type Order = {
  id: number;
  title: string;
  status: string;
  note: string | null;
  created_at: string;
  items: OrderItem[];
};

export type PerformanceRecord = {
  id: number;
  symbol: string;
  name: string;
  entry_date: string | null;
  entry_price: number | null;
  exit_date: string | null;
  realized_pnl_pct: number | null;
  holding_days: number | null;
  is_closed: boolean;
  score_at_recommendation: number | null;
  rule_version: string | null;
  post_review: string | null;
};
