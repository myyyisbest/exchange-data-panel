# -*- coding: utf-8 -*-
"""
SQLite 数据库模块（多币种基座版）
- CNY: 25 种货币对人民币汇率中间价（国家外汇管理局）
- IDR: 26 种货币对印尼盾卖出价（Bank Indonesia）
- HKD: 23 种货币对港币卖出价（HKAB）

字段说明:
  quote_method: 'direct' = 直接标价法(1外币=?本币), 'indirect' = 间接标价法(1本币=?外币)
  unit: 官网原始报价单位(1 或 100), 数据库中已归一化为 per 1
"""
import json
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

# 默认数据库路径基于本文件目录，可通过环境变量 DB_PATH 覆盖
DB_PATH = os.environ.get('DB_PATH') or os.path.join(os.path.dirname(__file__), 'data', 'exchange.db')

# ==================== CNY 基座（SAFE）====================
# SAFE 数据: direct=True 为直接标价法(100外币兑人民币), direct=False 为间接标价法(100人民币兑外币)
# 原始数据单位均为 100, 入库时已除以 100 归一化为 per 1
# 2026-06 决策: 全部统一为直接报价法入库（per 1 外币 = X CNY），趋势图和跨币种
# 对比只用一种方向。15 个币种虽然 CFETS 官方用间接报价法（100 CNY = X 外币），
# 但 scraper 已统一转成"1 外币 = X CNY"，quote_method 标记为 'direct'。
# unit=100 沿用 SAFE 历史兜底的 100 CNY 基准。
CURRENCIES_CNY = [
    ('USD', '美元',      'direct',   100),
    ('EUR', '欧元',      'direct',   100),
    ('JPY', '日元',      'direct',   100),
    ('HKD', '港元',      'direct',   100),
    ('GBP', '英镑',      'direct',   100),
    ('AUD', '澳元',      'direct',   100),
    ('NZD', '新西兰元',  'direct',   100),
    ('SGD', '新加坡元',  'direct',   100),
    ('CHF', '瑞士法郎',  'direct',   100),
    ('CAD', '加元',      'direct',   100),
    ('MOP', '澳门元',    'direct',   100),
    ('MYR', '林吉特',    'direct',   100),
    ('RUB', '卢布',      'direct',   100),
    ('ZAR', '兰特',      'direct',   100),
    ('KRW', '韩元',      'direct',   100),
    ('AED', '迪拉姆',    'direct',   100),
    ('SAR', '里亚尔',    'direct',   100),
    ('HUF', '福林',      'direct',   100),
    ('PLN', '兹罗提',    'direct',   100),
    ('DKK', '丹麦克朗',  'direct',   100),
    ('SEK', '瑞典克朗',  'direct',   100),
    ('NOK', '挪威克朗',  'direct',   100),
    ('TRY', '里拉',      'direct',   100),
    ('MXN', '比索',      'direct',   100),
    ('THB', '泰铢',      'direct',   100),
]

# ==================== IDR 基座（BI）====================
# BI 数据: 全部为直接标价法(1外币=?IDR), 大部分是 per 1, JPY 为 per 100
CURRENCIES_IDR = [
    ('AED', '阿联酋迪拉姆', 'direct', 1),
    ('AUD', '澳元',      'direct', 1),
    ('BND', '文莱元',    'direct', 1),
    ('CAD', '加元',      'direct', 1),
    ('CHF', '瑞士法郎',  'direct', 1),
    ('CNH', '离岸人民币', 'direct', 1),
    ('CNY', '人民币',    'direct', 1),
    ('DKK', '丹麦克朗',  'direct', 1),
    ('EUR', '欧元',      'direct', 1),
    ('GBP', '英镑',      'direct', 1),
    ('HKD', '港元',      'direct', 1),
    ('JPY', '日元',      'direct', 100),   # BI 官网: per 100
    ('KRW', '韩元',      'direct', 1),
    ('KWD', '科威特第纳尔', 'direct', 1),
    ('LAK', '老挝基普',  'direct', 1),
    ('MYR', '林吉特',    'direct', 1),
    ('NOK', '挪威克朗',  'direct', 1),
    ('NZD', '新西兰元',  'direct', 1),
    ('PGK', '巴布亚新几内亚基那', 'direct', 1),
    ('PHP', '菲律宾比索', 'direct', 1),
    ('SAR', '沙特里亚尔', 'direct', 1),
    ('SEK', '瑞典克朗',  'direct', 1),
    ('SGD', '新加坡元',  'direct', 1),
    ('THB', '泰铢',      'direct', 1),
    ('USD', '美元',      'direct', 1),
    ('VND', '越南盾',    'direct', 1),
]

