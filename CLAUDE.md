## Agent skills

### Issue tracker

Issues live in GitHub Issues for jammyjaccy/llama-cpp-monitor; use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## 本地环境约定

### Git

- 远程 `origin` → `https://github.com/jammyjaccy/llama-cpp-monitor.git`，主分支 `main`
- 全局提交身份：`Jimmy <7484428+jammyjaccy@users.noreply.github.com>`（noreply 邮箱，勿改）
- `gh` CLI 在 `C:\Users\Jimmy-HAF700\AppData\Local\Programs\gh\gh.exe`（bash PATH 里可能找不到，用绝对路径）

### Python

- 本项目使用 **conda 虚拟环境 `llamacpp-monitor`**：运行、安装依赖、跑测试都在此环境（`conda activate llamacpp-monitor`）
- 后端依赖以根目录 `requirements.txt` 为准；前端 Node 依赖以 `frontend/package.json` 为准

### 进度记录

- Agent 必须把**当前状态、已完成的步骤、失败过的尝试**写进仓库根目录的 `CHANGELOG.md`（没有则创建）
- **失败记录尤其重要**：每次失败写清「做了什么、怎么失败的、错误关键信息、如何绕过/解决」，供后续 Agent 避免重复踩坑
- 每完成一个有实质进展的步骤就更新一次，不要攒到最后
