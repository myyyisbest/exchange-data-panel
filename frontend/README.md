# 汇率数据面板 · Next.js 前端

暗色现代化 UI，通过 Next.js rewrites 将浏览器请求的 `/api/*` 代理到 Flask 后端。

## 开发

先启动 Flask（默认 `http://127.0.0.1:41010`），再：

```bash
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
