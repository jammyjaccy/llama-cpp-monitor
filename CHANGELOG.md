# CHANGELOG

> 项目进度与失败记录。按 CLAUDE.md 约定：每个实质步骤更新一次；失败必须记录（做了什么 / 怎么失败 / 错误关键信息 / 如何绕过）。

## 当前状态（2026-10-09）

- 应用已实现并提交（`fe91ed0`）：FastAPI 后端（`app/`）+ Vue 3 前端（`frontend/`）+ 测试（`tests/`）
- 规划文档齐备：`docs/spec.md`、`docs/design.md`、`GLOSSARY.md`、`docs/adr/0001-0004`
- 执行票在 GitHub issue #2-#8（均 ready-for-agent，父 issue #1）
- **待办（已对齐、未开工）**：
  1. 后端目录 `app/` → `backend/` 全量重命名（import/tests/scripts/文档引用）
  2. 模型默认配置改为项目 `.env`（`MODEL_BASE_URL`/`MODEL_API_KEY`/`MODEL_NAME`），提供 `.env.example`，`.env` 缺失时启动报错；页面值优先于 .env（ADR-0004）
  3. 用户后续可能追加更多修改（整理中）

## 已完成

- 2026-10-09: setup-matt-pocock-skills 配置（CLAUDE.md Agent skills 块 + docs/agents/* + GitHub triage 标签 5 个）
- 2026-10-09: 设计拷问（grill-me / grill-with-docs）→ spec（issue #1）→ 7 张执行票（issue #2-#8）
- 2026-10-09: 应用主体实现（feat 提交 fe91ed0）
- 2026-10-09: spec 落盘 docs/spec.md 并提交推送（f57a633）
- 2026-10-09: 模型配置决策变更 → ADR-0004，design.md / spec.md 文档同步更新

## 失败记录

- **gh 不在 bash PATH**：`gh: command not found`。绕过：用绝对路径 `C:/Users/Jimmy-HAF700/AppData/Local/Programs/gh/gh.exe`。
- **GitHub API 直连/代理均 301**：`api.github.com` 需要 `-L` 跟随重定向。绕过：`curl -sL -x http://127.0.0.1:7981`。
- **gh issue create --body-file 传 MSYS 路径失败**：`open /tmp/t1.md: The system cannot find the path specified`（gh 是 Windows 原生程序，不认 MSYS 风格路径）。绕过：body 文件放 `$LOCALAPPDATA/Temp` 并传原生路径。
- **仓库改名**：`ggerganov/llama.cpp` → `ggml-org/llama.cpp`，旧地址 301。代码统一用新地址。
- **release body 无完整 commit 列表**：最初预期 release body 含 commit 列表，实际只有最新一条标题 + 下载链接。绕过：改用 compare API `compare/b{N-1}...b{N}`。
