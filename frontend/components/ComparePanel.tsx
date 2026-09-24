"use client";

import { useCallback, useEffect, useState } from "react";
import BaseSwitcher from "@/components/BaseSwitcher";
import TrendChart from "@/components/TrendChart";
import { getPreferences, getSources, savePreferences } from "@/lib/api";
import { BASE_DEFAULTS, BASE_META } from "@/lib/favorites";
import type { BaseCode, CurrencyMeta, SourcesResponse } from "@/lib/types";

interface Props {
  onToast?: (msg: string, type?: "ok" | "warn" | "err" | "info") => void;
  /** 详情页锁定基座时传入；未传则面板内可切换 */
  lockedBase?: BaseCode;
}

export default function ComparePanel({ onToast, lockedBase }: Props) {
  const [sources, setSources] = useState<SourcesResponse | null>(null);
  const [trendBase, setTrendBase] = useState<BaseCode>(lockedBase || "CNY");
  const [selected, setSelected] = useState<string[]>(
    BASE_DEFAULTS[lockedBase || "CNY"] || BASE_DEFAULTS.CNY
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (lockedBase) setTrendBase(lockedBase);
  }, [lockedBase]);

  const meta: CurrencyMeta[] = sources?.[trendBase]?.currency_meta || [];
  const baseMeta = BASE_META[trendBase];

  const applyDefaults = useCallback(
    (base: BaseCode, available: string[], prefs?: string[]) => {
      const fallback = (BASE_DEFAULTS[base] || available.slice(0, 5)).filter(
        (c) => available.includes(c)
      );
      const fromPref = (prefs || []).filter((c) => available.includes(c));
      setSelected(
        fromPref.length
          ? fromPref
          : fallback.length
            ? fallback
            : available.slice(0, 5)
      );
    },
    []
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await getSources();
        if (cancelled) return;
        setSources(s);
      } catch (e) {
        onToast?.(e instanceof Error ? e.message : "加载数据源失败", "err");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onToast]);

  useEffect(() => {
    if (!sources) return;
    let cancelled = false;
    const available = sources[trendBase]?.currencies || [];
    applyDefaults(trendBase, available);
    (async () => {
      try {
        const pref = await getPreferences(trendBase);
        if (cancelled) return;
        if (pref.currencies?.length) {
          applyDefaults(trendBase, available, pref.currencies);
        }
      } catch {
        /* 偏好接口不可用时保留本地默认 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sources, trendBase, applyDefaults]);

  function toggleCurrency(code: string) {
    setSelected((prev) => {
      if (prev.includes(code)) {
        if (prev.length <= 1) {
          onToast?.("至少保留一个货币", "warn");
          return prev;
        }
        return prev.filter((c) => c !== code);
      }
      if (prev.length >= 5) {
        onToast?.("最多对比 5 个货币", "warn");
        return prev;
      }
      return [...prev, code];
    });
  }

  async function handleSave() {
    if (!selected.length) {
      onToast?.("当前未选择任何货币", "warn");
      return;
    }
    setSaving(true);
    try {
      const r = await savePreferences(trendBase, selected);
      if (r.status === "success") {
        onToast?.(
          `已保存 ${trendBase} 的默认 ${r.count ?? selected.length} 个货币`,
          "ok"
        );
      } else {
        onToast?.(r.error || "保存失败", "err");
      }
    } catch (e) {
      onToast?.(e instanceof Error ? e.message : "保存失败", "err");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-5 shadow-lg shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">多币种对比</h2>
          <p className="mt-0.5 text-[11px] text-zinc-500">
            选择最多 5 个相对方货币，查看相对期初涨跌幅
            {baseMeta ? ` · ${baseMeta.priceType}` : ""}
          </p>
        </div>
        <button
          type="button"
          disabled={saving}
          onClick={handleSave}
          className="rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:bg-zinc-700 disabled:opacity-50"
        >
          {saving ? "保存中…" : "保存为默认偏好"}
        </button>
      </div>

      {!lockedBase && (
        <BaseSwitcher
          value={trendBase}
          onChange={(b) => {
            if (b) setTrendBase(b);
          }}
          label="趋势输入货币"
          allowAll={false}
        />
      )}

      <div>
        <div className="mb-2 text-xs text-zinc-400">相对方货币（最多 5 个）</div>
        <div className="flex flex-wrap gap-1.5">
          {meta.map((c) => {
            const active = selected.includes(c.code);
            return (
              <button
                key={c.code}
                type="button"
                title={c.name}
                onClick={() => toggleCurrency(c.code)}
                className={[
                  "rounded-md border px-2 py-1 font-mono text-[11px] transition",
                  active
                    ? "border-sky-500/60 bg-sky-500/20 text-sky-200"
                    : "border-zinc-700 bg-zinc-950 text-zinc-400 hover:border-zinc-500",
                ].join(" ")}
              >
                {c.code}
              </button>
            );
          })}
          {!meta.length && (
            <span className="text-xs text-zinc-500">
              暂无币种元数据（Flask 未连接时为空）
            </span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selected.map((code) => {
            const c = meta.find((x) => x.code === code);
            return (
              <span
                key={code}
                className="rounded-full bg-zinc-800 px-2.5 py-0.5 text-[11px] text-zinc-200"
              >
                {code}
                {c ? ` · ${c.name}` : ""}
              </span>
            );
          })}
        </div>
      </div>

      <TrendChart
        base={trendBase}
        currencies={selected}
        currencyMeta={meta}
        onToast={onToast}
      />
    </section>
  );
}
