/** 基座货币代码 */
export type BaseCode = "CNY" | "IDR" | "HKD";

export interface CurrencyMeta {
  code: string;
  name: string;
  quote_method: string;
  unit: number;
}

export interface SourceInfo {
  name: string;
  currency_count: number;
  currencies: string[];
  currency_meta: CurrencyMeta[];
}

export type SourcesResponse = Record<string, SourceInfo>;

/** 统一视图表格行（与 database._build_unified_rows 一致） */
export interface UnifiedRow {
  base: string;
  base_name: string;
  target: string;
  target_name: string;
  quote_method: string;
  quote_method_label: string;
  unit: number;
  rate: number;
  prev_rate: number | null;
  prev_date: string | null;
  diff: number | null;
  pct: number | null;
}

export interface UnifiedLatestResponse {
  date: string | null;
  base_dates: Record<string, string | null>;
  available_bases: string[];
  rows: UnifiedRow[];
}

export interface UnifiedDateResponse {
  date: string;
  available_bases: string[];
  rows: UnifiedRow[];
}

/** /api/recent 行：date + 各货币代码字段 */
export interface RecentRow {
  date: string;
  [currencyCode: string]: string | number | null | undefined;
}

export interface RecentResponse {
  days: number;
  count: number;
  rows: RecentRow[];
}

export interface PreferencesResponse {
  base: string;
  currencies: string[];
  updated_at: string | null;
}

export interface SavePreferencesResponse {
  status: string;
  base?: string;
  currencies?: string[];
  count?: number;
  error?: string;
}

export interface CrawlResponse {
  status?: string;
  inserted?: number;
  message?: string;
  error?: string;
  [key: string]: unknown;
}

export interface StatsResponse {
  sources: Record<
    string,
    {
      total_records: number;
      latest_date: string | null;
      latest_updated_at: string | null;
    }
  >;
  crawl_hour: number;
  crawl_minute: number;
}
