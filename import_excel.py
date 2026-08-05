# -*- coding: utf-8 -*-
"""
历史汇率 Excel 导入工具
将《人民币汇率中间价（1994-2025）.xlsx》批量导入 SQLite

用法：
    python import_excel.py                                          # 默认路径
    python import_excel.py "C:/path/to/人民币汇率中间价.xlsx"        # 指定路径
"""
import sys
import os
import re
import sqlite3
import logging

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Excel 列顺序（与 database.CURRENCIES 一致）
EXCEL_COL_NAMES = ['美元', '欧元', '日元', '港元', '英镑', '澳元', '新西兰元',
                   '新加坡元', '瑞士法郎', '加元', '澳门元', '林吉特', '卢布', '兰特',
                   '韩元', '迪拉姆', '里亚尔', '福林', '兹罗提', '丹麦克朗',
                   '瑞典克朗', '挪威克朗', '里拉', '比索', '泰铢']

CURRENCY_CODES = ['USD', 'EUR', 'JPY', 'HKD', 'GBP', 'AUD', 'NZD', 'SGD', 'CHF', 'CAD',
                  'MOP', 'MYR', 'RUB', 'ZAR', 'KRW', 'AED', 'SAR', 'HUF', 'PLN', 'DKK',
                  'SEK', 'NOK', 'TRY', 'MXN', 'THB']

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'exchange.db')


def parse_value(v):
    """将 Excel 单元格值转为 float，'-'或None返回 None"""
    if v is None or str(v).strip() in ('-', '', 'N/A', '#N/A'):
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def parse_date(v):
    """解析日期字段，支持字符串和 datetime 对象"""
    if v is None:
        return None
    if hasattr(v, 'strftime'):  # datetime/date 对象
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    return None


def load_excel(excel_path: str) -> list:
    """
    读取 Excel，返回 [(date_str, rates_dict), ...]
    自动跳过标题行和无效行
    """
    try:
        import openpyxl
    except ImportError:
        logger.error('缺少 openpyxl，请运行: pip install openpyxl')
        sys.exit(1)

    logger.info(f'读取 Excel: {excel_path}')
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active

    rows_out = []
    skipped = 0

    for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
        if row_idx == 0:
            # 标题行：验证列结构
            header = [str(c).strip() if c else '' for c in row]
            logger.info(f'表头: {header[:5]}...')
            continue

        if not row or row[0] is None:
            skipped += 1
            continue

        date_str = parse_date(row[0])
        if not date_str:
            skipped += 1
            continue

        # 按顺序取 25 列数值（列索引 1~25）
        rates = {}
        for i, code in enumerate(CURRENCY_CODES):
            val = row[i + 1] if i + 1 < len(row) else None
            v = parse_value(val)
            if v is not None:
                rates[code] = v

        if not rates:  # 完全没有数字，跳过
            skipped += 1
            continue

        rows_out.append((date_str, rates))

    wb.close()
    logger.info(f'解析完成：{len(rows_out)} 条有效数据，{skipped} 条跳过')
    return rows_out


def import_to_db(rows: list, db_path: str = DB_PATH) -> tuple:
    """
    批量导入数据库（跳过已存在）
    返回 (inserted, skipped)
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # 确保表存在（复用 database 模块的逻辑）
    import database
    database.init_db()

    total_ins = 0
    total_skip = 0
    batch_size = 500

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # 先取出所有已存在的日期（快速集合查询）
        existing_dates = {row[0] for row in conn.execute('SELECT date FROM exchange_rates')}
        logger.info(f'数据库已有 {len(existing_dates)} 条记录')

        # 过滤出需要插入的行
        to_insert = [(d, r) for d, r in rows if d not in existing_dates]
        logger.info(f'需新增: {len(to_insert)} 条，已存在跳过: {len(rows) - len(to_insert)} 条')

        if not to_insert:
            return 0, len(rows)

        # 构建批量 INSERT 语句
        cols = 'date, ' + ', '.join(CURRENCY_CODES)
        placeholders = ', '.join(['?'] * (1 + len(CURRENCY_CODES)))
        sql = f'INSERT OR IGNORE INTO exchange_rates ({cols}) VALUES ({placeholders})'

        # 分批插入
        batch = []
        for i, (date_str, rates) in enumerate(to_insert):
            values = [date_str] + [rates.get(code) for code in CURRENCY_CODES]
            batch.append(values)

            if len(batch) >= batch_size:
                conn.executemany(sql, batch)
                conn.commit()
                total_ins += len(batch)
                logger.info(f'  已导入 {total_ins}/{len(to_insert)} ...')
                batch = []

        if batch:
            conn.executemany(sql, batch)
            conn.commit()
            total_ins += len(batch)

        total_skip = len(rows) - len(to_insert)
    finally:
        conn.close()

    return total_ins, total_skip


def main():
    # 默认路径（项目目录下的同名 Excel，也可通过命令行参数指定）
    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '人民币汇率中间价（1994-2025）.xlsx')

    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = default_path

    if not os.path.exists(excel_path):
        logger.error(f'文件不存在: {excel_path}')
        logger.error('用法: python import_excel.py "Excel文件路径"')
        sys.exit(1)

    print(f'\n{"=" * 60}')
    print(f'  人民币汇率历史数据导入工具')
    print(f'  来源文件: {os.path.basename(excel_path)}')
    print(f'  目标数据库: {DB_PATH}')
    print(f'{"=" * 60}\n')

    # 1. 读取 Excel
    rows = load_excel(excel_path)
    if not rows:
        logger.error('Excel 中没有读取到有效数据')
        sys.exit(1)

    # 2. 导入数据库
    inserted, skipped = import_to_db(rows)

    print(f'\n{"=" * 60}')
    print(f'  导入完成！')
    print(f'  新增: {inserted} 条')
    print(f'  已存在跳过: {skipped} 条')
    print(f'  数据库总记录数: {inserted + skipped} 条')
    print(f'{"=" * 60}\n')


if __name__ == '__main__':
    main()
