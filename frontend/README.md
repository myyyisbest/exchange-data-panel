# 汇率数据面板 · Next.js 前端

暗色仪表盘 UI：首页基座概览卡片 → 点击进入详情（表格 / 趋势 / 对比）。
官方三源（SAFE / BI / HKAB）与 Frankfurter 市场参考分区展示。
浏览器请求的 `/api/*` 经 Next.js rewrites 代理到 Flask 后端。

## 开发

先启动 Flask（默认 `http://127.0.0.1:41010`），再：

```bash
cd frontend
cp .env.example .env.local   # 可选，修改 FLASK_API_ORIGIN
npm install
npm run dev
```

默认访问 http://localhost:3000 。

环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `FLASK_API_ORIGIN` | `http://127.0.0.1:41010` | Next 服务端 rewrite 目标 |

## 构建

```bash
npm run build
npm start
```

## UI 结构

- **概览**：`BaseOverviewCards` — CNY / IDR / HKD 官方卡片 + USD 市场参考区
- **详情**：`RatesTable` + `ComparePanel`（含 `TrendChart`）+ `FavoritesBar`
- **顶栏**：抓取按钮、统计摘要、各源日期徽章
