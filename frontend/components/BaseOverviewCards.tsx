"use client";

import {
  BASE_META,
  CARD_HIGHLIGHT_TARGETS,
  MARKET_BASES,
  OFFICIAL_BASES,
} from "@/lib/favorites";
import { changeArrow, changeClass, fmtRate } from "@/lib/format";
import type { BaseCode, UnifiedRow } from "@/lib/types";

interface Props {
  rows: UnifiedRow[];
  baseDates: Record<string, string | null>;
  loading?: boolean;
  onSelect: (base: BaseCode) => void;
}

const ACCENT = {
  emerald: {
    ring: "hover:border-emerald-500/50 hover:shadow-emerald-900/30",
    glow: "from-emerald-500/15 via-transparent to-transparent",
    icon: "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30",
    badge: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/25",
    bar: "bg-emerald-500",
  },
  cyan: {
    ring: "hover:border-cyan-500/50 hover:shadow-cyan-900/30",
    glow: "from-cyan-500/15 via-transparent to-transparent",
    icon: "bg-cyan-500/20 text-cyan-300 ring-cyan-500/30",
    badge: "bg-cyan-500/15 text-cyan-300 ring-cyan-500/25",
    bar: "bg-cyan-500",
  },
  sky: {
    ring: "hover:border-sky-500/50 hover:shadow-sky-900/30",
    glow: "from-sky-500/15 via-transparent to-transparent",
    icon: "bg-sky-500/20 text-sky-300 ring-sky-500/30",
    badge: "bg-sky-500/15 text-sky-300 ring-sky-500/25",
    bar: "bg-sky-500",
  },
  violet: {
    ring: "hover:border-violet-500/50 hover:shadow-violet-900/30",
    glow: "from-violet-500/20 via-fuchsia-500/5 to-transparent",
    icon: "bg-violet-500/20 text-violet-300 ring-violet-500/30",
    badge: "bg-violet-500/20 text-violet-200 ring-violet-400/40",
    bar: "bg-violet-500",
  },
} as const;

function pickHighlights(base: string, rows: UnifiedRow[]): UnifiedRow[] {
  const forBase = rows.filter((r) => r.base === base);
  if (!forBase.length) return [];
  const preferred = CARD_HIGHLIGHT_TARGETS[base] || [];
  const byTarget = new Map(forBase.map((r) => [r.target, r]));
  const picked: UnifiedRow[] = [];
  for (const code of preferred) {
    const row = byTarget.get(code);
    if (row) picked.push(row);
    if (picked.length >= 4) break;
  }
  if (picked.length < 4) {
    const rest = [...forBase]
      .filter((r) => !picked.some((p) => p.target === r.target))
      .sort((a, b) => Math.abs(b.pct ?? 0) - Math.abs(a.pct ?? 0));
    for (const r of rest) {
      picked.push(r);
      if (picked.length >= 4) break;
    }
  }
  return picked;
}

