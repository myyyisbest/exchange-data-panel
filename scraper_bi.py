# -*- coding: utf-8 -*-
"""
印尼盾(IDR) 汇率数据源
- 优先: Bank Indonesia 官方 API（每个货币单独请求一个 endpoint）
   - USD:    https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursUSD_IDR3
   - 其它:  https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursNonUSD_IDR3
- 兜底: BI 官方 HTML 页面
- 数据: 各货币对印尼盾(IDR)的卖出价(BI 字段 'Nilai' 即 sell 价, per 1 单位外币)
- 归一化: 库中 JPY 是 per 100，其余 per 1；BI 全部 per 1，所以 JPY ×100
"""
import json
import logging
import re
import ssl
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ===== BI 官方 API =====
BI_API_URL_NONUSD = 'https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursNonUSD_IDR3'
BI_API_URL_USD = 'https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursUSD_IDR3'

# 我们关心的非 USD 货币（不包括 USD，因为 USD 有单独 endpoint）
NONUSD_CURRENCIES = [
    'CNH', 'CNY', 'EUR', 'GBP', 'HKD', 'JPY', 'KRW',
    'MYR', 'SGD', 'THB', 'AUD', 'CAD', 'NZD', 'CHF', 'DKK',
    'NOK', 'SEK', 'SAR', 'AED', 'BND', 'KWD', 'PGK', 'PHP',
    'VND', 'LAK',
]

# 数据库中 JPY 是 per 100，其余 IDR 大部分 per 1
# BI API 全部 per 1 卖价，JPY 需要 ×100
PER_100_CURRENCIES = {'JPY'}

# ===== HTML 兜底 =====
HTML_URL = 'https://www.bi.go.id/en/statistik/informasi-kurs/transaksi-bi/Default.aspx'
HTML_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


# ============== BI 官方 API ==============

def _create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
    })
    # BI 站点连接非常不稳定，需要更多重试和长 backoff
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=['GET'],
    )
    s.mount('https://', HTTPAdapter(max_retries=retries))
    return s


def _normalize_date(s: str) -> str:
    """BI 日期格式: '2026-06-09T00:00:00' 或 '2026-06-09' 或 '06/09/2026' → YYYY-MM-DD"""
    s = s.strip()
    if not s:
        return ''
    # ISO 格式带时间
    if 'T' in s:
        s = s.split('T')[0]
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return ''


def _parse_bi_xml(xml_text: str) -> list:
    """
    解析 BI API 返回的 XML
    格式（参考文档）:
    <diffgr:diffgram><NewDataSet xmlns="">
      <Table xmlns="http://tempuri.org/">
        <Tanggal>2026-06-09T00:00:00</Tanggal>
        <Nilai>2692.14</Nilai>           ← sell 价
        <Kurs>16823.45</Kurs>             ← buy 价
      </Table>
      ...
    </NewDataSet></diffgr:diffgram>
    返回: [(date_str, rate_per_1), ...]
    """
    results = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise RuntimeError(f'BI XML 解析失败: {e}')

    # 找所有 <Table>（带或不带 namespace）
    for tbl in root.iter():
        tag = tbl.tag.split('}')[-1] if '}' in tbl.tag else tbl.tag
        if tag != 'Table':
            continue
        # 找 Tanggal/Nilai 节点
        tanggal_node = None
        nilai_node = None
        for child in tbl.iter():
            ctag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if ctag == 'Tanggal' and tanggal_node is None:
                tanggal_node = child
            elif ctag == 'Nilai' and nilai_node is None:
                nilai_node = child
        if tanggal_node is None or tanggal_node.text is None:
            continue
        if nilai_node is None or nilai_node.text is None:
            continue
        ds = _normalize_date(tanggal_node.text)
        if not ds:
            continue
        try:
            v = float(nilai_node.text.replace(',', ''))
        except (ValueError, TypeError):
            continue
        if v <= 0:
            continue
        results.append((ds, v))
    return results


def _fetch_bi_one_currency(session: requests.Session, code: str, start_date: str, end_date: str, timeout: int = 15) -> dict:
    """
    抓取单个货币对 IDR 的 sell 价
    :return: {date_str: rate_per_1, ...}  仅保留最新有效日期
    """
    is_usd = (code.upper() == 'USD')
    url = BI_API_URL_USD if is_usd else BI_API_URL_NONUSD
    params = {
        'startdate': start_date,
        'enddate': end_date,
    }
    if not is_usd:
        params['mts'] = code.upper()

    r = session.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    parsed = _parse_bi_xml(r.text)
    if not parsed:
        raise RuntimeError(f'BI API {code} 返回空 XML')
    # 取最近一天
    parsed.sort(key=lambda x: x[0])
    latest_date, latest_val = parsed[-1]
    return {latest_date: latest_val}


