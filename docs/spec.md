## Problem Statement

用户本地运行 llama.cpp 推理服务（3×CUDA + MTP 投机解码 + flash-attn），llama.cpp 发版极频繁（约 3-4 版/天）。用户无法持续跟踪每个新版本的更新内容，判断哪些版本对自己本地环境有**正提升**、哪些变更会影响自己现有的**启动命令**、以及新版本引入了哪些**新增命令**。原方案（Hermes cron 纯 prompt 任务）已删除，需要一个可维护、可查询、可配置的项目级解决方案。

## Solution

构建 llama-cpp-monitor：一个前后端分离的 Web 应用。**增量任务**定时（默认 2 小时，间隔可调）检查 llama.cpp 的 GitHub release，对基线（默认 b11514）之后的每个**版本**执行分析管线（commit 提取 → 文本扫描**新增命令** → LLM 语义分析**正提升**与**启动影响** → 条件 **help-diff**），结果落入 SQLite；Web 前端提供**运行**记录、报告分页浏览和配置管理（含模型配置、任务间隔、手动触发）。

## User Stories

1. As a 本地推理用户, I want 系统定时（默认 2 小时）自动检查 llama.cpp 新版本, so that 我不需要手动盯 GitHub release 页面。
2. As a 本地推理用户, I want 在页面上调整任务间隔, so that 我可以按自己的节奏（更频繁或更稀疏）监控发版。
3. As a 本地推理用户, I want 在页面上点击「立即执行」手动触发一次任务, so that 发版密集期或我想立刻看结果时不必等定时。
4. As a 本地推理用户, I want 任务只处理上次处理到之后的新版本（增量任务）, so that 已分析过的版本不会重复分析、重复落库。
5. As a 本地推理用户, I want 每个版本在报告中只有一条记录, so that 报告列表干净、按版本浏览。
6. As a 本地推理用户, I want 报告中看到该版本的完整 commit 列表, so that 我可以核对 LLM 分析的原始依据。
7. As a 本地推理用户, I want LLM 明确给出该版本「有/无正提升」的结论和理由, so that 我一眼知道这个版本值不值得关注。
8. As a 本地推理用户, I want 正提升判定聚焦我的使用场景（3×CUDA、draft-mtp 投机解码、flash-attn、大 ctx）, so that 与我无关的变更（Vulkan/SYCL/Android/CI/文档）不会淹没真正重要的内容。
9. As a 本地推理用户, I want 报告分析我的启动命令是否受影响（所用 flag 被删/改名/默认值变化）, so that 升级前我知道现有服务配置会不会坏。
10. As a 本地推理用户, I want 报告给出建议我加上的新 flag, so that 我能低门槛地把新版本的收益用起来。
11. As a 本地推理用户, I want 每个版本的新增命令被单独记录（独立于版本报告）, so that 我可以专门查「哪个版本加了什么 flag」。
12. As a 本地推理用户, I want 新增命令记录标注来源（text 文本扫描 / help-diff 二进制比对）, so that 我知道该条记录的可靠程度。
13. As a 本地推理用户, I want 仅当版本被判定有正提升时才执行 help-diff（下载二进制跑 --help 与上版 diff）, so that 下载成本限制在少数值得关注的版本上。
14. As a 本地推理用户, I want 在任务执行页面看到每次运行的时间、触发方式（定时/手动）、状态（ok/partial/failed）、处理的版本和错误信息, so that 我能判断系统是否正常工作。
15. As a 本地推理用户, I want 报告列表以分页形式展现, so that 版本积累多了之后依然流畅浏览。
16. As a 本地推理用户, I want 在配置页面修改分析用 LLM 的 base_url、api key、模型名, so that 我可以随时切换分析模型（默认值来自项目 `.env` 配置，页面值优先）。
17. As a 本地推理用户, I want 在配置页面修改基线版本, so that 我可以重新设定增量起点。
18. As a 本地推理用户, I want 在配置页面修改启动命令, so that 我换了本地服务配置后影响分析跟着更新。
19. As a 本地推理用户, I want 在配置页面修改 GitHub 访问代理地址, so that 网络环境变化时监控不中断。
20. As a 本地推理用户, I want 任务成功完成（ok）后基线自动前移为本次处理的最大版本, so that 即使 versions 表被清空，监控也从上次分析到的版本续接，不回落 b11514 重放全部历史。
21. As a 本地推理用户, I want 当 LLM 服务不可用时版本仍落库（原始 commit 数据完整、分析字段留空）且运行标记 partial, so that 数据不丢、服务恢复后可补分析。
22. As a 本地推理用户, I want 当 GitHub 不可达时运行标记 failed 并记录原因、已处理进度不回退, so that 网络抖动不会导致重复分析。
23. As a 本地推理用户, I want 上一次运行未完成时新的触发被拒绝并明确提示「任务进行中」, so that 不会有两个任务并发写库。
24. As a 本地推理用户, I want help-diff 的二进制下载失败时该版本标注「help diff 未完成」且不重试, so that 单点失败不阻塞后续版本处理。
25. As a 本地推理用户, I want 应用只监听 127.0.0.1, so that 监控数据不暴露到网络。
26. As a 维护者, I want 后端依赖清单在 requirements.txt、前端依赖在 package.json, so that 环境可复现（conda 环境 llamacpp-monitor）。
27. As a 维护者, I want 启动脚本一键拉起应用, so that 部署简单、无服务化依赖。
28. As a 维护者, I want 前后端严格分离、前端只通过 REST API 通信, so that 两个工程可独立演进（ADR-0001）。

