# 汇率数据面板（多币种基座版）

一个基于 Flask + SQLite 的多数据源汇率采集、存储与可视化面板。自动抓取并每日定时同步官方汇率数据，提供 REST API 与内置 Web 界面，支持趋势图、涨跌幅与多基座币种对比。

## 简介

本面板聚合三大官方数据源的汇率数据，统一存储于本地 SQLite，按「基座货币」组织：

| 基座 | 数据源 | 货币数 | 价格类型 |
|------|--------|--------|----------|
| CNY（人民币） | 国家外汇管理局（SAFE） | 25 | 中间价 |
| IDR（印尼盾） | Bank Indonesia（BI） | 26 | 卖出价 |
| HKD（港币） | 香港银行公会（HKAB） | 23 | 卖出价 |

核心能力：

- 定时自动抓取 + 启动回填，断线自动补抓
- 多基座统一视图，一键切换 / 对比
- 趋势图：自定义输入货币与最多 5 个相对方货币
- 常用币种快捷过滤、涨跌幅高亮
- 完整 REST API，便于二次开发

## 安装

环境要求：Python 3.9+

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd "Exchange Data Panel"

# 2. 创建虚拟环境并安装依赖
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 准备本地配置（可选）
cp .env.example .env            # 按需修改端口、抓取时间等
```

首次启动时会自动创建 `data/exchange.db` 并初始化表结构。

## 使用

```bash
python app.py
```

启动后访问：

- Web 面板：http://localhost:41010
- 最新汇率：http://localhost:41010/api/latest?base=CNY

历史数据导入（可选）：

```bash
# 导入人民币历史 Excel
python import_excel.py "你的Excel文件路径.xlsx"

# 导入印尼盾历史 CSV
python import_bi_csv.py

# 导入港币历史 CSV
python import_hkd_csv.py
```

回填最近数据：

```bash
python backfill.py
```

## 配置

所有配置项均通过环境变量注入，默认值见 `.env.example`。可直接设置环境变量，或复制 `.env.example` 为 `.env` 后修改（程序启动时自动加载）。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_HOST` | `0.0.0.0` | 服务监听地址 |
| `APP_PORT` | `41010` | 服务监听端口 |
| `CRAWL_HOUR` | `10` | 每日定时抓取小时（24 小时制） |
| `CRAWL_MINUTE` | `0` | 每日定时抓取分钟 |
| `DB_PATH` | 项目下 `data/exchange.db` | SQLite 数据库路径 |

定时任务时区固定为 `Asia/Shanghai`（由 APScheduler 配置）。

## API 速览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/currencies?base=CNY` | 货币列表（含报价方法、单位） |
| GET | `/api/sources` | 全部数据源及币种元数据 |
| GET | `/api/stats` | 各基座统计信息 |
| GET | `/api/latest?base=CNY` | 最新汇率 |
| GET | `/api/date/2026-06-10?base=CNY` | 指定日期汇率 |
| GET | `/api/prev/2026-06-10?base=CNY` | 上一交易日汇率（算涨跌） |
| GET | `/api/range?base=CNY&start=...&end=...` | 区间查询 |
| GET | `/api/recent?base=CNY&days=30` | 最近 N 天（趋势图） |
| GET | `/api/dates?base=CNY&limit=30` | 最近有数据的日期 |
| GET | `/api/unified/latest` | 多基座统一最新视图 |
| GET | `/api/unified/date/2026-06-10` | 多基座统一指定日期视图 |
| POST | `/api/crawl` | 手动触发抓取（body: `source`/`start`/`end`） |
| POST | `/api/crawl-all` | 抓取全部数据源 |
| POST | `/api/backfill` | 回填最近 N 天 |
| GET / POST | `/api/preferences/<base>` | 用户趋势分析偏好 |


## 新前端（Next.js）

仓库内 `frontend/` 为 App Router + TypeScript + Tailwind 的暗色现代化界面，通过 **Next.js rewrites** 将浏览器同源请求 `/api/*` 代理到 Flask（默认 `http://127.0.0.1:41010`）。旧版 `templates/` + `static/` 仍由 Flask 直接提供，互不影响。

### 本地运行

```bash
# 终端 1：Flask API（项目根目录）
python app.py
# → http://localhost:41010

# 终端 2：Next.js 前端
cd frontend
cp .env.example .env.local   # 可选；修改 FLASK_API_ORIGIN
npm install
npm run dev
# → http://localhost:3000
```

| 服务 | 默认端口 | 说明 |
|------|----------|------|
| Flask | `41010` | API + 旧版 Web 面板 |
| Next.js | `3000` | 新前端；`/api/*` 代理到 Flask |

环境变量见 `frontend/.env.example`（`FLASK_API_ORIGIN`）。**实时数据与手动抓取依赖 Flask 已启动**；仅启动 Next 时界面可打开，但接口会失败。

V1 功能：多基座切换（CNY/IDR/HKD）、最新汇率表与涨跌幅、趋势图（选币种+区间）、多币种对比与常用币种过滤、手动抓取按钮、暗色主题。

## 项目结构

```
Exchange Data Panel/
├── app.py              # Flask 入口（API + 调度）
├── database.py         # SQLite 数据层
├── scraper.py          # CNY/SAFE 抓取器
├── scraper_bi.py       # IDR/BI 抓取器
├── scraper_hkab.py     # HKD/HKAB 抓取器
├── scheduler.py        # 定时调度与回填
├── backfill.py         # 回填脚本
├── import_excel.py     # 人民币历史 Excel 导入
├── import_bi_csv.py    # 印尼盾历史 CSV 导入
├── import_hkd_csv.py   # 港币历史 CSV 导入
├── download_assets.py  # 前端依赖下载工具
├── templates/          # 旧版页面模板（保留）
├── static/             # 旧版前端资源（保留）
├── frontend/           # Next.js 新前端（App Router）
├── requirements.txt
├── .env.example
└── README.md
```

## FAQ

**Q：启动后没有数据？**
A：首次启动会后台回填最近 30 天数据，受数据源接口响应速度影响，请稍候片刻；也可通过 `POST /api/crawl-all` 手动触发。

**Q：数据源抓取失败怎么办？**
A：各数据源均为第三方公开接口，偶发不稳定属正常。可通过 `GET /api/_debug/scrape?source=CNY` 查看原始返回排查；接口变更时需调整对应 `scraper_*.py`。

**Q：如何修改抓取时间？**
A：设置环境变量 `CRAWL_HOUR` 与 `CRAWL_MINUTE`（见「配置」）。

**Q：支持自定义基座货币吗？**
A：基座货币由 `database.py` 的 `BASE_CONFIG` 定义，新增需配套抓取器与表结构。

**Q：数据库文件在哪？**
A：默认在 `data/exchange.db`，可通过环境变量 `DB_PATH` 自定义。

## 许可证

[MIT License](./LICENSE)