# ==================== HKD 基座（HKAB）====================
# HKAB 数据: 全部为直接标价法(1外币=?HKD), 大部分是 per 100, GBP 为 per 1
CURRENCIES_HKD = [
    ('AUD', '澳元',      'direct', 100),
    ('BND', '文莱元',    'direct', 100),
    ('CAD', '加元',      'direct', 100),
    ('CHF', '瑞士法郎',  'direct', 100),
    ('CNH', '离岸人民币', 'direct', 100),
    ('CNY', '人民币',    'direct', 100),
    ('DKK', '丹麦克朗',  'direct', 100),
    ('EUR', '欧元',      'direct', 100),
    ('GBP', '英镑',      'direct', 1),      # HKAB 官网: per 1
    ('INR', '印度卢比',  'direct', 100),
    ('JPY', '日元',      'direct', 100),
    ('KRW', '韩元',      'direct', 100),
    ('MYR', '林吉特',    'direct', 100),
    ('NOK', '挪威克朗',  'direct', 100),
    ('NTD', '新台币',    'direct', 100),
    ('NZD', '新西兰元',  'direct', 100),
    ('PHP', '菲律宾比索', 'direct', 100),
    ('PKR', '巴基斯坦卢比', 'direct', 100),
    ('SEK', '瑞典克朗',  'direct', 100),
    ('SGD', '新加坡元',  'direct', 100),
    ('THB', '泰铢',      'direct', 100),
    ('USD', '美元',      'direct', 100),
    ('ZAR', '兰特',      'direct', 100),
]

# 统一注册表
BASE_CONFIG = {
    'CNY': {
        'table': 'exchange_rates',
        'currencies': CURRENCIES_CNY,
        'source_name': '国家外汇管理局',
    },
    'IDR': {
        'table': 'exchange_rates_idr',
        'currencies': CURRENCIES_IDR,
        'source_name': 'Bank Indonesia',
    },
    'HKD': {
        'table': 'exchange_rates_hkd',
        'currencies': CURRENCIES_HKD,
        'source_name': '香港银行公会',
    },
}

# 基座币种的中文名
BASE_NAMES = {
    'CNY': '人民币',
    'IDR': '印尼盾',
    'HKD': '港币',
}

# 报价方法中文标签
QUOTE_METHOD_LABELS = {
    'direct': '直接标价法',
    'indirect': '间接标价法',
}

# 兼容旧引用
CURRENCIES = CURRENCIES_CNY
CURRENCY_CODES = [c[0] for c in CURRENCIES_CNY]
CURRENCY_NAMES_CN = [c[1] for c in CURRENCIES_CNY]


def _get_config(base: str):
    cfg = BASE_CONFIG.get(base.upper())
    if not cfg:
        raise ValueError(f'不支持的基座货币: {base}')
    return cfg


def _codes(base: str) -> list:
    return [c[0] for c in _get_config(base)['currencies']]


def _column_exists(conn, table, column):
    """检查表中是否存在指定列"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r['name'] == column for r in rows)


def init_db():
    """初始化所有数据库表结构（已存在则跳过）"""
    with get_conn() as conn:
        # 汇率数据表
        for base, cfg in BASE_CONFIG.items():
            table = cfg['table']
            cols = ', '.join([f'{code} REAL' for code, _, _, _ in cfg['currencies']])
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    {cols},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_date ON {table}(date)')

        # 币种元数据表（报价方法 + 单位）
        conn.execute('''
            CREATE TABLE IF NOT EXISTS currency_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_currency TEXT NOT NULL,
                target_currency TEXT NOT NULL,
                quote_method TEXT NOT NULL DEFAULT 'direct',
                unit INTEGER NOT NULL DEFAULT 1,
                UNIQUE(base_currency, target_currency)
            )
        ''')

        # 初始化/更新 currency_meta 数据
        for base, cfg in BASE_CONFIG.items():
            for code, name, method, unit in cfg['currencies']:
                conn.execute('''
                    INSERT INTO currency_meta (base_currency, target_currency, quote_method, unit)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(base_currency, target_currency) DO UPDATE SET
                        quote_method=excluded.quote_method,
                        unit=excluded.unit
                ''', (base, code, method, unit))

        # 抓取日志表
        conn.execute('''
            CREATE TABLE IF NOT EXISTS crawl_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT,
                end_date TEXT,
                rows_inserted INTEGER,
                rows_skipped INTEGER,
                status TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 迁移：旧表可能没有 source 列
        if not _column_exists(conn, 'crawl_log', 'source'):
            conn.execute('ALTER TABLE crawl_log ADD COLUMN source TEXT')

        # 用户偏好表：每个基座币种下用户自定义的"汇率趋势分析"默认对比货币
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_currency TEXT UNIQUE NOT NULL,
                selected_currencies TEXT NOT NULL,  -- JSON 数组
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


@contextmanager
def get_conn():
    """数据库连接上下文管理器"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ==================== 币种元数据查询 ====================

