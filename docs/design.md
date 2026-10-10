# llama-cpp-monitor 设计文档

> 状态：已对齐，待实现。2026-10-09 经逐轮拷问确认。

## 1. 目标

监控 llama.cpp（`ggml-org/llama.cpp`，原 ggerganov 已改名）的版本更新：

- 定时（默认 2 小时，**间隔可调**）检查 GitHub release 页面
- 分析每个新版本的更新内容，判断**哪些对本地跑 llama.cpp 有正提升**
- 分析新版本**对用户本地启动命令是否有影响**
- 每个版本一条记录落库（SQLite），**新增命令单独记录**
- **增量任务**：只处理上次处理到之后的新版本
- Web 前端：查看任务执行情况 + 报告分页浏览
- 支持**手动触发**执行

## 2. 范围

**IN**：release 监控、LLM 分析、新增命令检测、SQLite 存储、Web UI（状态 + 分页报告 + 配置页）、内置定时调度、手动触发。

**OUT**：多仓库监控（只盯 llama.cpp）、多用户/认证、下载并自动升级本地二进制、非 Windows 二进制检测。

## 3. 关键环境事实（已验证）

| 事实 | 值 |
|---|---|
| 仓库地址 | `ggml-org/llama.cpp`（旧 `ggerganov/llama.cpp` 301 跳转，代码用新地址） |
| 发版频率 | 约 3-4 版/天，tag 格式 `bNNNNN` |
| release body | **不含完整 commit 列表**（仅最新一条 commit 标题 + 各平台下载链接） |
| 完整变更来源 | compare API：`/repos/ggml-org/llama.cpp/compare/b{N-1}...b{N}`，返回 `total_commits` + 每条 commit 消息，已验证可用 |
| 网络 | 直连 GitHub 301，需走本地代理 `http://127.0.0.1:7981`（代理做成配置项） |
| 用户当前版本 | b11514，经 llama.cpp-hub v0.9.8.3 分发，3×CUDA + MTP 投机解码 + flash-attn |
| 用户启动命令 | 见 §8 配置（llama-server.exe，关键 flag：`--spec-type draft-mtp --flash-attn on --split-mode layer --tensor-split --ctx-checkpoints --load-mode dio --fit` 等） |
| Python | 3.14.7 / uv |

## 4. 架构

```
┌─────────────────────────────────────────────────────┐
│  FastAPI 应用（单进程，绑定 127.0.0.1）               │
│  ├── Web UI 路由（Jinja 壳或直接托管前端静态产物）      │
│  ├── REST API（/api/runs /api/reports /api/settings）│
│  ├── APScheduler 内置定时调度（间隔可配置）            │
│  └── 监控引擎                                         │
│      ├── Fetcher：releases 列表 + compare API（走代理）│
│      ├── 文本扫描：release/commit 文本找 ADD --xxxx   │
│      ├── LLM 分析：正提升判断 + 启动命令影响分析        │
│      │   （可上网搜索辅助；模型可配置）                 │
│      └── 条件 --help diff：仅当 LLM 判定有正提升时，    │
│          下载该版 Windows 二进制，跑 --help 与上版 diff │
└─────────────────────────────────────────────────────┘
        │                          │
   SQLite (H:\data\llamacpp-monitor)   Vue 3 + Vite + Element Plus
```

**技术栈（已确认）**：

- 后端：Python + FastAPI + APScheduler + SQLite（标准库 sqlite3 或 SQLAlchemy，实现时定）
- 前端：**Vue 3 + Vite + Element Plus**，独立工程独立构建，产物由 FastAPI 静态托管
- **架构约束：前后端严格分离，REST API 是唯一通信面**——前端不直接访问 SQLite 或引擎（ADR-0001）
- 前端访问：**仅 127.0.0.1，无认证**
- 调度：**应用内置**（APScheduler，ADR-0002），页面可改间隔、可点「立即执行」
- Python 环境：**conda 虚拟环境 `llamacpp-monitor`**，项目所有依赖装在此环境，运行也用它；后端依赖写入根目录 `requirements.txt`（前端 Node 依赖由 package.json 管理）

**ADR**：架构决策记录见 `docs/adr/`——0001 前后端分离、0002 内置调度、0003 条件 help-diff、0004 模型默认配置存 .env、0005 基线自动推进为持久进度游标。

**目录约定**：后端代码目录为 `backend/`（原 `app/` 重命名，import 与文档引用同步更新）。

## 4.5 技术选型清单

**后端（Python，conda 环境 `llamacpp-monitor`）**

| 层 | 技术 | 说明 |
|---|---|---|
| Python | 3.14 | conda 环境 `llamacpp-monitor` |
| Web 框架 | FastAPI + Pydantic | API 与数据校验 |
| ASGI 服务器 | uvicorn | 生产与开发统一 |
| 调度 | APScheduler | 内置调度（ADR-0002） |
| 数据库 | SQLite | `H:\data\llamacpp-monitor\monitor.db` |
| ORM | **SQLAlchemy 2.x** | 四表模型集中定义；不用 Alembic 迁移（个人工具，schema 变更手动执行） |
| HTTP 客户端 | httpx | GitHub API（走代理）+ LLM 调用，一个依赖两用 |
| LLM 调用 | OpenAI 兼容接口（`/v1/chat/completions`），httpx 直调 | 不引 openai SDK，少一个依赖 |
| 文本 diff | 标准库 difflib | --help 对比 |
| 二进制解压 | 标准库 zipfile | 用后删 zip，只留 help 文本 |
| 测试 | pytest | |