function SkeletonCard({ market }: { market?: boolean }) {
  return (
    <div
      className={[
        "relative overflow-hidden rounded-2xl border bg-zinc-900/60 p-5",
        market
          ? "border-violet-500/20 border-dashed"
          : "border-zinc-800",
      ].join(" ")}
    >
      <div className="animate-pulse space-y-4">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-zinc-800" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-24 rounded bg-zinc-800" />
            <div className="h-3 w-16 rounded bg-zinc-800/80" />
          </div>
        </div>
        <div className="h-3 w-32 rounded bg-zinc-800/70" />
        <div className="space-y-2 pt-1">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex justify-between gap-2">
              <div className="h-3 w-12 rounded bg-zinc-800" />
              <div className="h-3 w-16 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BaseCard({
  base,
  rows,
  date,
  onSelect,
}: {
  base: BaseCode;
  rows: UnifiedRow[];
  date: string | null;
  onSelect: (base: BaseCode) => void;
}) {
  const meta = BASE_META[base];
  const accent = ACCENT[meta.accent];
  const highlights = pickHighlights(base, rows);
  const isMarket = meta.kind === "market";

  return (
    <button
      type="button"
      onClick={() => onSelect(base)}
      className={[
        "group relative flex w-full flex-col overflow-hidden rounded-2xl border bg-zinc-900/70 p-5 text-left shadow-lg shadow-black/25 transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
        isMarket
          ? "border-violet-500/35 border-dashed focus-visible:ring-violet-500"
          : "border-zinc-800 focus-visible:ring-emerald-500",
        accent.ring,
        "hover:-translate-y-0.5 hover:shadow-xl",
      ].join(" ")}
    >
      <div
        className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${accent.glow} opacity-80`}
      />
      <div className={`absolute top-0 left-0 h-full w-1 ${accent.bar}`} />

      <div className="relative flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-11 w-11 items-center justify-center rounded-xl font-mono text-lg font-bold ring-1 ${accent.icon}`}
          >
            {meta.icon}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-zinc-50">
                {meta.shortName}
              </h3>
              <span className="font-mono text-xs text-zinc-400">{base}</span>
            </div>
            <p className="mt-0.5 text-[11px] text-zinc-500">{meta.source}</p>
          </div>
        </div>
        {meta.badge ? (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide ring-1 ${accent.badge}`}
          >
            {meta.badge}
          </span>
        ) : (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${accent.badge}`}
          >
            官方源
          </span>
        )}
      </div>

      <div className="relative mt-4 flex flex-wrap items-center gap-2 text-[11px]">
        <span
          className={`rounded-md px-2 py-0.5 font-medium ring-1 ${accent.badge}`}
        >
          {meta.priceType}
        </span>
        <span className="font-mono text-zinc-500">
          最新 {date || "—"}
        </span>
      </div>

      <div className="relative mt-4 flex-1 space-y-1.5 border-t border-zinc-800/80 pt-3">
        {highlights.length === 0 ? (
          <p className="py-2 text-xs text-zinc-600">暂无汇率数据</p>
        ) : (
          highlights.map((r) => {
            const cls = changeClass(r.pct);
            const color =
              cls === "up"
                ? "text-rose-400"
                : cls === "down"
                  ? "text-emerald-400"
                  : "text-zinc-500";
            return (
              <div
                key={r.target}
                className="flex items-center justify-between gap-2 text-xs"
              >
                <span className="font-mono text-zinc-300">{r.target}</span>
                <span className="flex items-center gap-2 font-mono">
                  <span className="text-zinc-400">
                    {fmtRate(r.rate, r.unit)}
                  </span>
                  <span className={`min-w-[4.5rem] text-right ${color}`}>
                    {r.pct != null
                      ? `${changeArrow(cls)}${r.pct > 0 ? "+" : ""}${r.pct.toFixed(2)}%`
                      : "—"}
                  </span>
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="relative mt-4 flex items-center justify-between text-[11px] text-zinc-500 transition group-hover:text-zinc-300">
        <span>查看详情 · 表格 / 趋势 / 对比</span>
        <span className="text-zinc-400 group-hover:translate-x-0.5 group-hover:text-zinc-200">
          →
        </span>
      </div>
    </button>
  );
}

export default function BaseOverviewCards({
  rows,
  baseDates,
  loading,
  onSelect,
}: Props) {
  if (loading) {
    return (
      <div className="space-y-8">
        <section>
          <SectionHead
            title="官方基座"
            subtitle="SAFE · BI · HKAB · 官方报价，不宜与市场中间价直接比绝对水平"
            accent="official"
          />
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </section>
        <section>
          <SectionHead
            title="市场参考"
            subtitle="Frankfurter · 市场中间价，仅作参考对照"
            accent="market"
          />
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SkeletonCard market />
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section>
        <SectionHead
          title="官方基座"
          subtitle="SAFE · BI · HKAB · 官方报价，不宜与市场中间价直接比绝对水平"
          accent="official"
        />
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {OFFICIAL_BASES.map((code) => (
            <BaseCard
              key={code}
              base={code}
              rows={rows}
              date={baseDates[code] ?? null}
              onSelect={onSelect}
            />
          ))}
        </div>
      </section>

      <section>
        <SectionHead
          title="市场参考"
          subtitle="Frankfurter · 市场中间价，仅作参考对照 · 勿与官方报价直接比绝对水平"
          accent="market"
        />
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MARKET_BASES.map((code) => (
            <BaseCard
              key={code}
              base={code}
              rows={rows}
              date={baseDates[code] ?? null}
              onSelect={onSelect}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function SectionHead({
  title,
  subtitle,
  accent,
}: {
  title: string;
  subtitle: string;
  accent: "official" | "market";
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div>
        <div className="flex items-center gap-2">
          <span
            className={[
              "inline-block h-2 w-2 rounded-full",
              accent === "official" ? "bg-emerald-400" : "bg-violet-400",
            ].join(" ")}
          />
          <h2 className="text-sm font-semibold tracking-wide text-zinc-100">
            {title}
          </h2>
        </div>
        <p className="mt-1 max-w-2xl text-[11px] leading-relaxed text-zinc-500">
          {subtitle}
        </p>
      </div>
    </div>
  );
}