## Implementation Decisions

**架构（遵循 ADR-0001 / ADR-0002 / ADR-0003）**

- 系统分两个独立工程：后端（Python）与前端（TypeScript），REST API 是唯一通信面；前端构建产物由后端静态托管，最终单进程对外服务，仅绑定 127.0.0.1，无认证。
- 调度由后端内置 APScheduler 承担，间隔从配置读取（可运行时更新，更新后重新调度）；手动触发与定时触发走同一条执行入口。
- 新增命令检测以文本扫描（commit/release 文本中 `ADD --xxxx` 类字样）为默认手段；仅当 LLM 判定该版本有正提升时才执行 help-diff：下载该版 Windows CUDA 二进制（对应用户平台构建）、运行 `--help`、与上一版帮助文本 diff。help-diff 失败不重试，标注未完成，text 来源兜底。

**技术栈**

- 后端：Python 3.14（conda 环境 `llamacpp-monitor`）、FastAPI + Pydantic、uvicorn、APScheduler、SQLite + SQLAlchemy 2.x（不用 Alembic，schema 变更手动执行）、httpx（GitHub API 与 LLM 调用共用，代理可配置）、OpenAI 兼容接口直调 LLM（不引 openai SDK）、标准库 difflib（help diff）与 zipfile（二进制解压，用后删除 zip 只留 help 文本）、pytest。
- 前端：Vue 3 + Vite + TypeScript、Element Plus、vue-router、Pinia、axios、npm。
- 数据文件：SQLite 库位于 `H:\data\llamacpp-monitor\monitor.db`。

**数据模型（SQLite 四表）**

- `versions`：每个版本一条。tag（唯一）、published_at、commit_count、commits_raw（完整 commit 列表原文）、positive_items（LLM 正提升条目，JSON）、launch_impact（启动影响分析，JSON）、suggested_flags（建议 flag，JSON）、help_diffed（0/1）、analyzed（0/1）、created_at。
- `new_commands`：新增命令单独记录。tag、flag、source（text | help-diff）、description；(tag, flag, source) 唯一。
- `runs`：每次运行一条。started_at、ended_at、trigger（scheduled | manual）、status（ok | partial | failed）、versions_processed（JSON 数组）、error。
- `settings`：键值配置。interval_minutes（默认 120）、baseline_tag（默认 b11514，任务 ok 且处理了版本时自动前移为本次最大版本，见 ADR-0005）、model_base_url / model_api_key / model_name（默认值来自项目 `.env` 的 `MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME`，页面值优先，见 ADR-0004）、proxy（默认 http://127.0.0.1:7981）、launch_command（用户启动命令原文，见设计文档附录）。

**数据源（已验证的事实）**

- 仓库地址为 `ggml-org/llama.cpp`（旧 ggerganov 地址 301 跳转，代码用新地址）；tag 格式 `bNNNNN`。
- release body 不含完整 commit 列表；完整变更必须走 compare API `compare/b{N-1}...b{N}`。
- GitHub 访问需走本地代理（直连 301）。

