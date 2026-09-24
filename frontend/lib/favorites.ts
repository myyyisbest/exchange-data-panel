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
};

export const BASE_LABELS: Record<string, string> = {
  CNY: "人民币 CNY",
  IDR: "印尼盾 IDR",
  HKD: "港币 HKD",
};

export const BASE_ICONS: Record<string, string> = {
  CNY: "¥",
  IDR: "Rp",
  HKD: "HK$",
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
