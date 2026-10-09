"""配置：settings 表读写 + 默认值。

默认模型配置取 Hermes 系统默认（base_url localhost:4000，api_key 取环境变量
HERMES_CUSTOM_LOCALHOST_4000_API_KEY）。页面可改。
"""
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting

DEFAULTS: dict[str, str] = {
    "interval_minutes": "120",
    "baseline_tag": "b11514",
    "model_base_url": "http://localhost:4000",
    "model_api_key": os.environ.get("HERMES_CUSTOM_LOCALHOST_4000_API_KEY", ""),
    "model_name": "Swift-Qwen3.8-27B",
    "proxy": "http://127.0.0.1:7981",
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

EDITABLE_KEYS = list(DEFAULTS.keys())


@dataclass
class Settings:
    interval_minutes: int
    baseline_tag: str
    model_base_url: str
    model_api_key: str
    model_name: str
    proxy: str
    launch_command: str


def load_settings(db: Session) -> Settings:
    """读 settings 表；缺失或值为 NULL 的键用默认值补齐（并落库）。"""
    rows = {r.key: r for r in db.execute(select(Setting)).scalars()}
    values: dict[str, str] = {}
    for key, default in DEFAULTS.items():
        row = rows.get(key)
        if row is None or row.value is None:
            if row is None:
                row = Setting(key=key)
                db.add(row)
            row.value = default  # L3：已有行（value NULL）就地更新，避免主键冲突
        values[key] = row.value
    db.commit()
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
    """更新指定键（仅限 EDITABLE_KEYS），返回最新配置。"""
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
