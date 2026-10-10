# CHANGELOG

> 项目进度与失败记录。按 CLAUDE.md 约定：每个实质步骤更新一次；失败必须记录（做了什么 / 怎么失败 / 错误关键信息 / 如何绕过）。

## 当前状态（2026-10-10）

- 应用已实现并提交（`fe91ed0`）：FastAPI 后端（`backend/`）+ Vue 3 前端（`frontend/`）+ 测试（`tests/`）
- 规划文档齐备：`docs/spec.md`、`docs/design.md`、`GLOSSARY.md`、`docs/adr/0001-0005`
- 执行票在 GitHub issue #2-#8（均 ready-for-agent，父 issue #1）
- **已按 ADR-0004 调整**：后端目录 `app/` → `backend/`；模型默认三项改由项目 `.env` 提供（`.env` 缺失拒绝启动，页面值优先）
- **已按 code-review 修复**：`.env` 裸键空值不再写 None（`or ""`）；默认值不落库（改 `.env` 重启即生效）；`_build_runner` 移入 try（构建失败 run 行落 failed 不卡 running）；`ensure_model_defaults` 去 `env_path` 参数；`EDITABLE_KEYS` 派生；脚本健壮性（json.dumps / 优雅处理缺失 `.env`）
- **2026-10-10 新增需求（设计已对齐，文档已落盘）**：
  1. **基线自动推进**（ADR-0005）：~~任务 ok 且处理了至少一个版本时自动前移~~ **已实现**（2026-10-10，TDD 5 测试，见「已完成」）
  2. **端口约定**：后端（uvicorn）= 5000 **已实现**（start.bat + 全引用同步）；前端 dev（vite）= 5100 **待实现**（#12）
  3. 明确**不删数据**（已核实代码无任何删 versions/runs 逻辑，增量模型本就只增不删）；launch_command 默认值**不动**（仅 LLM 分析输入，不执行）
- **执行票进展**（父 issue #9，互不阻塞）：#10 T8 基线自动推进 **已完成**；#11 T9 后端 5000 + start.bat **已完成**（见「已完成」2026-10-10 条目）；#12 T10 前端 dev 5100 + 代理 **待实现**
- **待办**：
  1. 用户填入 `.env` 的 `MODEL_API_KEY` 后触发一次真实任务，验证 LLM 分析链路
  2. 实现 T10 前端 dev 5100 + 代理（#12）
  3. **proxy 默认值双源分叉**（T8 code-review 发现 3，范围外未动）：`STATIC_DEFAULTS.proxy` 已改 `7897`，但 `fetcher.py:52` 构造器默认、spec/design 文档、前端 placeholder 仍是 `7981`。运行时走 `settings.proxy`（7897）行为正确，仅裸构造 `Fetcher()` 与文档不一致。单独处理

## 已完成

