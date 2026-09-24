# -*- coding: utf-8 -*-
"""独立运行：回填最近 N 天缺失数据"""
import logging
import sys
import argparse

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

import database
import scheduler

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='回填汇率历史数据')
    parser.add_argument('--days', type=int, default=30, help='回填天数（默认30）')
    parser.add_argument('--source', type=str, default='CNY', choices=['CNY', 'IDR', 'HKD', 'USD'],
                        help='数据源：CNY/IDR/HKD/USD(Frankfurter)，默认CNY')
    args = parser.parse_args()

    database.init_db()
    result = scheduler.backfill_recent(args.days, args.source)
    print(f'\n回填结果: {result}')
    print(f'当前数据库 [{args.source}]: {database.count_all(args.source)} 条')
