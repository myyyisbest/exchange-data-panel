# -*- coding: utf-8 -*-
"""
定时任务模块：APScheduler
- 每日 10:00 抓取全部数据源当日汇率入库
- CNY: 国家外汇管理局（支持历史范围查询）
- IDR: Bank Indonesia（仅最新）
- HKD: 香港银行公会 / HKMA（仅最新）
- USD: Frankfurter 市场中间价（支持历史范围查询）
- 启动时若发现"今天还没抓到"，自动补一次（catch-up）
- 单个源失败不会影响其他源和后续运行
"""
import logging
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

import database
import scraper
import scraper_bi
import scraper_hkab
import scraper_frankfurter

logger = logging.getLogger(__name__)

# 数据源注册表
SOURCES = {
    'CNY': {
        'scraper': scraper,
        'base': 'CNY',
        'supports_history': True,
        'name': 'SAFE（人民币）',
    },
    'IDR': {
        'scraper': scraper_bi,
        'base': 'IDR',
        'supports_history': False,
        'name': 'BI（印尼盾）',
    },
    'HKD': {
        'scraper': scraper_hkab,
        'base': 'HKD',
        'supports_history': False,
        'name': 'HKAB/HKMA（港币）',
    },
    'USD': {
        'scraper': scraper_frankfurter,
        'base': 'USD',
        'supports_history': True,
        'name': 'Frankfurter（美元市场中间价）',
    },
}


def crawl_source(source_key: str, target_date: str = None) -> dict:
    """
    抓取指定数据源的当日数据
    :param source_key: CNY / IDR / HKD / USD
    :param target_date: YYYY-MM-DD（不支持历史的源会忽略此参数）
    """
    cfg = SOURCES.get(source_key)
    if not cfg:
        return {'status': 'failed', 'message': f'未知数据源: {source_key}'}

    base = cfg['base']
    mod = cfg['scraper']
    name = cfg['name']

    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f'[{name}] 开始抓取 {target_date} ...')
    try:
        if cfg['supports_history']:
            rows = mod.fetch(target_date, target_date)
        else:
            rows = mod.fetch(target_date)
    except Exception as e:
        logger.error(f'[{name}] 抓取失败: {e}')
        database.log_crawl(source_key, target_date, target_date, 0, 0, 'failed', str(e))
        return {'status': 'failed', 'message': str(e), 'inserted': 0, 'source': source_key}

    if not rows:
        msg = f'未返回数据（{target_date}，可能是周末/节假日/未来日期）'
        logger.warning(f'[{name}] {msg}')
        database.log_crawl(source_key, target_date, target_date, 0, 0, 'empty', msg)
        return {'status': 'empty', 'message': msg, 'inserted': 0, 'source': source_key}

    inserted, skipped = database.upsert_many(rows, base=base)
    database.log_crawl(source_key, target_date, target_date, inserted, skipped, 'success')
    logger.info(f'[{name}] 抓取完成：插入 {inserted} 条，跳过 {skipped} 条')
    return {
        'status': 'success',
        'inserted': inserted,
        'skipped': skipped,
        'source': source_key,
        'rows': [{'date': d, **r} for d, r in rows],
    }


def crawl_range(start: str, end: str, source_key: str = 'CNY') -> dict:
    """
    抓取指定区间数据入库（CNY/USD 支持区间；IDR/HKD 只抓 end 当天）
    """
    cfg = SOURCES.get(source_key)
    if not cfg:
        return {'status': 'failed', 'message': f'未知数据源: {source_key}'}

    if not cfg['supports_history']:
        # 不支持历史的源，只抓 end 日期当天
        return crawl_source(source_key, end)

    name = cfg['name']
    base = cfg['base']
    logger.info(f'[{name}] 开始抓取 {start} ~ {end} ...')
    try:
        rows = cfg['scraper'].fetch(start, end)
    except Exception as e:
        logger.error(f'[{name}] 抓取失败: {e}')
        database.log_crawl(source_key, start, end, 0, 0, 'failed', str(e))
        return {'status': 'failed', 'message': str(e), 'inserted': 0, 'source': source_key}

    if not rows:
        msg = f'未返回数据（{start}~{end}，可能是周末/节假日/未来日期）'
        logger.warning(f'[{name}] {msg}')
        database.log_crawl(source_key, start, end, 0, 0, 'empty', msg)
        return {'status': 'empty', 'message': msg, 'inserted': 0, 'source': source_key}

    inserted, skipped = database.upsert_many(rows, base=base)
    database.log_crawl(source_key, start, end, inserted, skipped, 'success')
    logger.info(f'[{name}] 抓取完成：插入 {inserted} 条，跳过 {skipped} 条')
    return {
        'status': 'success',
        'inserted': inserted,
        'skipped': skipped,
        'source': source_key,
        'rows': [{'date': d, **r} for d, r in rows],
    }


