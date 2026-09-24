/** 常用币种（与旧 static/js/app.js 一致） */
export const FAVORITE_CURRENCIES = new Set([
  "AED",
  "CNY",
  "EUR",
  "GBP",
  "HKD",
  "IDR",
  "JPY",
  "KRW",
  "SGD",
  "USD",
]);

export const FAV_STORAGE_KEY = "exchange.favoriteOnly.v1";

export const BASE_DEFAULTS: Record<string, string[]> = {
  CNY: ["USD", "EUR", "JPY", "GBP", "AUD"],
  IDR: ["USD", "EUR", "JPY", "SGD", "AUD"],
  HKD: ["USD", "EUR", "JPY", "GBP", "AUD"],
  USD: ["CNY", "EUR", "JPY", "HKD", "SGD"],
};

export const BASE_LABELS: Record<string, string> = {
  CNY: "人民币 CNY",
  IDR: "印尼盾 IDR",
  HKD: "港币 HKD",
  USD: "美元 USD · 市场中间价",
};

export const BASE_ICONS: Record<string, string> = {
  CNY: "¥",
  IDR: "Rp",
  HKD: "HK$",
  USD: "$",
};

/** 基座视觉与文案元数据（概览卡片 / 详情头） */
export type BaseKind = "official" | "market";

export interface BaseMeta {
  code: string;
  shortName: string;
  fullLabel: string;
  icon: string;
  priceType: string;
  source: string;
  kind: BaseKind;
  /** Tailwind 语义色名，用于卡片强调 */
  accent: "emerald" | "cyan" | "sky" | "violet";
  badge?: string;
}

export const BASE_META: Record<string, BaseMeta> = {
  CNY: {
    code: "CNY",
    shortName: "人民币",
    fullLabel: "人民币 CNY",
    icon: "¥",
    priceType: "官方中间价",
    source: "SAFE",
    kind: "official",
    accent: "emerald",
  },
  IDR: {
    code: "IDR",
    shortName: "印尼盾",
    fullLabel: "印尼盾 IDR",
    icon: "Rp",
    priceType: "官方卖出价",
    source: "Bank Indonesia",
    kind: "official",
    accent: "cyan",
  },
  HKD: {
    code: "HKD",
    shortName: "港币",
    fullLabel: "港币 HKD",
    icon: "HK$",
    priceType: "官方卖出价",
    source: "HKAB",
    kind: "official",
    accent: "sky",
  },
  USD: {
    code: "USD",
    shortName: "美元",
    fullLabel: "美元 USD",
    icon: "$",
    priceType: "市场中间价",
    source: "Frankfurter",
    kind: "market",
    accent: "violet",
    badge: "市场参考",
  },
};

export const OFFICIAL_BASES = ["CNY", "IDR", "HKD"] as const;
export const MARKET_BASES = ["USD"] as const;
export const ALL_BASES = ["CNY", "IDR", "HKD", "USD"] as const;

/** 概览卡片上优先展示的目标货币（按基座） */
export const CARD_HIGHLIGHT_TARGETS: Record<string, string[]> = {
  CNY: ["USD", "EUR", "JPY", "GBP", "HKD"],
  IDR: ["USD", "EUR", "JPY", "SGD", "CNY"],
  HKD: ["USD", "EUR", "JPY", "CNY", "GBP"],
  USD: ["CNY", "EUR", "JPY", "HKD", "SGD"],
};

export function loadFavoriteOnly(): boolean {
  try {
    const v = localStorage.getItem(FAV_STORAGE_KEY);
    if (v === "0" || v === "false") return false;
  } catch {
    /* ignore */
  }
  return true;
}

export function saveFavoriteOnly(value: boolean): void {
  try {
    localStorage.setItem(FAV_STORAGE_KEY, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}
