"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import BaseSwitcher from "@/components/BaseSwitcher";
import ComparePanel from "@/components/ComparePanel";
import CrawlButton from "@/components/CrawlButton";
import FavoritesBar from "@/components/FavoritesBar";
import RatesTable from "@/components/RatesTable";
import ToastStack, { type ToastItem, type ToastType } from "@/components/Toast";
import { getStats, getUnifiedLatest } from "@/lib/api";
import { loadFavoriteOnly, saveFavoriteOnly } from "@/lib/favorites";
import type { BaseCode, UnifiedRow } from "@/lib/types";

export default function Dashboard() {
  const [rows, setRows] = useState<UnifiedRow[]>([]);
  const [dateLabel, setDateLabel] = useState<string | null>(null);
  const [baseDates, setBaseDates] = useState<Record<string, string | null>>({});
  const [baseFilter, setBaseFilter] = useState<BaseCode | "">("");
  const [favoriteOnly, setFavoriteOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [statsLine, setStatsLine] = useState("—");
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastId = useRef(0);

  const pushToast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++toastId.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [data, stats] = await Promise.all([
        getUnifiedLatest(),
        getStats().catch(() => null),
      ]);
      setRows(data.rows || []);
      setDateLabel(data.date);
      setBaseDates(data.base_dates || {});
      if (stats) {
        const dates = Object.values(stats.sources || {})
          .map((x) => x.latest_date)
          .filter(Boolean) as string[];
        const maxDate = dates.length
          ? dates.reduce((a, b) => (a > b ? a : b))
          : "--";
        const total = Object.values(stats.sources || {}).reduce(
          (acc, x) => acc + (x.total_records || 0),
          0
        );
        const crawl = `${String(stats.crawl_hour).padStart(2, "0")}:${String(stats.crawl_minute).padStart(2, "0")}`;
        setStatsLine(
          `最新 ${maxDate} · 共 ${total.toLocaleString()} 条 · 定时 ${crawl}`
        );
      }
    } catch (e) {
      setRows([]);
      setDateLabel(null);
      pushToast(
        e instanceof Error
          ? `加载失败：${e.message}（请确认 Flask 已在 41010 端口运行）`
          : "加载失败",
        "err"
      );
    } finally {
      setLoading(false);
    }
  }, [pushToast]);

  useEffect(() => {
    setFavoriteOnly(loadFavoriteOnly());
    refresh();
  }, [refresh]);

  function toggleFavorite() {
    setFavoriteOnly((prev) => {
      const next = !prev;
      saveFavoriteOnly(next);
      return next;
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-zinc-800 bg-gradient-to-br from-zinc-900 to-zinc-950 p-5 shadow-xl shadow-black/30">
        <div>
          <p className="text-[11px] font-medium tracking-wider text-emerald-400 uppercase">
            Exchange Data Panel
          </p>
          <h1 className="mt-1 text-xl font-bold text-zinc-50 sm:text-2xl">
            汇率数据面板
          </h1>
          <p className="mt-1 text-xs text-zinc-400">
            SAFE / BI / HKAB / Frankfurter · 多基座统一视图 · Next.js 前端
          </p>
          <p className="mt-2 font-mono text-[11px] text-zinc-500">{statsLine}</p>
          {Object.keys(baseDates).length > 0 && (
            <p className="mt-1 text-[11px] text-zinc-500">
              各源日期：
              {Object.entries(baseDates)
                .map(([k, v]) => `${k}=${v || "--"}`)
                .join(" · ")}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <CrawlButton onDone={refresh} onToast={pushToast} />
          <button
            type="button"
            onClick={refresh}
            className="text-[11px] text-zinc-400 underline-offset-2 hover:text-zinc-200 hover:underline"
          >
            刷新数据
          </button>
        </div>
      </header>

      <div className="flex flex-col gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 sm:flex-row sm:items-center sm:justify-between">
        <BaseSwitcher
          value={baseFilter}
          onChange={setBaseFilter}
          label="表格基座"
          allowAll
        />
        <FavoritesBar favoriteOnly={favoriteOnly} onToggle={toggleFavorite} />
      </div>

      <RatesTable
        rows={rows}
        baseFilter={baseFilter}
        favoriteOnly={favoriteOnly}
        dateLabel={dateLabel}
        loading={loading}
      />

      <ComparePanel onToast={pushToast} />

      <footer className="pb-4 text-center text-[11px] text-zinc-600">
        API 经 Next.js 代理至 Flask（默认{" "}
        <code className="text-zinc-500">http://127.0.0.1:41010</code>
        ）。旧版模板界面仍可由 Flask 直接提供。
      </footer>

      <ToastStack items={toasts} onDismiss={dismissToast} />
    </div>
  );
}
