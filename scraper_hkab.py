# -*- coding: utf-8 -*-
"""
港币(HKD) 汇率数据源

数据获取优先级（每日最新牌价）:
  1) HKAB 公开 REST API (主路径, 按日精确, 含当日卖出价/电汇买入/汇票买入)
  2) HKAB 官方 HTML 页面 (兜底, API 不可用时)

API 端点:
  GET https://www.hkab.org.hk/api/member/public/getExrate/{YYYY-MM-DD}
  返回 JSON, 字段如 {CODE}Selling / {CODE}BuyingTT / {CODE}BuyingOD
  holiday=0 表示交易日, holiday=1 表示休市
  大多数币种 per 100 (Selling 数字÷100 = per-1), GBP 等 per 1
  无需鉴权, 大陆 IP 直连

返回格式: [(date_str, {currency_code: rate_per_1, ...}), ...]
- rate_per_1: 1 单位外币兑 HKD 的卖出价
- DB 历史 HKD 汇率按 per 1 存, scraper 输出也按 per 1
"""
import json
import logging
import re
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ============== HKAB 公开 API（主路径） ==============

# HKAB API 端点: 按日期获取当日的牌价
HKAB_API_URL = 'https://www.hkab.org.hk/api/member/public/getExrate/{date}'

# 23 种目标币种 (与 DB HKD 表 23 列完全一致)
# (CSV/DB 代码, HKAB API 字段前缀, 是否 per 1)
# - 大多数 per 100: API 返回 786.75 表示 100 USD = 786.75 HKD
# - GBP per 1: API 返回 10.560 表示 1 GBP = 10.560 HKD
HKAB_CURRENCIES = [
    ('AUD', 'AUD', False),   # 澳元
    ('BND', 'BND', False),   # 文莱元
    ('CAD', 'CAD', False),   # 加元
    ('CHF', 'CHF', False),   # 瑞士法郎
    ('CNH', 'CNH', False),   # 离岸人民币
    ('CNY', 'CNY', False),   # 人民币
    ('DKK', 'DKK', False),   # 丹麦克朗
    ('EUR', 'EUR', False),   # 欧元
    ('GBP', 'GBP', True),    # 英镑 (per 1)
    ('INR', 'INR', False),   # 印度卢比
    ('JPY', 'JPY', False),   # 日元
    ('KRW', 'WON', False),   # 韩元 (HKAB API 字段叫 WON, 非标准 ISO)
    ('MYR', 'MYR', False),   # 林吉特
    ('NOK', 'NOK', False),   # 挪威克朗
    ('NTD', 'NTD', False),   # 新台币
    ('NZD', 'NZD', False),   # 新西兰元
    ('PHP', 'PHP', False),   # 菲律宾比索
    ('PKR', 'PKR', False),   # 巴基斯坦卢比
    ('SEK', 'SEK', False),   # 瑞典克朗
    ('SGD', 'SGD', False),   # 新加坡元
    ('THB', 'THB', False),   # 泰铢
    ('USD', 'USD', False),   # 美元
    ('ZAR', 'ZAR', False),   # 南非兰特
]


# ============== HKAB HTML 兜底 ==============

HKAB_HTML_URL = 'https://www.hkab.org.hk/sc/rates/exchange-rates'

OBSOLETE_CURRENCIES = {'ATS', 'BEF', 'DEM', 'ESP', 'FRF', 'IEP', 'ITL', 'NLG', 'PTE'}

