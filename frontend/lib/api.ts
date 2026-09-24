/**
 * 类型化的 Flask API 客户端。
 * 浏览器请求同源 /api/*，由 Next.js rewrites 代理到 FLASK_API_ORIGIN。
 */
import type {
  BaseCode,
  CrawlResponse,
  CurrencyMeta,
  PreferencesResponse,
  RecentResponse,
  SavePreferencesResponse,
  SourcesResponse,
  StatsResponse,
  UnifiedDateResponse,
  UnifiedLatestResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = path.startsWith("/") ? path : `/${path}`;
  const resp = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!resp.ok) {
    const body = (await resp.json().catch(() => ({
      error: resp.statusText,
    }))) as { error?: string };
    throw new ApiError(body.error || `HTTP ${resp.status}`, resp.status);
  }
  return resp.json() as Promise<T>;
}

export function getSources(): Promise<SourcesResponse> {
  return apiFetch<SourcesResponse>("/api/sources");
}

export function getCurrencies(base: BaseCode | string): Promise<CurrencyMeta[]> {
  return apiFetch<CurrencyMeta[]>(
    `/api/currencies?base=${encodeURIComponent(base)}`
  );
}

export function getUnifiedLatest(): Promise<UnifiedLatestResponse> {
  return apiFetch<UnifiedLatestResponse>("/api/unified/latest");
}

export function getUnifiedByDate(date: string): Promise<UnifiedDateResponse> {
  return apiFetch<UnifiedDateResponse>(
    `/api/unified/date/${encodeURIComponent(date)}`
  );
}

export function getRecent(
  base: BaseCode | string,
  days = 30
): Promise<RecentResponse> {
  return apiFetch<RecentResponse>(
    `/api/recent?base=${encodeURIComponent(base)}&days=${days}`
  );
}

export function getPreferences(
  base: BaseCode | string
): Promise<PreferencesResponse> {
  return apiFetch<PreferencesResponse>(
    `/api/preferences/${encodeURIComponent(base)}`
  );
}

export function savePreferences(
  base: BaseCode | string,
  currencies: string[]
): Promise<SavePreferencesResponse> {
  return apiFetch<SavePreferencesResponse>(
    `/api/preferences/${encodeURIComponent(base)}`,
    {
      method: "POST",
      body: JSON.stringify({ currencies }),
    }
  );
}

export function crawl(body?: {
  source?: string;
  start?: string;
  end?: string;
}): Promise<CrawlResponse> {
  return apiFetch<CrawlResponse>("/api/crawl", {
    method: "POST",
    body: JSON.stringify(body || {}),
  });
}

export function crawlAll(): Promise<CrawlResponse> {
  return apiFetch<CrawlResponse>("/api/crawl-all", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getStats(): Promise<StatsResponse> {
  return apiFetch<StatsResponse>("/api/stats");
}
