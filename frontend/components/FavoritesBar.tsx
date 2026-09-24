"use client";

import { FAVORITE_CURRENCIES } from "@/lib/favorites";

interface Props {
  favoriteOnly: boolean;
  onToggle: () => void;
}

export default function FavoritesBar({ favoriteOnly, onToggle }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        aria-pressed={favoriteOnly}
        onClick={onToggle}
        className={[
          "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
          favoriteOnly
            ? "border-amber-500/50 bg-amber-500/15 text-amber-300"
            : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-600",
        ].join(" ")}
      >
        <span aria-hidden>⭐</span>
        <span>{favoriteOnly ? "仅常用币种" : "显示全部币种"}</span>
        <span className="text-zinc-500">({FAVORITE_CURRENCIES.size})</span>
      </button>
      <p className="text-[11px] text-zinc-500">
        常用：{Array.from(FAVORITE_CURRENCIES).join(" · ")}
      </p>
    </div>
  );
}