**前端（独立工程 `frontend/`，Node 依赖由 package.json 管理）**

| 层 | 技术 | 说明 |
|---|---|---|
| 框架 | Vue 3 + Vite | |
| 语言 | **TypeScript** | Vite 官方模板默认，API 响应结构有类型约束 |
| UI 库 | Element Plus | 分页表格、表单 |
| 路由 | vue-router | 三页面：任务执行 / 报告 / 配置 |
| 状态管理 | Pinia | 任务状态、配置 |
| HTTP | axios | 只与后端 REST API 通信（ADR-0001） |
| 包管理 | npm | Vite 默认 |

**工程**：`requirements.txt`（后端全部依赖）、`frontend/package.json`、启动脚本、git。

## 5. 核心流程

### 5.1 一次任务执行（定时或手动触发）

1. 拉取 release 列表，找出 > 已处理最大版本 的所有新版本（按 tag 数字排序）
2. 对每个新版本 v（升序）：
   a. `compare 上一版...v` 拿完整 commit 列表（首版 compare 基线用 v 的上一版，基线本身不入库）
   b. **文本扫描**：commit/release 文本匹配 `ADD --xxx` 类新增命令字样 → 写入 new_commands 表（来源=text）
   c. **LLM 分析**（每版一次独立调用，单版失败不影响其他版，可单独补分析）：输入 = commit 列表 + 用户启动命令；输出 = ① 对本地有正提升的条目（带理由）② 用户所用 flag 是否被删/改名/默认值变化 ③ 建议用户加上的新 flag。LLM 可上网搜索辅助。
   d. **条件 --help diff**（ADR-0003）：仅当 c 判定存在正提升时，下载该版 Windows CUDA 二进制（对应用户平台 `llama-b{N}-bin-win-cuda-12.4-x64.zip`），跑 `--help`，与上一版缓存的 help 文本 diff，新增 flag 写入 new_commands 表（来源=help-diff，覆盖/补充 text 来源）。**下载失败不重试**（增量任务不回头处理旧版本），该版 help_diffed=0，页面标注「help diff 未完成」，新增命令靠 text 来源兜底
   e. 汇总写 versions 表（一条版本记录）
3. 记录本次 run（起止时间、处理了哪些版本、成功/失败）
4. **基线自动推进**（ADR-0005）：run 记为 `ok` 且处理了至少一个版本时，把 settings 表 `baseline_tag` 更新为本次处理的最大版本（持久进度游标，见 §5.2）。`partial`/`failed` 不推进；处理 0 个版本（无新 release）不写库
5. 异常处理：GitHub 不可达/代理失效 → run 记 failed + 原因，已处理进度不回退；LLM 服务不可用 → 版本记录原始数据 + 分析字段留空，run 记 partial，下次执行补分析
6. **重入**：上一次任务（无论定时还是手动）仍在执行时，新触发**直接拒绝**，API 返回「任务进行中」，页面提示；不做排队

### 5.2 基线（持久进度游标）

baseline 是增量任务的持久进度游标（默认 **b11514**，可配置）。任务以 `ok` 完成且处理了至少一个版本时自动前移为本次处理的最大版本（ADR-0005）。下界为 `max(baseline, 已入库最大版本)`，因此正常运行时驱动增量的是已入库最大版本，baseline 只在 versions 表被清空后作为恢复起点——监控从「上次分析到的版本」续接，不回落 b11514 重放全部历史。baseline 只严格递增（不会压过用户手动设的更大值、不会倒退），用户仍可在页面手动改。

## 6. 数据模型（SQLite，`H:\data\llamacpp-monitor\monitor.db`）

```sql
-- 版本报告（每版一条）
versions(
  id INTEGER PRIMARY KEY,
  tag TEXT UNIQUE NOT NULL,          -- b11518
  published_at TEXT,
  commit_count INTEGER,
  commits_raw TEXT,                  -- 完整 commit 列表原文
  positive_items TEXT,               -- LLM 判定对本地有正提升的条目（JSON：条目+理由）
  launch_impact TEXT,                -- 对用户启动命令的影响分析（JSON）
  suggested_flags TEXT,              -- 建议用户加上的新 flag（JSON）
  help_diffed INTEGER DEFAULT 0,     -- 是否做过 --help diff
  analyzed INTEGER DEFAULT 0,        -- LLM 分析是否完成
  created_at TEXT
)

-- 新增命令（单独记录）
new_commands(
  id INTEGER PRIMARY KEY,
  tag TEXT NOT NULL,                 -- 所属版本
  flag TEXT NOT NULL,                -- --xxx
  source TEXT,                       -- text | help-diff
  description TEXT,                  -- 用途说明
  UNIQUE(tag, flag, source)
)

-- 任务执行记录
runs(
  id INTEGER PRIMARY KEY,
  started_at TEXT, ended_at TEXT,
  trigger TEXT,                      -- scheduled | manual
  status TEXT,                       -- ok | partial | failed
  versions_processed TEXT,           -- JSON 数组
  error TEXT
)

-- 配置（键值，页面可编辑）
settings(
  key TEXT PRIMARY KEY, value TEXT
)
-- 键：interval_minutes、baseline_tag、model_base_url、model_api_key、
--     model_name、proxy、launch_command
```

