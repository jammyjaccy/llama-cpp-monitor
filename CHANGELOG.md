# CHANGELOG

> 项目进度与失败记录。按 CLAUDE.md 约定：每个实质步骤更新一次；失败必须记录（做了什么 / 怎么失败 / 错误关键信息 / 如何绕过）。

## 当前状态（2026-10-09）

- 应用已实现并提交（`fe91ed0`）：FastAPI 后端（`backend/`）+ Vue 3 前端（`frontend/`）+ 测试（`tests/`）
- 规划文档齐备：`docs/spec.md`、`docs/design.md`、`GLOSSARY.md`、`docs/adr/0001-0004`
- 执行票在 GitHub issue #2-#8（均 ready-for-agent，父 issue #1）
- **已按 ADR-0004 调整**：后端目录 `app/` → `backend/`；模型默认三项改由项目 `.env` 提供（`.env` 缺失拒绝启动，页面值优先）
- **已按 code-review 修复**：`.env` 裸键空值不再写 None（`or ""`）；默认值不落库（改 `.env` 重启即生效）；`_build_runner` 移入 try（构建失败 run 行落 failed 不卡 running）；`ensure_model_defaults` 去 `env_path` 参数；`EDITABLE_KEYS` 派生；脚本健壮性（json.dumps / 优雅处理缺失 `.env`）
- **待办**：
  1. 用户填入 `.env` 的 `MODEL_API_KEY` 后触发一次真实任务，验证 LLM 分析链路
  2. 用户后续可能追加更多修改（整理中）

## 已完成

- 2026-10-09: setup-matt-pocock-skills 配置（CLAUDE.md Agent skills 块 + docs/agents/* + GitHub triage 标签 5 个）
- 2026-10-09: 设计拷问（grill-me / grill-with-docs）→ spec（issue #1）→ 7 张执行票（issue #2-#8）
- 2026-10-09: 应用主体实现（feat 提交 fe91ed0）
- 2026-10-09: spec 落盘 docs/spec.md 并提交推送（f57a633）
- 2026-10-09: 模型配置决策变更 → ADR-0004，design.md / spec.md 文档同步更新
- 2026-10-09: 按 ADR-0004 调整代码——`app/`→`backend/` 全量重命名（import/tests/scripts/ruff.toml 同步）；模型默认三项改由项目 `.env` 提供（新增 `load_env`/`ensure_model_defaults`/`EnvMissingError`，lifespan 启动时校验，`.env` 缺失拒绝启动）；新增 `.env.example`（入库）+ `.env`（不入库）；requirements.txt 加 `python-dotenv`；`scripts/` 移除 Hermes 配置读取改用 `.env`
- 2026-10-09: code-review 8 项修复——①`load_env` 裸键空值用 `or ""`（不再写 None 触发 pydantic 500）；②`load_settings` 不再落库默认值（settings 表只存页面覆盖，改 `.env` 重启即生效，强化 ADR-0004 优先级）；③④`_build_runner` 移入 try（定时路径不静默崩溃、手动路径 run 行落 failed 不卡 running）；⑤`ensure_model_defaults` 去 `env_path` 参数（避免缓存后路径被忽略的契约陷阱）；⑥⑦脚本健壮性（`debug_llm` 用 json.dumps 构造请求体、两脚本优雅处理缺失 `.env`）；⑧`EDITABLE_KEYS` 改为派生（`STATIC_DEFAULTS + MODEL_KEYS`，免双份维护）。测试 72 通过、ruff 通过、E2E 两路径复验

## 失败记录

- **gh 不在 bash PATH**：`gh: command not found`。绕过：用绝对路径 `C:/Users/Jimmy-HAF700/AppData/Local/Programs/gh/gh.exe`。
- **GitHub API 直连/代理均 301**：`api.github.com` 需要 `-L` 跟随重定向。绕过：`curl -sL -x http://127.0.0.1:7981`。
- **gh issue create --body-file 传 MSYS 路径失败**：`open /tmp/t1.md: The system cannot find the path specified`（gh 是 Windows 原生程序，不认 MSYS 风格路径）。绕过：body 文件放 `$LOCALAPPDATA/Temp` 并传原生路径。
- **仓库改名**：`ggerganov/llama.cpp` → `ggml-org/llama.cpp`，旧地址 301。代码统一用新地址。
- **release body 无完整 commit 列表**：最初预期 release body 含 commit 列表，实际只有最新一条标题 + 下载链接。绕过：改用 compare API `compare/b{N-1}...b{N}`。