def get_currency_meta(base: str = 'CNY') -> list:
    """获取某基座下所有币种的元数据"""
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT target_currency AS code, quote_method, unit FROM currency_meta WHERE base_currency=? ORDER BY target_currency',
            (base.upper(),)
        ).fetchall()
        return [dict(r) for r in rows]


def get_currency_meta_map(base: str = 'CNY') -> dict:
    """获取某基座下币种元数据字典 {code: {quote_method, unit}}"""
    rows = get_currency_meta(base)
    return {r['code']: r for r in rows}


# ==================== 通用 CRUD ====================

def upsert_rates(date_str: str, rates: dict, base: str = 'CNY') -> int:
    """
    插入或更新某日数据
    :param base: CNY / IDR / HKD
    :return: 1=新插入或更新, 0=无变化
    """
    cfg = _get_config(base)
    table = cfg['table']
    codes = _codes(base)

    placeholders = ', '.join(['?'] * (1 + len(codes)))
    cols = ', '.join(['date'] + codes)
    update_cols = ', '.join([f'{c}=excluded.{c}' for c in codes])
    values = [date_str] + [rates.get(code) for code in codes]

    with get_conn() as conn:
        cur = conn.execute(
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders}) '
            f'ON CONFLICT(date) DO UPDATE SET {update_cols}, created_at=CURRENT_TIMESTAMP',
            values
        )
        conn.commit()
        return 1 if cur.lastrowid else 0


def upsert_many(rows: list, base: str = 'CNY') -> tuple:
    """
    批量插入
    :param rows: [(date_str, rates_dict), ...]
    :return: (inserted_count, skipped_count)
    """
    cfg = _get_config(base)
    table = cfg['table']
    codes = _codes(base)

    inserted, skipped = 0, 0
    with get_conn() as conn:
        for date_str, rates in rows:
            existing = conn.execute(f'SELECT id FROM {table} WHERE date=?', (date_str,)).fetchone()
            if existing:
                skipped += 1
                continue
            placeholders = ', '.join(['?'] * (1 + len(codes)))
            cols = ', '.join(['date'] + codes)
            values = [date_str] + [rates.get(code) for code in codes]
            conn.execute(f'INSERT INTO {table} ({cols}) VALUES ({placeholders})', values)
            inserted += 1
        conn.commit()
    return inserted, skipped


def get_by_date(date_str: str, base: str = 'CNY') -> dict:
    """按日期查单日数据"""
    cfg = _get_config(base)
    with get_conn() as conn:
        row = conn.execute(f'SELECT * FROM {cfg["table"]} WHERE date=?', (date_str,)).fetchone()
        return dict(row) if row else None


def get_latest(base: str = 'CNY') -> dict:
    """获取最新一条"""
    cfg = _get_config(base)
    with get_conn() as conn:
        row = conn.execute(f'SELECT * FROM {cfg["table"]} ORDER BY date DESC LIMIT 1').fetchone()
        return dict(row) if row else None


def get_range(start_date: str, end_date: str, base: str = 'CNY') -> list:
    """按日期范围查（升序）"""
    cfg = _get_config(base)
    with get_conn() as conn:
        rows = conn.execute(
            f'SELECT * FROM {cfg["table"]} WHERE date BETWEEN ? AND ? ORDER BY date ASC',
            (start_date, end_date)
        ).fetchall()
        return [dict(r) for r in rows]


