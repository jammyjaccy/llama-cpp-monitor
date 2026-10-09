# 模型默认配置存于项目 .env，不再读取 Hermes 配置

分析用 LLM 的默认三项（base_url / api key / 模型名）由项目自带的 `.env` 提供（`MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME`），仓库提交 `.env.example` 模板，`.env` 本身不入库。配置优先级：页面 settings 值 > `.env`。`.env` 缺失时应用启动报错并拒绝启动。

**考虑过的方案**：启动时读取 Hermes 系统配置（`%LOCALAPPDATA%\hermes\config.yaml` 的 model 段）作为默认值——这是原设计。

**为什么改**：项目不应依赖 Hermes 私有配置路径，默认模型是项目自身的配置项，放在 `.env` 里自包含、可移植、可显式声明缺失；彻底放弃 Hermes 配置来源。
