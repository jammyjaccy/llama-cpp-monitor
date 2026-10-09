"""调试 LLM 端点连通性（key 从项目 .env 读取，进程内使用，不打印）。"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import EnvMissingError, load_env  # noqa: E402

try:
    cfg = load_env()
except EnvMissingError as e:
    print("ERROR:", e)
    sys.exit(1)

key = cfg["model_api_key"]
print("key found:", bool(key))

body = json.dumps({
    "model": cfg["model_name"],
    "messages": [{"role": "user", "content": "说 ok"}],
    "max_tokens": 10,
}).encode()

req = urllib.request.Request(
    cfg["model_base_url"].rstrip("/") + "/v1/chat/completions",
    method="POST",
    data=body,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode()
        print("status:", resp.status)
        print("body:", body[:300])
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:500])
