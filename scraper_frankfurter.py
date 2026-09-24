# -*- coding: utf-8 -*-
"""
Frankfurter 市场中间价（USD 基座）
- API: https://api.frankfurter.dev/v2/rates （可通过 FRANKFURTER_BASE_URL 覆盖）
- 返回扁平数组 [{date, base, quote, rate}, ...]，rate = 1 base = X quote
- 入库约定与其它基座一致：直接标价法 1 外币 = Y USD → 对 Frankfurter rate 取倒数
- 支持单日与区间历史（from/to）；空日期（周末等）自动跳过
"""
import logging
import os
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# 默认公共端点；自托管时可设 FRANKFURTER_BASE_URL=https://your-host/v2
DEFAULT_BASE_URL = 'https://api.frankfurter.dev/v2'
BASE_URL = (os.environ.get('FRANKFURTER_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')

# 可选：逗号分隔 provider 列表，例如 "ECB,BOJ"；空则使用默认 blended
PROVIDERS = (os.environ.get('FRANKFURTER_PROVIDERS') or '').strip()

# 与 database.CURRENCIES_USD 对齐的报价货币（不含 USD 自身）
QUOTE_CURRENCIES = [
    'AED', 'AUD', 'BDT', 'BHD', 'BND', 'BRL', 'CAD', 'CHF',
    'CNH', 'CNY', 'CZK', 'DKK', 'EGP', 'EUR', 'FJD', 'GBP',
    'HKD', 'HUF', 'IDR', 'ILS', 'INR', 'JPY', 'KHR', 'KRW',
    'KWD', 'LAK', 'LKR', 'MMK', 'MOP', 'MXN', 'MYR', 'NOK',
    'NPR', 'NZD', 'OMR', 'PGK', 'PHP', 'PKR', 'PLN', 'QAR',
    'RUB', 'SAR', 'SEK', 'SGD', 'THB', 'TRY', 'TWD', 'VND',
    'ZAR',
]

QUOTE_SET = set(QUOTE_CURRENCIES)


def _create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'exchange-data-panel/1.0 (+https://github.com/myyyisbest/exchange-data-panel)',
        'Accept': 'application/json',
    })
    retries = Retry(
        total=4,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['GET'],
        raise_on_status=False,
    )
    s.mount('https://', HTTPAdapter(max_retries=retries))
    s.mount('http://', HTTPAdapter(max_retries=retries))
    return s


def _normalize_date(s: str) -> str:
    s = (s or '').strip()
    if not s:
        return ''
    if 'T' in s:
        s = s.split('T')[0]
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return ''


def _invert_rate(frank_rate: float) -> Optional[float]:
    """
    Frankfurter: 1 USD = frank_rate quote
    本库:      1 quote = 1/frank_rate USD
    """
    try:
        v = float(frank_rate)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    # 保留足够精度：弱币种倒数很小，强币种较大
    return round(1.0 / v, 10)


def _build_params(
    start: Optional[str] = None,
    end: Optional[str] = None,
    quotes: Optional[Iterable[str]] = None,
) -> dict:
    params = {
        'base': 'USD',
        'quotes': ','.join(quotes or QUOTE_CURRENCIES),
    }
    if PROVIDERS:
        params['providers'] = PROVIDERS
    if start and end and start == end:
        params['date'] = start
    elif start or end:
        if start:
            params['from'] = start
        if end:
            params['to'] = end
    return params


def _parse_records(payload) -> List[Tuple[str, dict]]:
    """
    将扁平数组按 date 聚合为 [(date_str, {QUOTE: per1_usd, ...}), ...]
    """
    if not isinstance(payload, list):
        raise RuntimeError(f'Frankfurter 返回非数组: {type(payload).__name__}')

    by_date = {}
    for rec in payload:
        if not isinstance(rec, dict):
            continue
        ds = _normalize_date(str(rec.get('date') or ''))
        quote = str(rec.get('quote') or '').upper()
        if not ds or quote not in QUOTE_SET:
            continue
        inv = _invert_rate(rec.get('rate'))
        if inv is None:
            continue
        by_date.setdefault(ds, {})[quote] = inv

    rows = []
    for ds in sorted(by_date.keys()):
        rates = by_date[ds]
        if not rates:
            continue
        rows.append((ds, rates))
    return rows


def fetch(start: str = None, end: str = None) -> list:
    """
    抓取 Frankfurter USD 基座汇率。
    :param start: YYYY-MM-DD；缺省则取今日
    :param end:   YYYY-MM-DD；缺省则等于 start
    :return: [(date_str, rates_dict), ...]  rates 为 1 外币 = X USD
    """
    if start is None and end is None:
        start = end = date.today().isoformat()
    elif start is None:
        start = end
    elif end is None:
        end = start

    # 校验日期
    for label, val in (('start', start), ('end', end)):
        try:
            datetime.strptime(val, '%Y-%m-%d')
        except (TypeError, ValueError):
            raise ValueError(f'无效日期 {label}={val!r}，期望 YYYY-MM-DD')
    if start > end:
        raise ValueError(f'start ({start}) 必须 <= end ({end})')

    url = f'{BASE_URL}/rates'
    params = _build_params(start, end)
    logger.info(f'[Frankfurter] GET {url} params={params}')

    session = _create_session()
    try:
        resp = session.get(url, params=params, timeout=60)
    except requests.RequestException as e:
        raise RuntimeError(f'Frankfurter 请求失败: {e}') from e

    if resp.status_code != 200:
        body = (resp.text or '')[:300]
        raise RuntimeError(f'Frankfurter HTTP {resp.status_code}: {body}')

    try:
        payload = resp.json()
    except ValueError as e:
        raise RuntimeError(f'Frankfurter JSON 解析失败: {e}') from e

    rows = _parse_records(payload)
    if not rows:
        logger.warning(f'[Frankfurter] {start}~{end} 无有效汇率行（可能周末/节假日）')
    else:
        logger.info(f'[Frankfurter] 解析得到 {len(rows)} 个交易日')
    return rows


def fetch_latest() -> list:
    """仅抓取最新可用一日（不指定 date）"""
    url = f'{BASE_URL}/rates'
    params = _build_params()
    logger.info(f'[Frankfurter] GET latest {url} params={params}')
    session = _create_session()
    try:
        resp = session.get(url, params=params, timeout=60)
    except requests.RequestException as e:
        raise RuntimeError(f'Frankfurter 请求失败: {e}') from e
    if resp.status_code != 200:
        raise RuntimeError(f'Frankfurter HTTP {resp.status_code}: {(resp.text or "")[:300]}')
    return _parse_records(resp.json())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    today = date.today()
    start = (today - timedelta(days=3)).isoformat()
    end = today.isoformat()
    print(f'烟测 Frankfurter {start} ~ {end} ...')
    data = fetch(start, end)
    for ds, rates in data:
        sample = {k: rates[k] for k in list(rates)[:5]}
        print(f'  {ds}: {len(rates)} 币种  sample={sample}')
    print(f'共 {len(data)} 天')
