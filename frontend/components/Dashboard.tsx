"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import BaseOverviewCards from "@/components/BaseOverviewCards";
import BaseSwitcher from "@/components/BaseSwitcher";
import ComparePanel from "@/components/ComparePanel";
import CrawlButton from "@/components/CrawlButton";
import FavoritesBar from "@/components/FavoritesBar";
import RatesTable from "@/components/RatesTable";
import ToastStack, { type ToastItem, type ToastType } from "@/components/Toast";
import { getStats, getUnifiedLatest } from "@/lib/api";
import {
  BASE_META,
  loadFavoriteOnly,
  saveFavoriteOnly,
} from "@/lib/favorites";
import type { BaseCode, UnifiedRow } from "@/lib/types";

export default function Dashboard() {
  const [rows, setRows] = useState<UnifiedRow[]>([]);
  const [dateLabel, setDateLabel] = useState<string | null>(null);
  const [baseDates, setBaseDates] = useState<Record<string, string | null>>(
    {}
  );
  /** null = 概览；有值 = 该基座详情 */
  const [selectedBase, setSelectedBase] = useState<BaseCode | null>(null);
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

  const detailMeta = selectedBase ? BASE_META[selectedBase] : null;
  const isMarketDetail = detailMeta?.kind === "market";

  return (
    <div className="relative min-h-full">
      {/* 背景氛围 */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -top-32 left-1/4 h-72 w-72 rounded-full bg-emerald-600/10 blur-3xl" />
        <div className="absolute top-40 right-0 h-80 w-80 rounded-full bg-sky-600/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-violet-600/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:py-8">
        <header className="overflow-hidden rounded-2xl border border-zinc-800/80 bg-zinc-900/70 p-5 shadow-xl shadow-black/40 backdrop-blur-sm sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold tracking-[0.14em] text-emerald-400 uppercase">
                Exchange Data Panel
              </p>
              <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-zinc-50 sm:text-3xl">
                汇率数据面板
              </h1>
              <p className="mt-1.5 max-w-xl text-xs leading-relaxed text-zinc-400">
                官方三源（SAFE / BI / HKAB）与 Frankfurter 市场参考 · 先选基座，再看表格、趋势与对比
              </p>
              <p className="mt-3 font-mono text-[11px] text-zinc-500">
                {statsLine}
              </p>
              {Object.keys(baseDates).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {Object.entries(baseDates).map(([k, v]) => {
                    const m = BASE_META[k];
                    const market = m?.kind === "market";
                    return (
                      <span
                        key={k}
                        className={[
                          "rounded-md px-1.5 py-0.5 font-mono text-[10px] ring-1",
                          market
                            ? "bg-violet-500/10 text-violet-300 ring-violet-500/25"
                            : "bg-zinc-800/80 text-zinc-400 ring-zinc-700/60",
                        ].join(" ")}
                      >
                        {k} {v || "--"}
                      </span>
                    );
                  })}
                </div>
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
          </div>
        </header>

        {selectedBase === null ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-zinc-100">基座概览</h2>
                <p className="mt-0.5 text-[11px] text-zinc-500">
                  点击卡片进入详情 · 官方源与市场参考分区展示
                </p>
              </div>
            </div>
            <BaseOverviewCards
              rows={rows}
              baseDates={baseDates}
              loading={loading}
              onSelect={setSelectedBase}
            />
          </>
        ) : (
          <DetailView
            base={selectedBase}
            rows={rows}
            dateLabel={
              baseDates[selectedBase] || dateLabel
            }
            loading={loading}
            favoriteOnly={favoriteOnly}
            onToggleFavorite={toggleFavorite}
            onBack={() => setSelectedBase(null)}
            onChangeBase={setSelectedBase}
            onToast={pushToast}
            isMarket={!!isMarketDetail}
          />
        )}

        <footer className="pb-6 text-center text-[11px] text-zinc-600">
          API 经 Next.js 代理至 Flask（默认{" "}
          <code className="text-zinc-500">http://127.0.0.1:41010</code>
          ）。旧版模板界面仍可由 Flask 直接提供。
        </footer>
      </div>

      <ToastStack items={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function DetailView({
  base,
  rows,
  dateLabel,
  loading,
  favoriteOnly,
  onToggleFavorite,
  onBack,
  onChangeBase,
  onToast,
  isMarket,
}: {
  base: BaseCode;
  rows: UnifiedRow[];
  dateLabel: string | null;
  loading: boolean;
  favoriteOnly: boolean;
  onToggleFavorite: () => void;
  onBack: () => void;
  onChangeBase: (b: BaseCode) => void;
  onToast: (msg: string, type?: ToastType) => void;
  isMarket: boolean;
}) {
  const meta = BASE_META[base];

  return (
    <div className="space-y-5">
      {/* 详情顶栏 */}
      <div
        className={[
          "overflow-hidden rounded-2xl border p-4 sm:p-5",
          isMarket
            ? "border-violet-500/35 border-dashed bg-violet-950/20"
            : "border-zinc-800 bg-zinc-900/60",
        ].join(" ")}
      >
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
          >
            ← 返回概览
          </button>

          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 sm:gap-3">
            <span
              className={[
                "flex h-9 w-9 items-center justify-center rounded-lg font-mono text-sm font-bold ring-1",
                isMarket
                  ? "bg-violet-500/20 text-violet-300 ring-violet-500/40"
                  : "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30",
              ].join(" ")}
            >
              {meta.icon}
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-zinc-50">
                  {meta.fullLabel}
                </h2>
                {meta.badge && (
                  <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-200 ring-1 ring-violet-400/40">
                    {meta.badge}
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-[11px] text-zinc-500">
                {meta.source} · {meta.priceType} · 最新{" "}
                <span className="font-mono text-zinc-400">
                  {dateLabel || "—"}
                </span>
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 border-t border-zinc-800/80 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <BaseSwitcher
            value={base}
            onChange={(b) => {
              if (b) onChangeBase(b);
            }}
            label="切换基座"
            allowAll={false}
          />
          <FavoritesBar
            favoriteOnly={favoriteOnly}
            onToggle={onToggleFavorite}
          />
        </div>
      </div>

      <RatesTable
        rows={rows}
        baseFilter={base}
        favoriteOnly={favoriteOnly}
        dateLabel={dateLabel}
        loading={loading}
        compactBase
      />

      <ComparePanel onToast={onToast} lockedBase={base} />
    </div>
  );
}
