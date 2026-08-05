# -*- coding: utf-8 -*-
"""
国家外汇管理局 / CFETS 人民币汇率中间价
来源:
  1) CFETS: GET https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json
     - 中国外汇交易中心官方，无需认证，工作日 9:15 更新
     - 一次返回当日所有币种中间价
  2) SAFE:  POST https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do
     - 国家外汇管理局，HTML 表格
     - 仅在 CFETS 不可用时兜底
"""
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, datetime, timedelta

# 数据列顺序（与 database.CURRENCIES 保持一致）
CURRENCY_ORDER = [
    'USD', 'EUR', 'JPY', 'HKD', 'GBP', 'AUD', 'NZD', 'SGD', 'CHF', 'CAD',
    'MOP', 'MYR', 'RUB', 'ZAR', 'KRW', 'AED', 'SAR', 'HUF', 'PLN', 'DKK',
    'SEK', 'NOK', 'TRY', 'MXN', 'THB',
]

# CFETS 主路径
CFETS_URL = 'https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json'
# SAFE 兜底
URL = 'https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.safe.gov.cn/safe/rmbhlzjj/index.html',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# CFETS 用 vrtEName (e.g. "USD/CNY", "100JPY/CNY", "CNY/KRW") 来标注方向和单位
# 归一目标: 全部统一为直接报价法入库（per 1 外币 = X CNY），便于趋势图和跨币种对比。
# 用户决策 (2026-06): 港币/印尼等本来就是直接报价法；15 个 indirect 币种（MOP/MYR/RUB/
# ZAR/KRW/AED/SAR/HUF/PLN/DKK/SEK/NOK/TRY/MXN/THB）里只有 2 个常用货币，趋势图不
# 值得为此保留两种方向，全部转成直接报价法。
#
#   {CODE}/CNY       → 1 外币 = price CNY    (direct)    → price
#   100{CODE}/CNY    → 100 外币 = price CNY  (direct)    → price / 100
#   CNY/{CODE}       → 1 CNY = price 外币    (indirect)  → 1 / price
#                                                              (仅颠倒方向)
# 注: CFETS vrtEName="CNY/{CODE}" 的 price 实际是 per 1（虽然 SAFE 历史数据是 per
#     100），所以 1/price 就是 1 外币 = X CNY。database.CURRENCIES_CNY.quote_method
#     同步改为 'direct'，unit 仍为 100（兼容 SAFE 历史兜底）。


def _parse_cfets_json(body: str) -> list:
    """
    解析 CFETS ccpr.json，返回 [(date_str, rates_dict), ...]
    CFETS 数据是当日一张表：lastDate 字段是日期，
    records 数组每项含 vrtEName / foreignCName / price / bp。
    100日元/人民币 是 per 100，需 ÷100。
    """
    obj = json.loads(body)
    if obj.get('head', {}).get('rep_code') != '200':
        raise RuntimeError(f'CFETS 错误: {obj.get("head", {})}')
    data = obj.get('data') or {}
    last_date = data.get('lastDate', '')  # e.g. "2026-06-10 9:15"
    date_str = last_date.split(' ')[0] if last_date else date.today().isoformat()
    records = data.get('records') or obj.get('records') or []
    if not records:
        raise RuntimeError('CFETS 返回无 records')
    rates = {}
    for rec in records:
        # vrtEName 三种形式决定归一公式
        #   "USD/CNY"      direct per 1   → 1 外币 = price CNY
        #   "100JPY/CNY"   direct per 100 → 100 外币 = price CNY
        #   "CNY/KRW"      indirect per 100 → 100 CNY = price 外币
        vrt = (rec.get('vrtEName') or '').strip()
        code = rec.get('foreignCName') or vrt.split('/')[0].lstrip('0123456789')
        try:
            price = float(rec.get('price', 0))
        except (ValueError, TypeError):
            continue
        if price <= 0:
            continue

        if vrt.startswith('CNY/'):
            # 间接标价法: 1 CNY = price 外币（CFETS 给的是 per 1）
            # 统一转直接报价法: 1 外币 = 1 / price CNY
            v = 1.0 / price
        elif vrt.startswith('100'):
            # 直接 per 100: 100 外币 = price CNY
            v = price / 100.0
        else:
            # 直接 per 1: 1 外币 = price CNY
            v = price
        rates[code] = round(v, 6)
    if not rates:
        raise RuntimeError('CFETS JSON 解析后无有效汇率')
    return [(date_str, rates)]


