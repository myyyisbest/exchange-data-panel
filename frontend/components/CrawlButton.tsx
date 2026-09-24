"use client";

import { useState } from "react";
import { crawl, crawlAll } from "@/lib/api";

interface Props {
  onDone?: () => void;
  onToast?: (msg: string, type?: "ok" | "warn" | "err" | "info") => void;
}

export default function CrawlButton({ onDone, onToast }: Props) {
  const [busy, setBusy] = useState<"one" | "all" | null>(null);

  async function runCrawl(mode: "one" | "all") {
    setBusy(mode);
    onToast?.(
      mode === "all" ? "正在抓取全部数据源..." : "正在抓取 CNY 今日数据...",
      "info"
    );
    try {
      const r =
        mode === "all"
          ? await crawlAll()
          : await crawl({ source: "CNY" });
      if (r.status === "success") {
        const extra =
          typeof r.inserted === "number" ? `，新增 ${r.inserted} 条` : "";
        onToast?.(`抓取成功${extra}`, "ok");
      } else if (r.status === "empty") {
        onToast?.(String(r.message || "无新数据"), "warn");
      } else {
        onToast?.(String(r.message || r.error || "抓取结束"), "info");
      }
      onDone?.();
    } catch (e) {
      onToast?.(e instanceof Error ? e.message : "抓取失败", "err");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        disabled={busy !== null}
        onClick={() => runCrawl("one")}
        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className={busy === "one" ? "animate-spin" : ""}>↻</span>
        {busy === "one" ? "抓取中..." : "抓取今日 (CNY)"}
      </button>
      <button
        type="button"
        disabled={busy !== null}
        onClick={() => runCrawl("all")}
        className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-600 bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-100 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className={busy === "all" ? "animate-spin" : ""}>⟳</span>
        {busy === "all" ? "抓取中..." : "抓取全部源 (含 USD)"}
      </button>
    </div>
  );
}
