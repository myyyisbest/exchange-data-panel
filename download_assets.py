# -*- coding: utf-8 -*-
"""
下载前端静态资源到本地
- bootstrap.min.css
- bootstrap.bundle.min.js
- chart.umd.min.js
"""
import sys
import urllib.request
import os

# 强制 stdout 用 utf-8（Windows 中文终端默认 gbk）
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

FILES = {
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css': 'css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js': 'js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js': 'js/chart.umd.min.js',
}


def download():
    for url, rel in FILES.items():
        target = os.path.join(STATIC_DIR, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        print(f'下载 {url} → {target}')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(target, 'wb') as f:
                f.write(data)
            print(f'  OK {len(data):,} 字节')
        except Exception as e:
            print(f'  FAIL: {e}')


if __name__ == '__main__':
    download()
    print('完成')