def _fetch_cfets(retries: int = 3) -> list:
    """CFETS 一次拉当日所有币种"""
    req = urllib.request.Request(CFETS_URL, headers={
        'User-Agent': HEADERS['User-Agent'],
        'Referer': 'https://www.chinamoney.com.cn/',
        'Accept': 'application/json,text/plain,*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode('utf-8', errors='ignore')
            return _parse_cfets_json(body)
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f'CFETS 抓取失败: {last_err}')


def _parse_html_table(html: str) -> list:
    """
    解析 SAFE 返回的 HTML，提取 (date_str, [25 个汇率]) 列表。
    SAFE 的表格用 <tr> 包日期+25 个数字，按 CURRENCY_ORDER 顺序。
    """
    results = []
    # 匹配每一行 tr
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        # 提取该行所有 td 中的纯数字/文本
        cells = re.findall(r'<td[^>]*>\s*([\d\-\.]+)\s*</td>', row)
        if len(cells) < 2:
            continue
        date_str = cells[0]
        # 校验日期格式
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            continue
        # 数字列
        values = []
        for v in cells[1:]:
            try:
                values.append(float(v))
            except ValueError:
                continue
        if len(values) != 25:
            # 长度不对，可能是空行或表头
            continue
        rates = dict(zip(CURRENCY_ORDER, values))
        # SAFE 表里所有币种都按 100 基准报价，但分两种方向（跟 CFETS 一致）：
        #   10 个直接标价法: 100 外币 = price CNY  → v / 100  (per 1 外币 = X CNY)
        #   15 个间接标价法: 100 CNY = price 外币  → 100 / v  (per 1 外币 = X CNY)
        # 现在 database.CURRENCIES_CNY 全部标记为 'direct'，需要按 CURRENCIES_CNY
        # 反查 SAFE 历史原始的 direct/indirect 标记。这里用代码里 hardcode 的 INDIRECT_CNY
        # 集合（与 2026-06 scraper 重构前 SAFE 表的列顺序一致）。
        INDIRECT_CNY = {
            'MOP', 'MYR', 'RUB', 'ZAR', 'KRW', 'AED', 'SAR', 'HUF', 'PLN',
            'DKK', 'SEK', 'NOK', 'TRY', 'MXN', 'THB',
        }
        rates = {k: round((100.0 / v) if k in INDIRECT_CNY else (v / 100.0), 6)
                 for k, v in rates.items()}
        results.append((date_str, rates))
    return results


def fetch(start_date: str, end_date: str, retries: int = 3) -> list:
    """
    抓取指定日期范围的数据
    :param start_date: YYYY-MM-DD
    :param end_date:   YYYY-MM-DD
    :return: [(date_str, rates_dict), ...]

    策略: 范围 ≤1 天 走 CFETS JSON（更快更准，多币种），
          否则走 SAFE POST（按日期范围批量拉）。
          CFETS 失败时自动回退 SAFE。
    """
    # CFETS 只能给"今天"一张表；如果不是当日或失败则走 SAFE
    today = date.today().isoformat()
    if start_date <= today <= end_date:
        try:
            cfets_rows = _fetch_cfets(retries=retries)
            if cfets_rows and start_date <= cfets_rows[0][0] <= end_date:
                return cfets_rows
        except Exception:
            # CFETS 失败 → 回退 SAFE
            pass

    # SAFE HTML 兜底
    data = urllib.parse.urlencode({
        'startDate': start_date,
        'endDate': end_date,
        'queryYN': 'true',
    }).encode('utf-8')

    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(URL, data=data, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode('utf-8', errors='ignore')
            return _parse_html_table(body)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(2 ** i)
    raise RuntimeError(f'抓取失败 ({start_date} ~ {end_date}): {last_err}')


def fetch_one(target_date: str = None) -> dict:
    """抓取单日数据（不存库）"""
    if target_date is None:
        target_date = date.today().isoformat()
    rows = fetch(target_date, target_date)
    if not rows:
        return None
    return rows[0]


if __name__ == '__main__':
    # 简单自测
    today = date.today().isoformat()
    print(f'抓取 {today} 汇率...')
    rows = fetch(today, today)
    if rows:
        d, rates = rows[0]
        print(f'日期: {d}')
        for code, val in rates.items():
            print(f'  {code}: {val}')
    else:
        print('未返回数据（可能是周末/节假日）')