def backfill_recent(days: int = 30, source_key: str = 'CNY') -> dict:
    """回填最近 N 天缺失的工作日数据（CNY / USD 等支持历史的源）"""
    cfg = SOURCES.get(source_key)
    if not cfg or not cfg['supports_history']:
        return {
            'status': 'skipped',
            'message': f'{source_key} 不支持历史回填',
            'inserted': 0, 'skipped': 0,
        }

    name = cfg['name']
    base = cfg['base']
    mod = cfg['scraper']
    end = date.today()
    start = end - timedelta(days=days)
    missing = database.get_missing_dates(start.isoformat(), end.isoformat(), base=base)
    if not missing:
        return {'status': 'success', 'inserted': 0, 'skipped': 0, 'message': '无缺失日期'}

    logger.info(f'[{name}] 回填 {len(missing)} 个缺失日期: {missing[:5]}...')
    total_ins, total_skip = 0, 0
    for ds in missing:
        try:
            rows = mod.fetch(ds, ds)
            if rows:
                ins, skp = database.upsert_many(rows, base=base)
                total_ins += ins
                total_skip += skp
        except Exception as e:
            logger.error(f'[{name}] 回填 {ds} 失败: {e}')
    return {
        'status': 'success',
        'inserted': total_ins,
        'skipped': total_skip,
        'message': f'共处理 {len(missing)} 个缺失日',
    }


def crawl_all():
    """抓取全部数据源（供定时任务调用）—— 单个源失败不影响其他源"""
    results = {}
    today = date.today().isoformat()
    logger.info(f'[定时任务] 开始抓取 {today} 全部数据源')
    for key in SOURCES:
        try:
            results[key] = crawl_source(key)
        except Exception as e:
            # 双保险：crawl_source 内部已经捕获并 log 了，这里只是兜底
            logger.error(f'定时任务抓取 {key} 异常: {e}', exc_info=True)
            results[key] = {'status': 'failed', 'message': str(e), 'source': key}
    success = sum(1 for r in results.values() if r.get('status') == 'success')
    logger.info(f'[定时任务] 本轮抓取完成：{success}/{len(SOURCES)} 成功')
    return results


def _on_job_error(event):
    """APScheduler 事件回调：任务执行出错时记录但不传播（避免进程被拖死）"""
    logger.error(f'[定时任务] job_id={event.job_id} exception: {event.exception}', exc_info=True)


def _on_job_missed(event):
    """APScheduler 事件回调：错过执行时间时记录"""
    logger.warning(f'[定时任务] job_id={event.job_id} miss: scheduled={event.scheduled_run_time}')


def catch_up_if_needed():
    """
    启动时检查：若今天还没抓到数据（且当前已过抓取时间），立刻补一次。
    这样：
    - 应用重启后不会因为错过 10:00 而漏跑
    - 长时间挂掉后仍能补当天数据
    """
    now = datetime.now()
    today = now.date().isoformat()
    # 抓取时间点
    today_crawl_at = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now < today_crawl_at:
        logger.info(f'[启动检查] 当前 {now.strftime("%H:%M")}，未到 10:00 抓取时间，跳过 catch-up')
        return

    for key, cfg in SOURCES.items():
        try:
            latest = database.get_latest(cfg['base'])
            if latest and latest.get('date') == today:
                logger.info(f'[{cfg["name"]}] 今日已抓取 ({today})，跳过 catch-up')
                continue
            logger.info(f'[{cfg["name"]}] 今日 {today} 尚未抓取，启动 catch-up ...')
            try:
                crawl_source(key, today)
            except Exception as e:
                logger.error(f'[{cfg["name"]}] catch-up 失败: {e}', exc_info=True)
        except Exception as e:
            logger.error(f'[{key}] catch-up 检查失败: {e}', exc_info=True)


def create_scheduler(crawl_hour: int = 10, crawl_minute: int = 0) -> BackgroundScheduler:
    """
    创建调度器（每日 10:00 触发全部数据源）
    - misfire_grace_time=600: 错过 10 分钟内还会补跑一次
    - coalesce=True: 多次错过合并成一次执行
    - max_instances=1: 同一时间只允许一个实例
    """
    sched = BackgroundScheduler(timezone='Asia/Shanghai')

    # 注册事件监听（任务出错/错过都不让进程挂掉）
    sched.add_listener(_on_job_error, EVENT_JOB_ERROR)
    sched.add_listener(_on_job_missed, EVENT_JOB_MISSED)

    sched.add_job(
        crawl_all,
        CronTrigger(hour=crawl_hour, minute=crawl_minute, timezone='Asia/Shanghai'),
        id='daily_crawl_all',
        name=f'每日{crawl_hour:02d}:{crawl_minute:02d}抓取全部汇率',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )
    return sched


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    database.init_db()
    print('测试抓取所有数据源...')
    for key in SOURCES:
        print(f'\n--- {key} ---')
        print(crawl_source(key))