- 2026-10-09: setup-matt-pocock-skills 配置（CLAUDE.md Agent skills 块 + docs/agents/* + GitHub triage 标签 5 个）
- 2026-10-09: 设计拷问（grill-me / grill-with-docs）→ spec（issue #1）→ 7 张执行票（issue #2-#8）
- 2026-10-09: 应用主体实现（feat 提交 fe91ed0）
- 2026-10-09: spec 落盘 docs/spec.md 并提交推送（f57a633）
- 2026-10-09: 模型配置决策变更 → ADR-0004，design.md / spec.md 文档同步更新
- 2026-10-09: 按 ADR-0004 调整代码——`app/`→`backend/` 全量重命名（import/tests/scripts/ruff.toml 同步）；模型默认三项改由项目 `.env` 提供（新增 `load_env`/`ensure_model_defaults`/`EnvMissingError`，lifespan 启动时校验，`.env` 缺失拒绝启动）；新增 `.env.example`（入库）+ `.env`（不入库）；requirements.txt 加 `python-dotenv`；`scripts/` 移除 Hermes 配置读取改用 `.env`
- 2026-10-10: 基线自动推进决策（grill-with-docs）→ ADR-0005 + GLOSSARY「基线」定义更新 + design.md §5.1/§5.2/§8.5 + spec.md（settings 表/执行管线/用户故事 #20/Further Notes）文档同步；端口约定 后端 5000 / 前端 dev 5100 + start.bat 写入 design.md §8.5 与 spec.md
- 2026-10-10: 修复 dev 模式前端代理端口——`vite.config.ts` 代理目标 8000 → 8765（与后端启动端口一致）；此前 dev 模式（5173）下所有 `/api/*` 请求 500，页面保存配置静默失败，导致 settings 表残留占位符 `model_api_key`（`${HERMES_...}`）覆盖 `.env` 真实 key，任务持续 partial。已清除该坏覆盖，key 回落 `.env`
- 2026-10-10: **T8 基线自动推进（ADR-0005，issue #10）**——`runner._finish` 收尾处：run 记 `ok` 且 `versions_processed` 非空时，把 settings 表 `baseline_tag` 更新为本次处理版本中 tag 数字最大者（`tag_number` 比较），与 run 状态同一事务落库（避免「run 已 ok 但基线未动」）；partial/failed 不推进、处理 0 版本不写库。TDD 红绿 6 片：ok 推进 / partial 不推进 / failed 不推进 / 0 版本不写库（settings 无 baseline_tag 行）/ 手动更大值不被压过 / reanalyze tag 低于手动 baseline 时 ok run 不倒退。全量测试 78 通过（72+6）、ruff 通过
- 2026-10-10: **T9 后端端口 5000 + start.bat（issue #11）**——新建仓库根 `start.bat`（`conda activate llamacpp-monitor` 后 `uvicorn backend.main:app --host 127.0.0.1 --port 5000`）；`scripts/smoke_test.py` BASE 8765→5000；`.claude/settings.json` 批准命令端口 8765→5000 且 `app.main`→`backend.main`。`design.md` §8.5 端口约定本就写 5000（无需改）；`vite.config.ts` 代理目标属 #12 范围未动。验证：真实起后端于 5000，`/api/health` 返回 `{"status":"ok"}`，随后关闭
- 2026-10-10: **T8 code-review 修复**——①**单调性兜底**（发现 1，真 bug）：reanalyze 路径的 tag 不受下界约束，`max(processed)` 可能低于手动设的 baseline，致基线倒退；`_finish` 写入前与当前生效基线严格比较，更小/相等不写（不倒退、不压过手动值），非 bNNNNN 当前值保守不覆盖。补倒退路径测试（预置 b11518 analyzed=0 + 手动 baseline b11520 + 无新 release，断言 ok 后基线仍 b11520），已验证旧实现下该测试红。②**docstring 失真**（发现 4）：config.py 注明 `baseline_tag` 是「settings 表只存页面值」的例外（runner 自动推进会落库，遮蔽 STATIC_DEFAULTS 默认变更）
- 2026-10-09: code-review 8 项修复——①`load_env` 裸键空值用 `or ""`（不再写 None 触发 pydantic 500）；②`load_settings` 不再落库默认值（settings 表只存页面覆盖，改 `.env` 重启即生效，强化 ADR-0004 优先级）；③④`_build_runner` 移入 try（定时路径不静默崩溃、手动路径 run 行落 failed 不卡 running）；⑤`ensure_model_defaults` 去 `env_path` 参数（避免缓存后路径被忽略的契约陷阱）；⑥⑦脚本健壮性（`debug_llm` 用 json.dumps 构造请求体、两脚本优雅处理缺失 `.env`）；⑧`EDITABLE_KEYS` 改为派生（`STATIC_DEFAULTS + MODEL_KEYS`，免双份维护）。测试 72 通过、ruff 通过、E2E 两路径复验

## 失败记录

- **gh 不在 bash PATH**：`gh: command not found`。绕过：用绝对路径 `C:/Users/Jimmy-HAF700/AppData/Local/Programs/gh/gh.exe`。
- **GitHub API 直连/代理均 301**：`api.github.com` 需要 `-L` 跟随重定向。绕过：`curl -sL -x http://127.0.0.1:7981`。
- **gh issue create --body-file 传 MSYS 路径失败**：`open /tmp/t1.md: The system cannot find the path specified`（gh 是 Windows 原生程序，不认 MSYS 风格路径）。绕过：body 文件放 `$LOCALAPPDATA/Temp` 并传原生路径。
- **仓库改名**：`ggerganov/llama.cpp` → `ggml-org/llama.cpp`，旧地址 301。代码统一用新地址。
- **release body 无完整 commit 列表**：最初预期 release body 含 commit 列表，实际只有最新一条标题 + 下载链接。绕过：改用 compare API `compare/b{N-1}...b{N}`。
