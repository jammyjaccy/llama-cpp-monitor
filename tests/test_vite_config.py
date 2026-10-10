"""T10：vite dev 配置断言（端口 5100 + 代理指向 5000）。

接缝：直接断言 frontend/vite.config.ts 的 server.port 与 /api 代理 target。
期望值来自 spec（design.md §8.5 端口约定），非代码自推。
"""
import re
from pathlib import Path

VITE_CONFIG = Path(__file__).resolve().parent.parent / "frontend" / "vite.config.ts"


def _read() -> str:
    return VITE_CONFIG.read_text(encoding="utf-8")


def test_vite_dev_port_is_5100():
    m = re.search(r"port:\s*(\d+)", _read())
    assert m, "vite.config.ts 未找到 server.port"
    assert m.group(1) == "5100"


def test_vite_proxy_target_is_5000():
    m = re.search(r"target:\s*['\"](http://127\.0\.0\.1:\d+)['\"]", _read())
    assert m, "vite.config.ts 未找到 /api 代理 target"
    assert m.group(1) == "http://127.0.0.1:5000"
