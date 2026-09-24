"use client";

export type ToastType = "ok" | "warn" | "err" | "info";

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

const COLORS: Record<ToastType, string> = {
  ok: "border-emerald-500/40 bg-emerald-950/90 text-emerald-200",
  warn: "border-amber-500/40 bg-amber-950/90 text-amber-200",
  err: "border-rose-500/40 bg-rose-950/90 text-rose-200",
  info: "border-sky-500/40 bg-sky-950/90 text-sky-200",
};

interface Props {
  items: ToastItem[];
  onDismiss: (id: number) => void;
}

export default function ToastStack({ items, onDismiss }: Props) {
  if (!items.length) return null;
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-80 flex-col gap-2">
      {items.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onDismiss(t.id)}
          className={`pointer-events-auto rounded-lg border px-3 py-2 text-left text-xs shadow-lg backdrop-blur ${COLORS[t.type]}`}
        >
          {t.message}
        </button>
      ))}
    </div>
  );
}
