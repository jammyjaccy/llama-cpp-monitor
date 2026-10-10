"""配置：settings 表读写 + 默认值。

`.env` 派生默认（ADR-0004 模型三项 + ADR-0006 代理）来自项目根 `.env`：
`MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME` / `PROXY`。仓库提交
`.env.example` 模板，`.env` 不入库；`.env` 缺失（或缺 `PROXY` 键）时应用
启动报错并拒绝启动；彻底放弃 Hermes 配置来源。

优先级：页面 settings 值 > `.env`。settings 表只存「页面显式改过的值」，
`.env` 作为默认来源每次加载时实时读取（不落库），因此改 `.env` 重启即生效。
例外：`baseline_tag` 由 runner 在任务 ok 时自动推进（ADR-0005 持久进度游标），
非页面值也会落库，故会遮蔽 `STATIC_DEFAULTS["baseline_tag"]` 的默认变更。
"""
import os
from dataclasses import dataclass

from dotenv import dotenv_values
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Setting

# 静态默认项（与 .env 无关，长期固定）。
# 注意：proxy 不在这里——其默认值来自 .env 的 PROXY 键（ADR-0006）。
STATIC_DEFAULTS: dict[str, str] = {
    "interval_minutes": "120",
    "baseline_tag": "b11514",
    "launch_command": (
        "D:\\llama-cpp-hub\\llama.cpp-hub-v0.9.8.3-windows-cuda12\\llamacpp\\"
        "llama-b11514-bin-win-cuda-12.4-x64\\llama-server.exe "
        "-m I:\\models\\ukisai\\Swift-Qwen3.8-27B\\Swift-Qwen3.8-27B-Q4_K_M.gguf "
        "--device cuda0,cuda1,cuda2 --spec-type draft-mtp --ctx-size 139072 "
        "--flash-attn on --spec-draft-n-max 3 --load-mode dio --fit on "
        "--temp 0.7 --top-p 0.95 --top-k 40 --ctx-checkpoints 32 "
        "--spec-draft-type-k q4_0 --spec-draft-type-v q4_0 "
        "--cache-type-k q8_0 --cache-type-v q8_0 --split-mode layer "
        "--tensor-split 30/34/0 --batch-size 2048 --ubatch-size 512 --parallel 1 "
        "--port 8100 --no-webui "
        "--mmproj I:\\models\\ukisai\\Swift-Qwen3.8-27B\\mmproj-Swift-Qwen3.8-27B-F16.gguf "
        "--mmproj-device CUDA2 --jinja --no-ui "
        "--chat-template-file I:\\models\\ukisai\\Swift-Qwen3.8-27B\\chat_template.jinja "
        "--metrics --alias Swift-Qwen3.8-27B --timeout 36000 --host 0.0.0.0"
    ),
}

# 模型三项键（默认值来自 .env）
MODEL_KEYS = ["model_base_url", "model_api_key", "model_name"]

# .env 派生默认键 = 模型三项 + 代理（proxy 默认来自 .env 的 PROXY 键，ADR-0006）
ENV_KEYS = MODEL_KEYS + ["proxy"]

# 可编辑键 = 静态项 + .env 派生项（派生，避免双份维护）
EDITABLE_KEYS = list(STATIC_DEFAULTS) + ENV_KEYS


class EnvMissingError(Exception):
    """项目 .env 缺失（ADR-0004）：应用应拒绝启动。"""


@dataclass
class Settings:
    interval_minutes: int
    baseline_tag: str
    model_base_url: str
    model_api_key: str
    model_name: str
    proxy: str
    launch_command: str


def _default_env_path() -> str:
    """项目根 .env 路径（config.py 位于 backend/ 下）。"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def load_env(env_path: str | None = None) -> dict[str, str]:
    """读取项目 .env 的默认值（模型三项 + 代理）。文件缺失抛 EnvMissingError。

    模型三项：键缺失或裸键（无值）时取空串（不阻断启动，页面可补配）。
    代理（PROXY）：缺失或空值时抛 EnvMissingError 并指明键名（ADR-0006，比模型三键更严）。
    """
    path = env_path or _default_env_path()
    if not os.path.isfile(path):
        raise EnvMissingError(
            f"未找到项目 .env（{path}）。请复制 .env.example 为 .env 并填写 MODEL_* 三项与 PROXY。"
        )
    values = dotenv_values(path)
    proxy = values.get("PROXY")
    if not proxy:
        raise EnvMissingError(
            "项目 .env 缺少 PROXY 键（或值为空）。请在 .env 中设置 PROXY（完整代理 URL，"
            "如 http://127.0.0.1:7897）。"
        )
    return {
        "model_base_url": values.get("MODEL_BASE_URL") or "",
        "model_api_key": values.get("MODEL_API_KEY") or "",
        "model_name": values.get("MODEL_NAME") or "",
        "proxy": proxy,
    }


# 模块级缓存：启动时由 ensure_env_defaults 填充，之后 load_settings 复用。
_ENV_DEFAULTS: dict[str, str] | None = None


def ensure_env_defaults() -> dict[str, str]:
    """启动时调用：从默认路径加载 .env（模型三项 + 代理）到模块缓存（幂等）。

    缺失时抛 EnvMissingError 拒绝启动。无参数——缓存已填充后路径不可切换，
    避免「传了路径却被忽略」的契约陷阱。
    """
    global _ENV_DEFAULTS
    if _ENV_DEFAULTS is None:
        _ENV_DEFAULTS = load_env()
    return _ENV_DEFAULTS


def _env_defaults() -> dict[str, str]:
    return ensure_env_defaults()


def _defaults() -> dict[str, str]:
    d = dict(STATIC_DEFAULTS)
    d.update(_env_defaults())
    return d


def load_settings(db: Session) -> Settings:
    """读 settings 表；页面显式改过的值优先，其余取默认值（静态 + .env）。

    不落库默认值：settings 表只保存页面 PUT 的覆盖值，`.env` 每次加载实时读取，
    因此修改 `.env` 后重启即生效（ADR-0004 优先级：页面值 > .env）。
    """
    rows = {r.key: r for r in db.execute(select(Setting)).scalars()}
    values: dict[str, str] = {}
    for key, default in _defaults().items():
        row = rows.get(key)
        values[key] = row.value if (row is not None and row.value is not None) else default
    return Settings(
        interval_minutes=int(values["interval_minutes"]),
        baseline_tag=values["baseline_tag"],
        model_base_url=values["model_base_url"],
        model_api_key=values["model_api_key"],
        model_name=values["model_name"],
        proxy=values["proxy"],
        launch_command=values["launch_command"],
    )


def update_settings(db: Session, updates: dict[str, str]) -> Settings:
    """更新指定键（仅限 EDITABLE_KEYS，即页面显式覆盖），返回最新配置。"""
    unknown = set(updates) - set(EDITABLE_KEYS)
    if unknown:
        raise ValueError(f"unknown settings keys: {sorted(unknown)}")
    for key, value in updates.items():
        row = db.get(Setting, key)
        if row is None:
            row = Setting(key=key)
            db.add(row)
        row.value = str(value)
    db.commit()
    return load_settings(db)