# HKAB 页面币种中文名（繁体/简体）→ ISO 代码
HKAB_NAME_TO_CODE = {
    '澳洲元': 'AUD', '澳元': 'AUD',
    '汶莱元': 'BND', '文莱元': 'BND',
    '加拿大元': 'CAD', '加元': 'CAD',
    '人民币': 'CNY', '离岸人民币': 'CNH',
    '瑞士法郎': 'CHF',
    '丹麦克朗': 'DKK',
    '欧罗': 'EUR', '欧元': 'EUR',
    '英镑': 'GBP',
    '印度卢比': 'INR',
    '印尼盾': 'IDR',
    '日元': 'JPY',
    '韩国圜': 'KRW', '韩元': 'KRW',
    '马来西亚元': 'MYR', '林吉特': 'MYR',
    '挪威克朗': 'NOK',
    '新台币': 'NTD',
    '纽西兰元': 'NZD', '新西兰元': 'NZD',
    '菲律宾披索': 'PHP', '菲律宾比索': 'PHP',
    '巴基斯坦卢比': 'PKR',
    '瑞典克朗': 'SEK',
    '新加坡元': 'SGD',
    '泰国铢': 'THB', '泰铢': 'THB',
    '美元': 'USD',
    '南非兰特': 'ZAR', '兰特': 'ZAR',
    '墨西哥比索': 'MXN',
    '阿联酋迪拉姆': 'AED',
    '沙特里亚尔': 'SAR',
    '卢布': 'RUB',
    '捷克克朗': 'CZK',
    '匈牙利福林': 'HUF',
}

HKAB_PER_ONE = {'GBP'}


# ============== 共用 session ==============

def _create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    })
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=['GET'],
    )
    s.mount('https://', HTTPAdapter(max_retries=retries))
    return s


# ============== HKAB API 主路径 ==============

def _fetch_hkab_api(target_date: str) -> tuple:
    """
    调用 HKAB 公开 API 获取指定日期的牌价
    :param target_date: YYYY-MM-DD
    :return: (date_str, {code: rate_per_1}) 或 None (休市/无数据)
    """
    s = _create_session()
    url = HKAB_API_URL.format(date=target_date)
    r = s.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()

    # 根级 holiday: 0=交易日, 1=休市
    if data.get('holiday') not in (0, '0', None):
        return None

    # ⚠️ HKAB API 返回字段全在根级, 并没有 lastRate 包裹层
    # 根级字段: holiday, RateDate, USDSelling, CNYSelling, ...
    actual_date = data.get('RateDate') or data.get('date') or target_date
    rates = {}
    for code, field, is_per_one in HKAB_CURRENCIES:
        sell_raw = data.get(f'{field}Selling')
        if sell_raw is None or sell_raw == '':
            continue
        try:
            v = float(sell_raw)
        except (ValueError, TypeError):
            continue
        if v <= 0:
            continue
        # 归一为 per 1
        if not is_per_one:
            v = v / 100.0
        rates[code] = round(v, 6)

    if not rates:
        return None
    return (actual_date, rates)


# ============== HKAB HTML 兜底 ==============

def _extract_nuxt_data(html: str) -> dict:
    """从 HKAB HTML 提取 Nuxt.js SSR 数据（兜底）"""
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    payload_str = None
    for s in scripts:
        s = s.strip()
        if s.startswith('[['):
            payload_str = s
            break
    if not payload_str:
        raise RuntimeError('未找到 Nuxt.js payload')
    flat = json.loads(payload_str)

    def resolve(obj, depth=0, seen=None):
        if seen is None:
            seen = set()
        if depth > 20:
            return obj
        if isinstance(obj, int) and obj in flat:
            if obj in seen:
                return None
            seen.add(obj)
            return resolve(flat[obj], depth + 1, seen)
        if isinstance(obj, list):
            return [resolve(x, depth + 1, seen) for x in obj]
        if isinstance(obj, dict):
            return {k: resolve(v, depth + 1, seen) for k, v in obj.items()}
        return obj

    return resolve(flat, 0, set())


