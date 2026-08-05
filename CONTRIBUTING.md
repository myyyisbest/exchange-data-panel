# 贡献指南

感谢你对本项目的关注！欢迎提交 Issue 和 Pull Request。

## 开发环境搭建

1. Fork 本仓库并克隆到本地
2. 安装依赖（参见 README.md 中的安装说明）
3. 复制 `.env.example` 为 `.env` 并填写本地配置
4. 启动开发服务器

## 代码规范

- 遵循项目现有的代码风格
- 提交前确保代码通过 lint 检查
- 函数命名语义化，单一职责
- 关键逻辑添加中文注释

## 提交规范

提交信息格式：`<type>: <description>`

| type | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 Bug |
| docs | 文档变更 |
| style | 代码格式（不影响功能） |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具变更 |

## Pull Request 流程

1. 基于 `main` 分支创建特性分支：`git checkout -b feat/your-feature`
2. 确保所有测试通过
3. 提交 PR 并描述变更内容
4. 等待 Code Review

## 安全须知

- **禁止提交** `.env` 文件、数据库文件、真实业务数据
- 发现安全漏洞请通过 Issue 私密报告，不要公开提交

## 许可证

提交的代码将在 [MIT License](./LICENSE) 下发布。
