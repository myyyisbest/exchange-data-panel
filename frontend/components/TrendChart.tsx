"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getRecent } from "@/lib/api";
import type { BaseCode, CurrencyMeta } from "@/lib/types";

const PALETTE = ["#f43f5e", "#eab308", "#38bdf8", "#34d399", "#a78bfa"];
const DAY_OPTIONS = [7, 30, 90, 180];

interface Props {
  base: BaseCode;
  currencies: string[];
  currencyMeta: CurrencyMeta[];
  onToast?: (msg: string, type?: "ok" | "warn" | "err" | "info") => void;
}

export default function TrendChart({
  base,
  currencies,
  currencyMeta,
  onToast,
}: Props) {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [chartRows, setChartRows] = useState<
    Array<Record<string, string | number | null>>
  >([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!currencies.length) {
        setChartRows([]);
        return;
      }
      setLoading(true);
      try {
        const data = await getRecent(base, days);
        if (cancelled) return;
        if (!data.rows.length) {
          setChartRows([]);
          onToast?.("暂无趋势数据", "warn");
          return;
        }
        const first = data.rows[0];
        const mapped = data.rows.map((r) => {
          const point: Record<string, string | number | null> = {
            date: r.date,
          };
          for (const code of currencies) {
            const v = r[code];
            const baseVal = first[code];
            if (
              typeof v === "number" &&
              typeof baseVal === "number" &&
              baseVal !== 0
            ) {
              point[code] = +(((v - baseVal) / baseVal) * 100).toFixed(4);
            } else {
              point[code] = null;
            }
          }
          return point;
        });
        setChartRows(mapped);
      } catch (e) {
        if (!cancelled) {
          onToast?.(
            e instanceof Error ? e.message : "趋势图加载失败",
            "err"
          );
          setChartRows([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [base, currencies, days, onToast]);

  const nameMap = useMemo(() => {
    const m = new Map<string, string>();
    currencyMeta.forEach((c) => m.set(c.code, c.name));
    return m;
  }, [currencyMeta]);

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 shadow-lg shadow-black/20">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">趋势图</h2>
          <p className="mt-0.5 text-[11px] text-zinc-500">
            {base} 相对期初变化百分比（近 {days} 个交易日）
          </p>
        </div>
        <div className="inline-flex rounded-lg border border-zinc-700 bg-zinc-950 p-0.5">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={[
                "rounded-md px-2.5 py-1 text-xs font-medium transition",
                days === d
                  ? "bg-sky-600 text-white"
                  : "text-zinc-400 hover:text-zinc-200",
              ].join(" ")}
            >
              {d} 天
            </button>
          ))}
        </div>
      </div>

      <div className="h-72 w-full">
        {loading ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            加载趋势数据…
          </div>
        ) : chartRows.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            暂无数据
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#a1a1aa", fontSize: 10 }}
                minTickGap={28}
              />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                tickFormatter={(v: number) => `${v}%`}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(value, name) => {
                  const n = typeof value === "number" ? value : Number(value);
                  const label = `${name}（${nameMap.get(String(name)) || name}）`;
                  if (Number.isNaN(n)) return ["--", label];
                  return [`${n >= 0 ? "+" : ""}${n.toFixed(3)}%`, label];
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
                formatter={(value) =>
                  `${value} · ${nameMap.get(String(value)) || value}`
                }
              />
              {currencies.map((code, i) => (
                <Line
                  key={code}
                  type="monotone"
                  dataKey={code}
                  stroke={PALETTE[i % PALETTE.length]}
                  strokeWidth={2}
                  dot={chartRows.length > 100 ? false : { r: 2 }}
                  connectNulls
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