## 7. 前端页面

| 页面 | 内容 |
|---|---|
| 任务执行 | runs 列表（时间、触发方式、状态、处理版本、错误），顶部「立即执行」按钮 + 间隔设置 |
| 报告 | versions 分页列表（Element Plus 分页），点进详情：正提升条目、启动命令影响、建议 flag、新增命令、原始 commit 列表 |
| 配置 | 模型配置（base_url / api key / 模型名，**默认值来自项目 `.env`**，见 ADR-0004）、任务间隔、基线版本、代理地址、启动命令 |

## 8. 配置项

| 配置 | 默认 | 说明 |
|---|---|---|
| `interval_minutes` | 120 | 任务间隔，页面可调 |
| `baseline_tag` | b11514 | 首次运行基线 |
| `model_base_url` / `model_api_key` / `model_name` | **项目自带默认模型配置，存于 `.env`**（`MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME`，见 ADR-0004；仓库提供 `.env.example` 模板，`.env` 不入库） | 分析用 LLM，页面可改（页面值优先于 .env）；`.env` 缺失时启动报错拒绝启动 |
| `proxy` | `http://127.0.0.1:7981` | GitHub 访问代理 |
| `launch_command` | 用户提供的 llama-server.exe 命令（原文存档于本文件附录） | 影响分析输入 |
| DB 路径 | `H:\data\llamacpp-monitor\monitor.db` | |

## 8.5 环境与运行

- **Python 环境**：conda 虚拟环境 `llamacpp-monitor`（`conda create -n llamacpp-monitor python=3.x`），安装与运行都在此环境
- **依赖清单**：后端全部依赖写入根目录 `requirements.txt`；前端 Node 依赖由 `frontend/package.json` 管理
- **进程管理**：启动脚本 `start.bat` 一键拉起（后端 `uvicorn backend.main:app --host 127.0.0.1 --port 5000`，conda 环境 `llamacpp-monitor`；前端构建产物已就位，生产模式由 FastAPI 在 5000 上静态托管）；**不做 Windows 服务化**，需要常驻时由用户自行配置任务计划程序
- **端口约定**：后端（uvicorn）= **5000**；前端 dev（vite）= **5100**（vite 代理 `/api` → 5000）；生产模式前后端同端口 5000
- **前端构建**：开发时 Vite dev server 代理 API；生产构建产物（`frontend/dist`）由 FastAPI 静态挂载，不入库

## 9. 「正提升」判定标准（LLM 分析依据）

- **算正提升**：① 性能类改进（CUDA/MTP 投机解码/flash-attn/内存，尤其与用户 3×CUDA + draft-mtp 配置相关的）；② 新功能且用户启动命令能用上；③ 修掉影响用户这类用法的 bug
- **不算**：纯重构、CI、文档、用户不用的后端（Vulkan/SYCL/Android/OpenVINO 等）
- 每版必须给出明确结论：**有正提升 / 无**，附理由（写入 `positive_items`）

## 10. 开放项（实现时定，不影响架构）

- --help diff 的二进制缓存目录与清理策略（只留上一版 help 文本即可，zip 用完即删）
- LLM 分析 prompt 的具体措辞与输出 schema
- 前端构建产物的提交/生成方式（构建产物不入库，本地 build）

## 附录：用户启动命令（原文）

```
D:\llama-cpp-hub\llama.cpp-hub-v0.9.8.3-windows-cuda12\llamacpp\llama-b11514-bin-win-cuda-12.4-x64\llama-server.exe -m I:\models\ukisai\Swift-Qwen3.8-27B\Swift-Qwen3.8-27B-Q4_K_M.gguf --device cuda0,cuda1,cuda2 --spec-type draft-mtp --ctx-size 139072 --flash-attn on --spec-draft-n-max 3 --load-mode dio --fit on --temp 0.7 --top-p 0.95 --top-k 40 --ctx-checkpoints 32 --spec-draft-type-k q4_0 --spec-draft-type-v q4_0 --cache-type-k q8_0 --cache-type-v q8_0 --split-mode layer --tensor-split 30/34/0 --batch-size 2048 --ubatch-size 512 --parallel 1 --port 8100 --no-webui --mmproj I:\models\ukisai\Swift-Qwen3.8-27B\mmproj-Swift-Qwen3.8-27B-F16.gguf --mmproj-device CUDA2 --jinja --no-ui --chat-template-file I:\models\ukisai\Swift-Qwen3.8-27B\chat_template.jinja --metrics --alias Swift-Qwen3.8-27B --timeout 36000 --host 0.0.0.0
```
