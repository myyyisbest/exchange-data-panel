/** 格式化汇率数值（展示原始官网单位） */
export function fmtRate(v: number | null | undefined, unit?: number): string {
  if (v == null) return "--";
  const n = Number(v) * (unit || 1);
  if (n >= 10000)
    return n.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  if (n >= 100)
    return n.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
  if (n >= 10)
    return n.toLocaleString("en-US", {
      minimumFractionDigits: 4,
      maximumFractionDigits: 4,
    });
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  });
}

export function changeClass(pct: number | null | undefined): string {
  if (pct == null) return "flat";
  if (pct > 0.001) return "up";
  if (pct < -0.001) return "down";
  return "flat";
}

export function changeArrow(cls: string): string {
  if (cls === "up") return "▲";
  if (cls === "down") return "▼";
  return "";
}