def list_dates(limit: int = 30, base: str = 'CNY') -> list:
    """列出最近的 N 个有数据的日期"""
    cfg = _get_config(base)
    with get_conn() as conn:
        rows = conn.execute(
            f'SELECT date FROM {cfg["table"]} ORDER BY date DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [r['date'] for r in rows]


def get_recent_days(n: int = 30, base: str = 'CNY') -> list:
    """最近 N 个交易日（按日历日范围过滤，剔除更早的日期）"""
    cfg = _get_config(base)
    with get_conn() as conn:
        # 找到最新日期，倒推 N 天作为截止日期
        latest = conn.execute(
            f'SELECT MAX(date) AS d FROM {cfg["table"]}'
        ).fetchone()
        if not latest or not latest['d']:
            return []
        latest_date = datetime.strptime(latest['d'], '%Y-%m-%d')
        cutoff = (latest_date - timedelta(days=n - 1)).strftime('%Y-%m-%d')
        rows = conn.execute(
            f'SELECT * FROM {cfg["table"]} WHERE date >= ? ORDER BY date',
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_prev_date(current_date: str, base: str = 'CNY') -> dict:
    """获取指定日期的前一个有数据的日期的汇率（用于涨跌幅计算）"""
    cfg = _get_config(base)
    with get_conn() as conn:
        row = conn.execute(
            f'SELECT * FROM {cfg["table"]} WHERE date < ? ORDER BY date DESC LIMIT 1',
            (current_date,)
        ).fetchone()
        return dict(row) if row else None


def get_missing_dates(start_date: str, end_date: str, base: str = 'CNY') -> list:
    """获取指定区间内数据库中缺失的日期（仅返回工作日）"""
    from datetime import date, timedelta
    cfg = _get_config(base)
    with get_conn() as conn:
        rows = conn.execute(
            f'SELECT date FROM {cfg["table"]} WHERE date BETWEEN ? AND ?',
            (start_date, end_date)
        ).fetchall()
        exist = {r['date'] for r in rows}
    cur = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    missing = []
    while cur <= end:
        if cur.weekday() < 5:
            ds = cur.isoformat()
            if ds not in exist:
                missing.append(ds)
        cur += timedelta(days=1)
    return missing


def log_crawl(source, start_date, end_date, inserted, skipped, status, message=''):
    """记录抓取日志"""
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO crawl_log (source, start_date, end_date, rows_inserted, rows_skipped, status, message) VALUES (?,?,?,?,?,?,?)',
            (source, start_date, end_date, inserted, skipped, status, message)
        )
        conn.commit()


def count_all(base: str = 'CNY') -> int:
    cfg = _get_config(base)
    with get_conn() as conn:
        return conn.execute(f'SELECT COUNT(*) AS n FROM {cfg["table"]}').fetchone()['n']


# ==================== 统一视图（多基座合并）====================

def get_latest_dates() -> dict:
    """获取每个基座的最新数据日期 {base: date_str or None}"""
    out = {}
    with get_conn() as conn:
        for base, cfg in BASE_CONFIG.items():
            row = conn.execute(f'SELECT date FROM {cfg["table"]} ORDER BY date DESC LIMIT 1').fetchone()
            out[base] = row['date'] if row else None
    return out


def _build_unified_rows(rows_by_base: dict, prev_by_base: dict, date_by_base: dict) -> list:
    """
    将按 base 归类的 {date, rates} 展开为表格行
    :return: [{base, base_name, target, target_name, quote_method, quote_method_label, unit, rate, prev_rate, prev_date, diff, pct}, ...]
    """
    unified = []
    for base, row in rows_by_base.items():
        if not row:
            continue
        cfg = BASE_CONFIG[base]
        prev_row = prev_by_base.get(base)
        for code, name, method, unit in cfg['currencies']:
            cur = row.get(code)
            prev = prev_row.get(code) if prev_row else None
            if cur is None:
                continue
            diff = (cur - prev) if (prev is not None) else None
            pct = ((cur - prev) / prev * 100) if (prev is not None and prev != 0) else None
            unified.append({
                'base': base,
                'base_name': BASE_NAMES.get(base, base),
                'target': code,
                'target_name': name,
                'quote_method': method,
                'quote_method_label': QUOTE_METHOD_LABELS.get(method, method),
                'unit': unit,
                'rate': cur,
                'prev_rate': prev,
                'prev_date': date_by_base.get(base + '_prev'),
                'diff': diff,
                'pct': pct,
            })
    return unified


def get_unified_by_date(date_str: str) -> dict:
    """
    获取指定日期所有基座的统一视图
    :return: {
        'date': date_str,
        'available_bases': [base, ...],   # 该日有数据的基座
        'rows': [统一行, ...],
    }
    """
    rows_by_base = {}
    prev_by_base = {}
    prev_dates = {}
    available = []
    with get_conn() as conn:
        for base, cfg in BASE_CONFIG.items():
            row = conn.execute(
                f'SELECT * FROM {cfg["table"]} WHERE date=?', (date_str,)
            ).fetchone()
            if not row:
                continue
            available.append(base)
            rows_by_base[base] = dict(row)
            # 找该基座下前一个交易日
            prev = conn.execute(
                f'SELECT * FROM {cfg["table"]} WHERE date < ? ORDER BY date DESC LIMIT 1',
                (date_str,)
            ).fetchone()
            if prev:
                prev_by_base[base] = dict(prev)
                prev_dates[base + '_prev'] = prev['date']

    unified = _build_unified_rows(rows_by_base, prev_by_base, prev_dates)
    return {
        'date': date_str,
        'available_bases': available,
        'rows': unified,
    }


def get_unified_latest() -> dict:
    """
    获取所有基座的最新统一视图（按各基座最新日期分别取，不强求同一天）
    :return: {
        'date': 'max of latest dates',         # 用于展示的主日期
        'base_dates': {base: date_str or None}, # 每个基座各自的最新日期
        'available_bases': [...],
        'rows': [...],
    }
    """
    base_dates = get_latest_dates()
    if not any(base_dates.values()):
        return {'date': None, 'base_dates': base_dates, 'available_bases': [], 'rows': []}

    rows_by_base = {}
    prev_by_base = {}
    prev_dates = {}
    available = []

    with get_conn() as conn:
        for base, ds in base_dates.items():
            if not ds:
                continue
            cfg = BASE_CONFIG[base]
            row = conn.execute(
                f'SELECT * FROM {cfg["table"]} WHERE date=?', (ds,)
            ).fetchone()
            if not row:
                continue
            available.append(base)
            rows_by_base[base] = dict(row)
            prev = conn.execute(
                f'SELECT * FROM {cfg["table"]} WHERE date < ? ORDER BY date DESC LIMIT 1',
                (ds,)
            ).fetchone()
            if prev:
                prev_by_base[base] = dict(prev)
                prev_dates[base + '_prev'] = prev['date']

    unified = _build_unified_rows(rows_by_base, prev_by_base, prev_dates)
    # 主展示日期 = 各基座最新日期的最大值
    main_date = max(d for d in base_dates.values() if d) if any(base_dates.values()) else None
    return {
        'date': main_date,
        'base_dates': base_dates,
        'available_bases': available,
        'rows': unified,
    }


# ==================== 用户偏好 ====================

def get_user_preferences(base: str) -> dict:
    """
    获取某基座下用户保存的趋势分析默认对比货币
    返回: { 'base': 'CNY', 'currencies': ['USD', 'EUR', ...], 'updated_at': '...' } 或 None
    """
    base = base.upper()
    with get_conn() as conn:
        row = conn.execute(
            'SELECT base_currency, selected_currencies, updated_at FROM user_preferences WHERE base_currency=?',
            (base,)
        ).fetchone()
        if not row:
            return None
        try:
            currencies = json.loads(row['selected_currencies'])
        except (ValueError, TypeError):
            currencies = []
        return {
            'base': row['base_currency'],
            'currencies': currencies,
            'updated_at': row['updated_at'],
        }


def save_user_preferences(base: str, currencies: list) -> dict:
    """
    保存某基座下用户自定义的趋势分析默认对比货币
    :param currencies: 货币代码列表（建议 1-5 个）
    :return: { 'base': 'CNY', 'currencies': [...], 'count': N }
    """
    base = base.upper()
    if not isinstance(currencies, list):
        raise ValueError('currencies 必须是列表')
    # 清洗：去重、转大写、保留字符串
    cleaned = []
    seen = set()
    for c in currencies:
        s = str(c).strip().upper()
        if s and s not in seen:
            cleaned.append(s)
            seen.add(s)
    payload = json.dumps(cleaned, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute('''
            INSERT INTO user_preferences (base_currency, selected_currencies, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(base_currency) DO UPDATE SET
                selected_currencies=excluded.selected_currencies,
                updated_at=CURRENT_TIMESTAMP
        ''', (base, payload))
        conn.commit()
    return {'base': base, 'currencies': cleaned, 'count': len(cleaned)}


if __name__ == '__main__':
    init_db()
    for base, cfg in BASE_CONFIG.items():
        n = count_all(base)
        print(f'[{base}] 数据库初始化完成，共 {n} 条记录')
        print(f'  货币列表: {", ".join([c[0] for c in cfg["currencies"]])}')
        meta = get_currency_meta(base)
        for m in meta[:3]:
            print(f'    {m["code"]}: method={m["quote_method"]}, unit={m["unit"]}')