def _fetch_bi_api(target_date: str, timeout: int = 10) -> dict:
    """
    通过 BI 官方 API 抓取多个货币
    :return: {date_str: {code: rate_per_1, ...}, ...}  通常只有一天
    """
    start = (datetime.strptime(target_date, '%Y-%m-%d').date() - timedelta(days=2)).isoformat()
    end = target_date

    session = _create_session()
    # 先抓非 USD（多货币），再抓 USD
    all_codes = NONUSD_CURRENCIES + ['USD']
    by_date: dict = {}

    # 试一个非 USD 货币判断 API 是否可达，500/403 立即放弃
    try:
        rates = _fetch_bi_one_currency(session, all_codes[0], start, end, timeout=timeout)
        for d, v in rates.items():
            by_date.setdefault(d, {})[all_codes[0]] = v
    except Exception as e:
        err_msg = str(e)[:120]
        logger.warning(f'[BI] API 探测 {all_codes[0]} 失败: {err_msg}')
        # 500 错误是 geo 限制，立即放弃
        if '500' in err_msg or 'cannot access' in err_msg.lower():
            raise RuntimeError(f'BI API geo-restricted (500): {err_msg}')
        raise

    # 第一个 OK 后再抓剩余货币（仍然用较短超时，单个失败就跳过）
    for code in all_codes[1:]:
        for attempt in range(2):
            try:
                rates = _fetch_bi_one_currency(session, code, start, end, timeout=timeout)
                for d, v in rates.items():
                    by_date.setdefault(d, {})[code] = v
                break
            except Exception as e:
                logger.debug(f'[BI] {code} 第 {attempt+1} 次失败: {e.__class__.__name__}: {str(e)[:80]}')
                time.sleep(1.0)
        else:
            logger.warning(f'[BI] {code} 多次失败，跳过')

    if not by_date:
        raise RuntimeError('BI API 全部货币失败')
    # 取最近一天
    latest_date = max(by_date.keys())
    return {latest_date: by_date[latest_date]}


# ============== HTML 兜底 ==============

def _parse_html_table(html: str) -> dict:
    """解析 BI HTML 表格（每行: code, unit, sell, buy, ...）"""
    results = {}
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) < 4:
            continue
        clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
        code = clean[0]
        if not (len(code) == 3 and code.isalpha() and code.isupper()):
            continue
        try:
            unit = int(clean[1]) if clean[1] else 1
            sell_raw = float(clean[2].replace(',', ''))
        except (ValueError, IndexError):
            continue
        # BI HTML 是 per unit 的 sell 价（unit 列），与 API 一致
        if unit:
            v = sell_raw / unit
        else:
            v = sell_raw
        results[code] = v
    return results


def _fetch_html(target_date: str, retries: int = 5) -> dict:
    """BI HTML 兜底（站点不稳定，需要多次重试）"""
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(HTML_URL, headers=HTML_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            rates = _parse_html_table(html)
            if not rates:
                raise RuntimeError('未从 BI HTML 解析到汇率数据')
            return {target_date: rates}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(2 ** i)
    raise RuntimeError(f'BI HTML 抓取失败: {last_err}')


# ============== 公开接口 ==============

def _normalize_units(rates: dict) -> dict:
    """对 BI 返回的 per 1 数据按数据库 unit 配置做归一化"""
    out = {}
    for code, v in rates.items():
        if code in PER_100_CURRENCIES:
            v = v * 100
        out[code] = round(v, 4)
    return out


def fetch(target_date: str = None, retries: int = 2) -> list:
    """
    抓取 BI 汇率：先 API，失败回退到 HTML
    :param target_date: YYYY-MM-DD
    :param retries: HTML 兜底重试次数（BI 站点非常不稳定）
    :return: [(date_str, rates_dict), ...]
    """
    if target_date is None:
        target_date = date.today().isoformat()

    # 1) BI 官方 API 优先
    try:
        data = _fetch_bi_api(target_date, timeout=12)
        if data:
            latest_date = max(data.keys())
            rates = _normalize_units(data[latest_date])
            if rates:
                logger.info(f'[BI] API 成功 ({latest_date}, {len(rates)} 货币)')
                return [(latest_date, rates)]
    except Exception as e:
        logger.warning(f'[BI] API 失败 ({e.__class__.__name__}: {str(e)[:100]})，回退到 HTML')

    # 2) HTML 兜底
    for attempt in range(retries):
        try:
            data = _fetch_html(target_date, retries=5)
            latest_date = max(data.keys())
            rates = _normalize_units(data[latest_date])
            if rates:
                logger.info(f'[BI] HTML 抓取成功 ({latest_date}, {len(rates)} 货币)')
                return [(latest_date, rates)]
        except Exception as e:
            logger.warning(f'[BI] HTML 第 {attempt+1} 次失败: {e}')
        time.sleep(2)
    raise RuntimeError('BI API 和 HTML 都失败')


def fetch_one(target_date: str = None) -> tuple:
    rows = fetch(target_date)
    return rows[0] if rows else None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    print('抓取 BI (IDR) 汇率...')
    try:
        d, rates = fetch_one()
        print(f'\n>>> 日期: {d}')
        print(f'>>> 共 {len(rates)} 种货币')
        for code in ['USD', 'EUR', 'JPY', 'CNY', 'SGD', 'AUD', 'KRW', 'GBP', 'HKD']:
            print(f'  {code}: {rates.get(code)}')
    except Exception as e:
        print(f'失败: {e}')
