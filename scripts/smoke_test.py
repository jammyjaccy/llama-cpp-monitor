"""冒烟测试：启动服务 -> 触发真实任务 -> 验证 API 返回。

API key 从 %LOCALAPPDATA%/hermes/config.yaml 读取，仅进程内使用，不打印。
"""
import os
import re
import sys
import time
import urllib.request

import yaml

BASE = "http://127.0.0.1:8765"


def get_api_key() -> str:
    path = os.path.join(os.environ["LOCALAPPDATA"], "hermes", "config.yaml")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 递归找包含 4000 的 api key
    def find(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if "api_key" in k.lower() and "4000" in str(k):
                    return v
                r = find(v)
                if r:
                    return r
        elif isinstance(node, list):
            for item in node:
                r = find(item)
                if r:
                    return r
        return None
    key = find(cfg)
    if not key:
        # 兜底：找任意 localhost:4000 相关配置块
        text = open(path, encoding="utf-8").read()
        m = re.search(r"api_key:\s*(\S+)", text)
        key = m.group(1) if m else ""
    return key


def api(path, method="GET", body=None, timeout=10):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=(body if isinstance(body, (bytes, str)) else None),
        headers={"Content-Type": "application/json"},
    )
    if body and not isinstance(body, (bytes, str)):
        import json
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        import json
        return json.loads(resp.read().decode())


def main():
    key = get_api_key()
    print(f"api key loaded: {'yes' if key else 'NO'}")

    # 1. 服务应已启动
    print("health:", api("/api/health"))

    # 2. 配置 api key（若为空）
    s = api("/api/settings")
    if not s["model_api_key"]:
        api("/api/settings", "PUT", {"model_api_key": key})
        s = api("/api/settings")
    print("settings ok, model:", s["model_name"])

    # 3. 触发手动任务
    print("triggering manual run...")
    try:
        run = api("/api/runs/trigger", "POST", {})
    except urllib.error.HTTPError as e:
        print("trigger failed:", e.code, e.read().decode())
        return 1
    print("run id:", run["id"], "status:", run["status"])

    # 4. 轮询 run 状态（最多 10 分钟）
    run_id = run["id"]
    for i in range(120):
        time.sleep(5)
        runs = api("/api/runs")
        cur = next((r for r in runs if r["id"] == run_id), None)
        if cur and cur["status"] != "running":
            break
    else:
        print("run did not finish in 10 min")
        return 1

    print("final run:", {k: cur[k] for k in ("status", "versions_processed", "error")})

    # 5. 报告
    reports = api("/api/reports?page_size=5")
    print(f"reports: {len(reports)}")
    for r in reports[:5]:
        print(f"  {r['tag']} commits={r['commit_count']} analyzed={r['analyzed']} "
              f"help_diffed={r['help_diffed']} positive={len(r['positive_items'])}")

    if reports:
        detail = api(f"/api/reports/{reports[0]['tag']}")
        print(f"detail {detail['tag']}: new_commands={len(detail['new_commands'])}, "
              f"commits={len(detail['commits_raw'])}")
        for c in detail["new_commands"][:5]:
            print(f"    --{c['flag']} ({c['source']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
