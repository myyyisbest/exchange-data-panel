"use client";

import { BASE_ICONS, BASE_LABELS } from "@/lib/favorites";
import type { BaseCode } from "@/lib/types";

const BASES: Array<BaseCode | ""> = ["", "CNY", "IDR", "HKD", "USD"];

interface Props {
  value: BaseCode | "";
  onChange: (base: BaseCode | "") => void;
  label?: string;
  allowAll?: boolean;
}

export default function BaseSwitcher({
  value,
  onChange,
  label = "基座筛选",
  allowAll = true,
}: Props) {
  const options = allowAll ? BASES : (["CNY", "IDR", "HKD", "USD"] as BaseCode[]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-zinc-400">{label}</span>
      <div className="inline-flex rounded-lg border border-zinc-700/80 bg-zinc-900/80 p-0.5">
        {options.map((b) => {
          const active = value === b;
          const key = b || "ALL";
          const text =
            b === ""
              ? "全部"
              : `${BASE_ICONS[b] || ""} ${BASE_LABELS[b] || b}`;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onChange(b as BaseCode | "")}
              className={[
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                active
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-zinc-300 hover:bg-zinc-800 hover:text-white",
              ].join(" ")}
            >
              {text}
            </button>
          );
        })}
      </div>
    </div>
  );
}
