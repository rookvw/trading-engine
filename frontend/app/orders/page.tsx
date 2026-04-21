"use client";
import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { api, type Order } from "@/lib/api";
import clsx from "clsx";

type OrderSummary = {
  id: number;
  title: string;
  status: string;
  item_count: number;
  created_at: string;
  executed_at: string | null;
};

const STATUS_COLOR: Record<string, string> = {
  draft:     "bg-elevated text-muted border-border",
  confirmed: "bg-npurple/20 text-npurple border-npurple/30",
  executing: "bg-nyellow/20 text-nyellow border-nyellow/30",
  completed: "bg-ngreen/20 text-ngreen border-ngreen/30",
  cancelled: "bg-nrose/20 text-nrose border-nrose/30",
};
const STATUS_LABEL: Record<string, string> = {
  draft: "초안", confirmed: "1차확인", executing: "실행중", completed: "완료", cancelled: "취소",
};

export default function OrdersPage() {
  const { data, isLoading, mutate } = useSWR<OrderSummary[]>(
    "/api/v1/orders/",
    (url: string) => api.get<OrderSummary[]>(url),
    { refreshInterval: 10_000 }
  );
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pt-2">
        <div>
          <p className="text-xs text-muted tracking-widest uppercase mb-0.5">Order Center</p>
          <h1 className="text-xl font-bold text-text">주문 센터</h1>
        </div>
        <button
          onClick={async () => {
            await api.post("/api/v1/strategy/recommend/run", {});
            mutate();
          }}
          className="btn-primary text-xs py-2 px-4"
        >
          + 추천 생성
        </button>
      </div>

      <AnimatePresence mode="wait">
        {selectedId ? (
          <motion.div key="detail" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
            <OrderDetail orderId={selectedId} onBack={() => setSelectedId(null)} onRefresh={mutate} />
          </motion.div>
        ) : (
          <motion.div key="list" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
            {isLoading && <Skeleton />}
            {(data ?? []).map((o, i) => (
              <motion.div
                key={o.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="card cursor-pointer hover:border-npurple/20 transition-colors active:scale-[0.99]"
                onClick={() => setSelectedId(o.id)}
              >
                <div className="flex items-center justify-between">
                  <span className={clsx("badge border", STATUS_COLOR[o.status] ?? "bg-elevated text-muted border-border")}>
                    {STATUS_LABEL[o.status] ?? o.status}
                  </span>
                  <span className="text-xs text-muted font-mono">
                    {new Date(o.created_at).toLocaleDateString("ko-KR")}
                  </span>
                </div>
                <p className="font-semibold text-text mt-1.5">{o.title}</p>
                {o.item_count > 0 && (
                  <p className="text-xs text-muted mt-0.5">{o.item_count}개 종목</p>
                )}
              </motion.div>
            ))}
            {!isLoading && (!data || data.length === 0) && (
              <div className="card text-center py-10">
                <p className="text-muted text-sm">주문 없음</p>
                <p className="text-xs text-muted/50 mt-1">추천 생성 버튼으로 시작하세요</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function OrderDetail({ orderId, onBack, onRefresh }: {
  orderId: number; onBack: () => void; onRefresh: () => void;
}) {
  const { data, mutate } = useSWR<Order>(
    `/api/v1/orders/${orderId}`,
    (url: string) => api.get<Order>(url)
  );
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [executing, setExecuting] = useState(false);

  if (!data) return <Skeleton />;

  const handleConfirm = async () => {
    await api.post(`/api/v1/orders/${orderId}/confirm`, {});
    mutate();
  };

  const handleExecute = async () => {
    setExecuting(true);
    try {
      await api.post(`/api/v1/orders/${orderId}/execute`, {
        confirm_execution: true,
        final_confirm: "EXECUTE",
      });
      mutate(); onRefresh(); setConfirmOpen(false);
    } catch (e: unknown) {
      if (e instanceof Error) alert(e.message);
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="space-y-3">
      <button onClick={onBack} className="flex items-center gap-1 text-npurple text-sm hover:text-npurple/80 transition-colors">
        ← 목록으로
      </button>

      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <span className={clsx("badge border", STATUS_COLOR[data.status] ?? "bg-elevated text-muted border-border")}>
            {STATUS_LABEL[data.status] ?? data.status}
          </span>
          <span className="text-xs text-muted font-mono">{data.created_at?.slice(0, 16)}</span>
        </div>
        <p className="font-bold text-lg text-text">{data.title}</p>
        {data.note && <p className="text-xs text-muted mt-1">{data.note}</p>}
      </div>

      <div className="space-y-2">
        {data.items.map((item, i) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="card"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={clsx("badge border",
                  item.action === "buy" ? "bg-npurple/20 text-npurple border-npurple/30" : "bg-nrose/20 text-nrose border-nrose/30"
                )}>
                  {item.action === "buy" ? "▲ 매수" : "▼ 매도"}
                </span>
                <span className="font-semibold text-text text-sm">{item.name}</span>
                <span className="text-xs text-muted font-mono">{item.symbol}</span>
              </div>
              <span className={clsx("badge border text-xs", STATUS_COLOR[item.status] ?? "bg-elevated text-muted border-border")}>
                {item.status}
              </span>
            </div>
            <div className="flex gap-4 mt-1.5 text-xs text-muted font-mono">
              <span>{item.quantity.toLocaleString()}주</span>
              {item.price && <span>₩{item.price.toLocaleString()}</span>}
              {item.amount && <span className="text-text">≈₩{(item.amount / 10_000).toFixed(0)}만</span>}
            </div>
            {item.reason && <p className="text-xs text-muted mt-1">{item.reason}</p>}
          </motion.div>
        ))}
      </div>

      <div className="flex gap-2 pt-1">
        {data.status === "draft" && (
          <button onClick={handleConfirm} className="btn-primary flex-1">1차 확인</button>
        )}
        {data.status === "confirmed" && (
          <button onClick={() => setConfirmOpen(true)} className="btn-danger flex-1">
            실주문 실행
          </button>
        )}
      </div>

      <AnimatePresence>
        {confirmOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end"
            style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}
            onClick={() => setConfirmOpen(false)}
          >
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", stiffness: 400, damping: 35 }}
              className="w-full max-w-2xl mx-auto rounded-t-3xl p-6"
              style={{ background: "#1A1028", border: "1px solid rgba(251,113,133,0.3)", borderBottom: "none" }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-10 h-1 bg-border rounded-full mx-auto mb-4" />
              <div className="flex items-center gap-2 mb-3">
                <span className="text-nrose text-xl">⚠</span>
                <h3 className="text-lg font-bold text-nrose">실전 계좌 주문</h3>
              </div>
              <p className="text-sm text-text mb-1">
                이 작업은 <strong className="text-nrose">실제 계좌에 실주문을 전송</strong>합니다.
              </p>
              <p className="text-xs text-muted mb-5">
                총 {data.items.length}건의 주문이 키움 API를 통해 즉시 전송됩니다.
              </p>
              <div className="flex gap-3">
                <button onClick={() => setConfirmOpen(false)} className="btn-ghost flex-1">취소</button>
                <button
                  onClick={handleExecute}
                  disabled={executing}
                  className="btn-danger flex-1"
                >
                  {executing ? (
                    <span className="flex items-center gap-2">
                      <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      전송 중...
                    </span>
                  ) : "실주문 확정"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="card h-16 animate-pulse" />
      ))}
    </div>
  );
}