**执行管线（一次运行，按 tag 升序逐版本）**

1. 拉 release 列表，选出大于 `max(baseline, 已入库最大版本)` 的所有版本。
2. 每版：compare 取 commit 列表 → 文本扫描新增命令（source=text）→ LLM 分析（每版一次独立调用，输入为 commit 列表 + 启动命令，输出为结构化 JSON：正提升条目+理由、启动影响、建议 flag；LLM 可上网搜索辅助）→ 若判定有正提升则 help-diff（source=help-diff）→ 写 versions 记录。
3. 写 runs 记录。
4. 基线自动推进（ADR-0005）：run 记 ok 且处理了至少一个版本时，把 settings 表 baseline_tag 更新为本次处理的最大版本；partial/failed 不推进，处理 0 个版本不写库。
5. 失败语义：GitHub 不可达 → run=failed，进度不回退；LLM 不可用 → 版本落原始数据、分析留空、run=partial，下次运行补分析；单版 LLM 失败不影响其他版本。
6. 重入：运行进行中拒绝新触发（API 返回任务进行中），不排队。

**API 契约（前端唯一入口）**

- 运行：POST 手动触发 / GET 运行列表（分页）/ GET 当前运行状态（含进行中标志）。
- 报告：GET 版本列表（分页、按 tag 倒序）/ GET 版本详情（含该版本新增命令）。
- 配置：GET / PUT 设置（interval、baseline、model 三项、proxy、launch_command）。
- 静态：前端构建产物挂载于根路径。

**LLM 分析判定标准（写入 prompt）**

- 算正提升：性能类（尤其与 3×CUDA / draft-mtp / flash-attn / 大 ctx 相关的）、用户启动命令可用的新功能、修掉影响用户用法的 bug。
- 不算：纯重构、CI、文档、用户不用的后端（Vulkan/SYCL/Android/OpenVINO 等）。
- 输出必须含明确结论：有正提升 / 无，附理由。

## Testing Decisions

- 好测试的标准：只测外部行为（API 响应、落库结果、状态流转），不测内部实现细节；外部依赖（GitHub、LLM、二进制执行）一律用 fake 注入。
- **接缝 1（最高层，行为接缝）**：REST API 层，用 FastAPI TestClient（httpx ASGI 直连应用）覆盖全部用户可见行为：手动触发、运行状态查询、报告分页、配置读写、重入拒绝、失败状态语义。
- **接缝 2（引擎依赖边界）**：监控引擎与三个外部系统（GitHub API、LLM API、二进制执行）之间留薄抽象，测试注入 fake（httpx MockTransport / 假 LLM 响应 / 假 help 文本），覆盖引擎逻辑：增量版本选择、文本扫描、help diff、SQLite 落库、partial/failed 降级。
- 前端不写自动化测试（技术栈未含前端测试框架），靠手动验证。
- 引擎内部实现（SQLAlchemy 模型映射、调度器装配）不单独立测试，经上述两个接缝间接覆盖。
- Prior art：仓库为新建项目，无既有测试；pytest 为既定测试框架。

## Out of Scope

- 多仓库监控（只盯 llama.cpp）。
- 多用户、认证、远程访问（仅 127.0.0.1）。
- 下载并自动升级本地 llama.cpp 二进制（只分析，不动用户环境）。
- Windows 服务化 / 进程守护（脚本启动，常驻由用户自行配置任务计划程序）。
- 数据库迁移工具（SQLAlchemy 模型 + 手动 schema 变更）。
- 前端自动化测试。
- 非 Windows 平台的 help-diff（用户平台为 Windows CUDA）。

## Further Notes

- 设计文档：`docs/design.md`（含完整流程图、配置表、用户启动命令原文附录）。
- 领域术语以 `GLOSSARY.md` 为准；架构决策见 `docs/adr/0001-0005`。
- LLM 默认模型来自项目 `.env`（`MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME`），仓库提供 `.env.example` 模板，`.env` 本身不入库；页面配置可覆盖（页面值优先）；`.env` 缺失时启动报错拒绝启动（ADR-0004）。
- 基线 b11514 为初始进度游标，任务 ok 且处理了版本时自动前移（ADR-0005）；基线本身不入库。
- 端口约定：后端（uvicorn）= 5000，前端 dev（vite）= 5100；启动脚本 `start.bat` 一键拉起。