def _parse_hkab_html(html: str) -> dict:
    """从 HKAB HTML 解析今日汇率（兜底）"""
    m_date = re.search(r'最后更新[：:]\s*(\d{4}-\d{2}-\d{2})', html)
    target_date = m_date.group(1) if m_date else date.today().isoformat()

    chunks = re.split(r'(?=<div role="row"[^>]*general_table_row)', html)
    rates = {}
    seen_codes = set()
    for c in chunks:
        if not c.startswith('<div role="row"'):
            continue
        m_code = re.search(r'货币代号[:：]?</div>\s*<div[^>]*>\s*([A-Z]{3,4})<', c)
        if m_code:
            raw_code = m_code.group(1)
            code = {'WON': 'KRW'}.get(raw_code, raw_code)
            m_name_cn = re.search(r'货币[:：]?</div>\s*<div[^>]*>\s*([^<]{1,30})<', c)
            if not m_name_cn:
                continue
        else:
            name_alt = '|'.join(re.escape(n) for n in sorted(HKAB_NAME_TO_CODE.keys(), key=len, reverse=True))
            m_name = re.search(rf'>({name_alt})<', c)
            if not m_name:
                continue
            code = HKAB_NAME_TO_CODE.get(m_name.group(1))
        if not code or code in seen_codes or code in OBSOLETE_CURRENCIES:
            continue
        m_sell = re.search(r'卖出价[:：]?</div>\s*<div[^>]*>\s*([\d.,]+)', c)
        if not m_sell:
            continue
        try:
            v = float(m_sell.group(1).replace(',', ''))
        except ValueError:
            continue
        if v <= 0:
            continue
        if code not in HKAB_PER_ONE:
            v = v / 100.0
        rates[code] = round(v, 6)
        seen_codes.add(code)

    if not rates:
        raise RuntimeError('HKAB HTML 解析后未找到汇率数据')
    return rates


def _fetch_hkab_html(retries: int = 3) -> dict:
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(HKAB_HTML_URL, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
                'Accept': 'text/html',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            return _parse_hkab_html(html)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(2 ** i)
    raise RuntimeError(f'HKAB HTML 抓取失败: {last_err}')


# ============== 公开接口 ==============

def fetch(target_date: str = None, retries: int = 2) -> list:
    """
    抓取 HKD 汇率 (按优先级: HKAB API -> HKAB HTML 兜底)
    :param target_date: YYYY-MM-DD (默认今日, HKAB API 严格要求具体日期)
    :param retries: HTML 兜底重试次数
    :return: [(date_str, rates_dict), ...]
    """
    if target_date is None:
        target_date = date.today().isoformat()

    # 1) HKAB 公开 API 优先 (主路径, 按日精确)
    try:
        result = _fetch_hkab_api(target_date)
        if result:
            d, rates = result
            logger.info(f'[HKAB-API] {d} 成功 ({len(rates)} 货币)')
            return [(d, rates)]
        else:
            logger.info(f'[HKAB-API] {target_date} 休市/无数据, 尝试最近一个交易日')
            # 向前回溯找最近一个交易日 (最多 7 天)
            cur = datetime.strptime(target_date, '%Y-%m-%d').date()
            for _ in range(7):
                cur -= timedelta(days=1)
                try:
                    r = _fetch_hkab_api(cur.isoformat())
                    if r:
                        d, rates = r
                        logger.info(f'[HKAB-API] 找到 {d} ({len(rates)} 货币, 非 {target_date} 交易日)')
                        return [(d, rates)]
                except Exception:
                    continue
            logger.warning('[HKAB-API] 近日无可用数据, 回退 HKAB HTML')
    except Exception as e:
        logger.warning(f'[HKAB-API] 失败 ({e.__class__.__name__}: {e}), 回退 HKAB HTML')

    # 2) HKAB HTML 兜底
    for attempt in range(retries):
        try:
            rates = _fetch_hkab_html(retries=3)
            logger.info(f'[HKAB-HTML] 抓取成功 ({len(rates)} 货币)')
            return [(target_date, rates)]
        except Exception as e:
            logger.warning(f'[HKAB-HTML] 第 {attempt+1} 次失败: {e}')
            time.sleep(2)

    raise RuntimeError('HKAB API / HKAB HTML 两条路径均失败')


def fetch_one(target_date: str = None) -> tuple:
    rows = fetch(target_date)
    return rows[-1] if rows else None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    print('抓取 HKD 汇率（HKAB API 主路径）...')
    try:
        rows = fetch()
        for d, rates in rows:
            print(f'\n>>> {d}: {len(rates)} 货币')
            for code in ['USD', 'EUR', 'JPY', 'CNY', 'SGD', 'GBP', 'AUD', 'KRW']:
                if code in rates:
                    print(f'  {code}: {rates[code]}')
    except Exception as e:
        print(f'失败: {e}')
