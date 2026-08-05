# -*- coding: utf-8 -*-
"""
汇率数据面板 - Flask 后端入口（多币种基座版）
提供 REST API + 静态前端页面 + 定时调度
"""
import logging
import os
import threading
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, render_template, request

# 自动加载 .env（存在时），便于本地配置；缺失则跳过，不强制依赖
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database
import scheduler as sched_mod
import scraper
import scraper_bi
import scraper_hkab

# ----------- 配置（支持环境变量覆盖，便于容器化部署）-----------
HOST = os.environ.get('APP_HOST', '0.0.0.0')
PORT = int(os.environ.get('APP_PORT', '41010'))
CRAWL_HOUR = int(os.environ.get('CRAWL_HOUR', '10'))
CRAWL_MINUTE = int(os.environ.get('CRAWL_MINUTE', '0'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('app')

# ----------- Flask -----------
app = Flask(__name__, static_folder='static', static_url_path='/exchange/static', template_folder='templates')


def _get_base():
    """从 query 参数获取基座货币，默认 CNY"""
    base = request.args.get('base', 'CNY').upper()
    if base not in database.BASE_CONFIG:
        raise ValueError(f'不支持的基座货币: {base}')
    return base


# ====== 页面 ======
@app.route('/')
def index():
    # 将所有币种的元数据传给前端（含报价方法和单位）
    currencies_meta = {}
    for base, cfg in database.BASE_CONFIG.items():
        currencies_meta[base] = [
            {'code': c, 'name': n, 'quote_method': qm, 'unit': u}
            for c, n, qm, u in cfg['currencies']
        ]
    return render_template(
        'index.html',
        currencies_meta=currencies_meta,
        sources={k: v['source_name'] for k, v in database.BASE_CONFIG.items()},
        base_names=database.BASE_NAMES,
    )


# ====== 元数据 ======
@app.route('/api/currencies')
def api_currencies():
    """货币列表（含报价方法和单位）"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify([
        {'code': c, 'name': n, 'quote_method': qm, 'unit': u}
        for c, n, qm, u in database.BASE_CONFIG[base]['currencies']
    ])


@app.route('/api/sources')
def api_sources():
    """数据源列表（含币种元数据）"""
    return jsonify({
        k: {
            'name': v['source_name'],
            'currency_count': len(v['currencies']),
            'currencies': [c[0] for c in v['currencies']],
            'currency_meta': [
                {'code': c, 'name': n, 'quote_method': qm, 'unit': u}
                for c, n, qm, u in v['currencies']
            ],
        }
        for k, v in database.BASE_CONFIG.items()
    })


@app.route('/api/stats')
def api_stats():
    """统计信息（全币种）"""
    stats = {}
    for base in database.BASE_CONFIG:
        latest = database.get_latest(base)
        stats[base] = {
            'total_records': database.count_all(base),
            'latest_date': latest['date'] if latest else None,
            'latest_updated_at': latest.get('created_at') if latest else None,
        }
    return jsonify({
        'sources': stats,
        'crawl_hour': CRAWL_HOUR,
        'crawl_minute': CRAWL_MINUTE,
    })


# ====== 数据查询 ======
@app.route('/api/latest')
def api_latest():
    """最新一条数据"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    row = database.get_latest(base)
    if not row:
        return jsonify({'error': 'no data yet'}), 404
    return jsonify(row)


@app.route('/api/date/<date_str>')
def api_by_date(date_str):
    """按日期查询"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'invalid date format, expected YYYY-MM-DD'}), 400
    row = database.get_by_date(date_str, base)
    if not row:
        return jsonify({'error': f'no data for {date_str}'}), 404
    return jsonify(row)


@app.route('/api/prev/<date_str>')
def api_prev_date(date_str):
    """获取指定日期的前一个交易日数据（用于计算涨跌幅）"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'invalid date format'}), 400
    row = database.get_prev_date(date_str, base)
    if not row:
        return jsonify({'error': f'no prev data before {date_str}'}), 404
    return jsonify(row)


@app.route('/api/range')
def api_range():
    """日期范围查询"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        return jsonify({'error': 'need start and end params (YYYY-MM-DD)'}), 400
    try:
        datetime.strptime(start, '%Y-%m-%d')
        datetime.strptime(end, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'invalid date format'}), 400
    if start > end:
        return jsonify({'error': 'start must be <= end'}), 400
    rows = database.get_range(start, end, base)
    return jsonify({
        'start': start,
        'end': end,
        'count': len(rows),
        'rows': rows,
    })


@app.route('/api/recent')
def api_recent():
    """最近 N 天（默认 30），用于趋势图"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        days = int(request.args.get('days', 30))
    except ValueError:
        days = 30
    days = max(1, min(days, 365))
    rows = database.get_recent_days(days, base)
    return jsonify({
        'days': days,
        'count': len(rows),
        'rows': rows,
    })


@app.route('/api/dates')
def api_dates():
    """列出最近 N 个有数据的日期"""
    try:
        base = _get_base()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        limit = int(request.args.get('limit', 30))
    except ValueError:
        limit = 30
    limit = max(1, min(limit, 365))
    return jsonify({'dates': database.list_dates(limit, base)})


# ====== 统一视图（合并 CNY/IDR/HKD 三个基座）======
@app.route('/api/unified/latest')
def api_unified_latest():
    """获取所有基座的最新数据，按行展开为统一表格"""
    return jsonify(database.get_unified_latest())


@app.route('/api/unified/date/<date_str>')
def api_unified_by_date(date_str):
    """获取指定日期所有基座的统一表格数据"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'invalid date format, expected YYYY-MM-DD'}), 400
    return jsonify(database.get_unified_by_date(date_str))


# ====== 手动触发 ======
@app.route('/api/crawl', methods=['POST'])
def api_crawl():
    """
    手动触发抓取
    Body JSON (可选):
      { "source": "CNY", "start": "2026-06-01", "end": "2026-06-04" }
    不传 source 则默认 CNY
    不传 start/end 则抓取当日
    """
    body = request.get_json(silent=True) or {}
    source = body.get('source', 'CNY').upper()
    start = body.get('start') or date.today().isoformat()
    end = body.get('end') or start
    try:
        datetime.strptime(start, '%Y-%m-%d')
        datetime.strptime(end, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'invalid date format'}), 400
    if start > end:
        return jsonify({'error': 'start must be <= end'}), 400
    result = sched_mod.crawl_range(start, end, source)
    return jsonify(result)


@app.route('/api/crawl-all', methods=['POST'])
def api_crawl_all():
    """手动触发抓取所有数据源"""
    result = sched_mod.crawl_all()
    return jsonify(result)


@app.route('/api/backfill', methods=['POST'])
def api_backfill():
    """回填最近 N 天（仅 CNY 有效）"""
    body = request.get_json(silent=True) or {}
    days = int(body.get('days', 30))
    source = body.get('source', 'CNY').upper()
    days = max(1, min(days, 365))
    result = sched_mod.backfill_recent(days, source)
    return jsonify(result)


# ====== 调试：直接看 scrape 原文 ======
@app.route('/api/_debug/scrape')
def api_debug_scrape():
    """调试用：直接调用 scraper 并返回原始数据"""
    source = request.args.get('source', 'CNY').upper()
    start = request.args.get('start', date.today().isoformat())
    end = request.args.get('end', start)
    if source == 'CNY':
        rows = scraper.fetch(start, end)
    elif source == 'IDR':
        rows = scraper_bi.fetch(start)
    elif source == 'HKD':
        rows = scraper_hkab.fetch(start)
    else:
        return jsonify({'error': 'invalid source'}), 400
    return jsonify(rows)


# ====== 用户偏好（每个基座币种独立的趋势分析默认货币）======
@app.route('/api/preferences/<base>', methods=['GET'])
def api_get_preferences(base: str):
    """获取某基座下用户保存的默认趋势对比货币"""
    try:
        cfg = database._get_config(base)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    pref = database.get_user_preferences(base)
    if not pref:
        return jsonify({'base': base.upper(), 'currencies': [], 'updated_at': None})
    return jsonify(pref)


@app.route('/api/preferences/<base>', methods=['POST'])
def api_save_preferences(base: str):
    """
    保存某基座下用户自定义的趋势分析默认对比货币
    Body: { "currencies": ["USD", "EUR", "JPY", "GBP", "AUD"] }
    最多 5 个，去重
    """
    try:
        cfg = database._get_config(base)  # 校验 base 合法
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    body = request.get_json(silent=True) or {}
    currencies = body.get('currencies', [])
    if not isinstance(currencies, list):
        return jsonify({'error': 'currencies 必须是列表'}), 400
    if len(currencies) > 5:
        return jsonify({'error': '最多只能保存 5 个货币'}), 400

    # 校验每个货币代码属于该基座下合法列表
    valid_codes = {c[0] for c in cfg['currencies']}
    invalid = [c for c in currencies if str(c).upper() not in valid_codes]
    if invalid:
        return jsonify({'error': f'非法货币代码: {invalid}', 'valid': sorted(valid_codes)}), 400

    try:
        result = database.save_user_preferences(base, currencies)
        return jsonify({'status': 'success', **result})
    except Exception as e:
        logger.error(f'保存用户偏好失败: {e}')
        return jsonify({'status': 'failed', 'error': str(e)}), 500


# ----------- 启动 -----------
def init_app():
    database.init_db()
    for base in database.BASE_CONFIG:
        logger.info(f'[{base}] 数据库初始化完成，当前 {database.count_all(base)} 条记录')

    # 启动时跑一次回填（后台线程，不阻塞启动）
    def _backfill_async():
        try:
            result = sched_mod.backfill_recent(30, 'CNY')
            logger.info(f'启动回填(CNY): {result}')
        except Exception as e:
            logger.error(f'启动回填失败: {e}')

    threading.Thread(target=_backfill_async, daemon=True).start()

    # 启动时检查是否需要补抓今日数据（避免应用挂掉后错过 10:00）
    def _catch_up_async():
        try:
            sched_mod.catch_up_if_needed()
        except Exception as e:
            logger.error(f'启动 catch-up 失败: {e}')

    threading.Thread(target=_catch_up_async, daemon=True).start()

    # 启动定时任务
    sched = sched_mod.create_scheduler(CRAWL_HOUR, CRAWL_MINUTE)
    sched.start()
    logger.info(f'定时任务已启动：每日 {CRAWL_HOUR:02d}:{CRAWL_MINUTE:02d} 抓取全部汇率')
    return sched


if __name__ == '__main__':
    init_app()
    print(f'\n{"="*60}')
    print(f'  汇率数据面板已启动')
    print(f'  访问: http://localhost:{PORT}')
    print(f'  API:  http://localhost:{PORT}/api/latest')
    print(f'{"="*60}\n')
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
