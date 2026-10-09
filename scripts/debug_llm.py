"""调试 LLM 端点连通性（key 进程内使用，不打印）。"""
import os
import urllib.request

import yaml

path = os.path.join(os.environ["LOCALAPPDATA"], "hermes", "config.yaml")
cfg = yaml.safe_load(open(path, encoding="utf-8"))
text = open(path, encoding="utf-8").read()

import re
m = re.search(r"api_key:\s*(\S+)", text)
key = m.group(1) if m else ""
print("key found:", bool(key))

req = urllib.request.Request(
    "http://localhost:4000/v1/chat/completions",
    method="POST",
    data='{"model":"Swift-Qwen3.8-27B","messages":[{"role":"user","content":"说 ok"}],"max_tokens":10}'.encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode()
        print("status:", resp.status)
        print("body:", body[:300])
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:500])
