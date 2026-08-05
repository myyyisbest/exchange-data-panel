# -*- coding: utf-8 -*-
"""
导入 HKD 历史汇率 CSV 到 exchange_rates_hkd 表

CSV 格式 (30798 行):
  Date,Currency_Code,Currency,Unit,Selling,Buying_TT,Buying_DD
  - 23 个币种, 日期范围 2022-01-03 ~ 2026-06-10
  - Unit=100 (大多数) / Unit=1 (GBP)
  - WON (CSV) -> KRW (DB)
  - DB 列存的是 per-1 汇率, Unit=100 时需要 /100

DB 当前: exchange_rates_hkd 已有 11 天 (2026-05-26~06-10), 用 INSERT OR IGNORE 跳过
"""
import csv
import sqlite3
import os
import sys
from collections import defaultdict
from datetime import datetime

CSV_PATH = os.path.join(os.path.dirname(__file__), 'hkd_exchange_rates_2022_2026.csv')
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'exchange.db')

# CSV 币种代码 -> DB 列名
CODE_MAP = {
    'WON': 'KRW',
    # 其余 22 个币种代码跟 DB 列名一致
}

# HKD 表 DB 的列（用于 SQL）
HKD_COLS = ['AUD','BND','CAD','CHF','CNH','CNY','DKK','EUR','GBP','INR',
            'JPY','KRW','MYR','NOK','NTD','NZD','PHP','PKR','SEK','SGD',
            'THB','USD','ZAR']

def main():
    if not os.path.exists(CSV_PATH):
        print(f'❌ CSV 不存在: {CSV_PATH}')
        sys.exit(1)
    if not os.path.exists(DB_PATH):
        print(f'❌ DB 不存在: {DB_PATH}')
        sys.exit(1)

    # 1) 读 CSV, 按 date 分组
    print(f'📖 读取 CSV: {CSV_PATH}')
    by_date = defaultdict(dict)   # {date_str: {col_name: rate_per_1}}
    skipped_currency = set()
    csv_total = 0
    with open(CSV_PATH, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_total += 1
            d = row.get('Date', '').strip()
            raw_code = row.get('Currency_Code', '').strip().upper()
            if not d or not raw_code:
                continue
            # 转换 WON -> KRW
            code = CODE_MAP.get(raw_code, raw_code)
            if code not in HKD_COLS:
                skipped_currency.add(raw_code)
                continue
            # 验证日期格式
            try:
                datetime.strptime(d, '%Y-%m-%d')
            except ValueError:
                continue
            # 读 Selling 价
            try:
                v = float(row['Selling'])
                unit = float(row.get('Unit') or 1)
            except (ValueError, KeyError):
                continue
            if v <= 0 or unit <= 0:
                continue
            # 归一化为 per 1
            per_one = v / unit
            by_date[d][code] = round(per_one, 6)

    print(f'   CSV 总行: {csv_total}, 解析日期: {len(by_date)} 天')
    if skipped_currency:
        print(f'   ⚠️  跳过的未知币种: {skipped_currency}')

    # 2) 查 DB 已存在日期
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT date FROM exchange_rates_hkd')
    existing = {r[0] for r in cur.fetchall()}
    print(f'   DB 已存在: {len(existing)} 天 ({min(existing) if existing else "-"} ~ {max(existing) if existing else "-"})')

    # 3) 准备 INSERT, 跳过已存在
    cols_sql = ','.join(HKD_COLS)
    placeholders = ','.join(['?'] * (len(HKD_COLS) + 1))  # +1 for date
    sql = f'INSERT OR IGNORE INTO exchange_rates_hkd (date, {cols_sql}) VALUES ({placeholders})'

    inserted = 0
    skipped = 0
    batch = []
    for d in sorted(by_date):
        if d in existing:
            skipped += 1
            continue
        rates = by_date[d]
        row_vals = [d] + [rates.get(c) for c in HKD_COLS]
        batch.append(row_vals)

    print(f'   待插入: {len(batch)} 天 (跳过已存在: {skipped})')

    # 4) 批量插入 (每 500 一批)
    BATCH = 500
    for i in range(0, len(batch), BATCH):
        chunk = batch[i:i+BATCH]
        cur.executemany(sql, chunk)
        inserted += len(chunk)
        conn.commit()
        if (i // BATCH) % 4 == 0:
            print(f'   已插入 {inserted}/{len(batch)}...')

    # 5) 验证
    cur.execute('SELECT COUNT(*), MIN(date), MAX(date) FROM exchange_rates_hkd')
    total, mn, mx = cur.fetchone()
    print()
    print('=== 导入结果 ===')
    print(f'  本次插入: {inserted} 天')
    print(f'  跳过已存在: {skipped} 天')
    print(f'  HKD 表总行数: {total}')
    print(f'  日期范围: {mn} ~ {mx}')

    # 6) 抽样验证
    print()
    print('=== 抽样验证 ===')
    cur.execute('SELECT date, USD, EUR, JPY, CNY, GBP, KRW FROM exchange_rates_hkd ORDER BY date DESC LIMIT 3')
    for r in cur.fetchall():
        print(f'  {r[0]}: USD={r[1]} EUR={r[2]} JPY={r[3]} CNY={r[4]} GBP={r[5]} KRW={r[6]}')

    # 验证最早期一天
    cur.execute('SELECT date, USD, EUR, JPY, CNY, GBP, KRW FROM exchange_rates_hkd WHERE date = "2022-01-03"')
    r = cur.fetchone()
    if r:
        print(f'  2022-01-03 (首日): USD={r[1]} EUR={r[2]} JPY={r[3]} CNY={r[4]} GBP={r[5]} KRW={r[6]}')

    conn.close()
    print()
    print('✅ 完成')

if __name__ == '__main__':
    main()
