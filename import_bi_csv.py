# -*- coding: utf-8 -*-
"""
从 bi_exchange_rates_2022_2026.csv 导入历史汇率到 exchange_rates_idr。
- 源: Date, Currency, Value=1, Sell, Buy
- Sell 是 BI 公布的"每 1 单位外币的 IDR 卖价" (per 1)。
- DB schema: JPY per 100，其他 per 1 → JPY × 100 后存。
- UPSERT，CSV 比 DB 新的字段会覆盖，但 2026-06-04~09 的 JPY 已经正确，不动。
- 冲突策略：CSV 优先（CSV 是完整历史数据集）
"""
import csv
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

# 路径基于本脚本所在目录，避免硬编码绝对路径
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_BASE_DIR, 'bi_exchange_rates_2022_2026.csv')
DB_PATH = os.path.join(_BASE_DIR, 'data', 'exchange.db')

# DB 列顺序（不含 id, date, created_at）
COLUMNS = [
    'AED', 'AUD', 'BND', 'CAD', 'CHF', 'CNH', 'CNY', 'DKK', 'EUR', 'GBP',
    'HKD', 'JPY', 'KRW', 'KWD', 'LAK', 'MYR', 'NOK', 'NZD', 'PGK', 'PHP',
    'SAR', 'SEK', 'SGD', 'THB', 'USD', 'VND',
]
PER_100 = {'JPY'}

# 1) 解析 CSV
by_date: dict = defaultdict(dict)
with open(CSV_PATH, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        d = row['Date']
        c = row['Currency']
        try:
            unit = float(row['Value'])
            v = float(row['Sell'])
        except (ValueError, KeyError):
            continue
        if v <= 0 or c not in COLUMNS or unit <= 0:
            continue
        # CSV 里 JPY 的 Value=100, 其他币种 Value=1;
        # 都归一为 per 1; DB schema JPY 存 per 100, 所以 JPY × 100
        per_one = v / unit
        if c in PER_100:
            per_one = per_one * 100  # 存 per 100 到 DB
        by_date[d][c] = round(per_one, 4)

print(f'  parsed: {sum(len(v) for v in by_date.values())} cells, {len(by_date)} dates')

# 2) 一次性事务 UPSERT
conn = sqlite3.connect(DB_PATH)
try:
    placeholders = ','.join(['?'] * len(COLUMNS))
    cols_sql = ','.join(COLUMNS)
    update_set = ','.join(f'{c}=COALESCE(excluded.{c}, {c})' for c in COLUMNS)
    # 用 ON CONFLICT(date) DO UPDATE，覆盖 CSV 提供的新值；
    # 但保留 DB 已有但 CSV 缺失的列（COALESCE(new, old)）。
    sql = f'''INSERT INTO exchange_rates_idr (date, {cols_sql})
              VALUES (?, {placeholders})
              ON CONFLICT(date) DO UPDATE SET {update_set}'''

    inserted = updated = 0
    for d in sorted(by_date.keys()):
        rates = by_date[d]
        row_vals = [d] + [rates.get(c) for c in COLUMNS]
        cur = conn.execute(sql, row_vals)
        if cur.rowcount == 0:
            inserted += 1
        else:
            updated += 1
    conn.commit()
    print(f'  upserted: {inserted} new + {updated} updated')

    # 3) 校验
    stats = conn.execute(
        'SELECT COUNT(*), MIN(date), MAX(date) FROM exchange_rates_idr'
    ).fetchone()
    print(f'  DB stats: {stats[0]} rows, {stats[1]} ~ {stats[2]}')

    print('\n  sample (2026-06-10 after import):')
    r = conn.execute(
        'SELECT USD, EUR, JPY, CNY, HKD, KRW FROM exchange_rates_idr WHERE date=?',
        ('2026-06-10',),
    ).fetchone()
    print(f'    USD={r[0]} EUR={r[1]} JPY={r[2]} CNY={r[3]} HKD={r[4]} KRW={r[5]}')

    # 4) 检查 DB 中 JPY 是否合理 (per 100 应该在 1万 量级)
    bad = conn.execute(
        'SELECT date, JPY FROM exchange_rates_idr WHERE JPY > 0 AND JPY < 200'
    ).fetchall()
    if bad:
        print(f'\n  ⚠️  {len(bad)} 行 JPY 偏小（可能是 per 1 漏乘 100），前 5 行:')
        for d, v in bad[:5]:
            print(f'    {d}: {v}')
    else:
        print('\n  ✓ JPY 全部 ≥200 (per 100 合理)')

    # 5) 检查日期覆盖
    missing = conn.execute(
        '''SELECT COUNT(*) FROM exchange_rates_idr
           WHERE date BETWEEN '2022-01-01' AND '2026-05-31'
           AND USD IS NULL'''
    ).fetchone()[0]
    print(f'  2022~2026-05 缺 USD 行: {missing}')
finally:
    conn.close()
