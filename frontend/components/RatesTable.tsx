"use client";

import { useMemo, useState } from "react";
import { FAVORITE_CURRENCIES } from "@/lib/favorites";
import { changeArrow, changeClass, fmtRate } from "@/lib/format";
import type { UnifiedRow } from "@/lib/types";

type SortKey = "base" | "target" | "rate" | "change" | "pct";

interface Props {
  rows: UnifiedRow[];
  baseFilter: string;
  favoriteOnly: boolean;
  dateLabel?: string | null;
  loading?: boolean;
}

export default function RatesTable({
  rows,
  baseFilter,
  favoriteOnly,
  dateLabel,
  loading,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey | null>("pct");
  const [sortDir, setSortDir] = useState<-1 | 1>(-1);

  const display = useMemo(() => {
    let list = baseFilter
      ? rows.filter((r) => r.base === baseFilter)
      : rows.slice();
    if (favoriteOnly) {
      list = list.filter((r) => FAVORITE_CURRENCIES.has(r.target));
    }
    if (sortKey) {
      const dir = sortDir;
      list = [...list].sort((a, b) => {
        let va: string | number | null | undefined;
        let vb: string | number | null | undefined;
        switch (sortKey) {
          case "base":
            va = a.base;
            vb = b.base;
            break;
          case "target":
            va = a.target;
            vb = b.target;
            break;
          case "rate":
            va = a.rate ?? -Infinity;
            vb = b.rate ?? -Infinity;
            break;
          case "change":
            va = a.diff ?? -Infinity;
            vb = b.diff ?? -Infinity;
            break;
          case "pct":
            va = a.pct ?? -Infinity;
            vb = b.pct ?? -Infinity;
            break;
        }
        if (typeof va === "string" && typeof vb === "string") {
          return va.localeCompare(vb) * dir;
        }
        return ((va as number) - (vb as number)) * dir;
      });
    }
    return list;
  }, [rows, baseFilter, favoriteOnly, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(-1);
    }
  }

  function sortIcon(key: SortKey) {
    if (sortKey !== key) return "⇅";
    return sortDir === 1 ? "↑" : "↓";
  }

  const thClass =
    "cursor-pointer select-none whitespace-nowrap px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-400 hover:text-zinc-200";

  return (
    <section className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/60 shadow-lg shadow-black/20">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-zinc-100">最新汇率</h2>
        <div className="text-xs text-zinc-400">
          日期：
          <span className="ml-1 font-mono text-emerald-400">
            {dateLabel || "--"}
          </span>
          <span className="ml-3 text-zinc-500">共 {display.length} 行</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-950/80">
            <tr>
              <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-zinc-500">
                #
              </th>
              <th className={thClass} onClick={() => toggleSort("base")}>
                基座 {sortIcon("base")}
              </th>
              <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-zinc-500">
                基座名称
              </th>
              <th className={thClass} onClick={() => toggleSort("target")}>
                货币 {sortIcon("target")}
              </th>
              <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-zinc-500">
                货币名称
              </th>
              <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-zinc-500">
                报价
              </th>
              <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-zinc-500">
                单位
              </th>
              <th
                className={thClass + " text-right!"}
                onClick={() => toggleSort("rate")}
              >
                汇率 {sortIcon("rate")}
              </th>
              <th
                className={thClass + " text-right!"}
                onClick={() => toggleSort("change")}
              >
                涨跌 {sortIcon("change")}
              </th>
              <th
                className={thClass + " text-right!"}
                onClick={() => toggleSort("pct")}
              >
                涨跌幅 {sortIcon("pct")}
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={10}
                  className="px-4 py-10 text-center text-zinc-500"
                >
                  加载中…
                </td>
              </tr>
            ) : display.length === 0 ? (
              <tr>
                <td
                  colSpan={10}
                  className="px-4 py-10 text-center text-zinc-500"
                >
                  {favoriteOnly
                    ? "当前筛选下没有常用币种数据（关闭 ⭐ 可查看全部）"
                    : "暂无数据（请确认 Flask API 已启动）"}
                </td>
              </tr>
            ) : (
              display.map((r, idx) => {
                const cls = changeClass(r.pct);
                const color =
                  cls === "up"
                    ? "text-rose-400"
                    : cls === "down"
                      ? "text-emerald-400"
                      : "text-zinc-400";
                const unitLabel = r.unit === 100 ? "100" : "1";
                const favMark =
                  !favoriteOnly && FAVORITE_CURRENCIES.has(r.target) ? (
                    <span className="ml-1 text-amber-400" title="常用币种">
                      ★
                    </span>
                  ) : null;
                return (
                  <tr
                    key={`${r.base}-${r.target}-${idx}`}
                    className="border-t border-zinc-800/80 hover:bg-zinc-800/40"
                  >
                    <td className="px-3 py-2 text-xs text-zinc-500">
                      {idx + 1}
                    </td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-sky-300">
                        {r.base}
                      </span>
                      {favMark}
                    </td>
                    <td className="px-3 py-2 text-zinc-400">{r.base_name}</td>
                    <td className="px-3 py-2 font-mono text-xs text-zinc-100">
                      {r.target}
                      {favMark}
                    </td>
                    <td className="px-3 py-2 text-zinc-300">{r.target_name}</td>
                    <td className="px-3 py-2">
                      <span className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-400">
                        {r.quote_method_label}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-zinc-400">{unitLabel}</td>
                    <td className="px-3 py-2 text-right font-mono text-zinc-100">
                      {fmtRate(r.rate, r.unit)}
                    </td>
                    <td className={`px-3 py-2 text-right font-mono ${color}`}>
                      {r.diff != null
                        ? `${r.diff > 0 ? "+" : ""}${(r.diff * (r.unit || 1)).toFixed(4)}`
                        : "--"}
                    </td>
                    <td className={`px-3 py-2 text-right font-mono ${color}`}>
                      {r.pct != null
                        ? `${changeArrow(cls)}${r.pct > 0 ? "+" : ""}${r.pct.toFixed(3)}%`
                        : "--"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
