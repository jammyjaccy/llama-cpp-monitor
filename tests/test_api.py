"""REST API 测试（TestClient，临时 DB）。"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend import config, database
from backend.database import Base
from backend.main import _run_out, _version_out, app
from backend.models import NewCommand, Run, Version


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/api.db", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSession)
    # ADR-0004/0006：lifespan 会 ensure_env_defaults()（读真实 .env）；测试注入固定值
    monkeypatch.setattr(config, "_ENV_DEFAULTS", {
        "model_base_url": "http://localhost:4000",
        "model_api_key": "env-key",
        "model_name": "Swift-Qwen3.8-27B",
        "proxy": "http://127.0.0.1:7897",
    })
    with TestClient(app) as c:
        with TestingSession() as s:
            config.load_settings(s)
        yield c, TestingSession


def test_health(client):
    c, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_roundtrip(client):
    c, _ = client
    r = c.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["interval_minutes"] == 120
    assert body["baseline_tag"] == "b11514"

    r = c.put("/api/settings", json={"interval_minutes": 60, "baseline_tag": "b11600"})
    assert r.status_code == 200
    assert r.json()["interval_minutes"] == 60
    assert r.json()["baseline_tag"] == "b11600"

    r = c.get("/api/settings")
    assert r.json()["interval_minutes"] == 60


def test_runs_empty(client):
    c, _ = client
    r = c.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_trigger_busy_returns_409(client, monkeypatch):
    """M5：任务进行中时手动触发返回 409。"""
    from backend.engine import runner as runner_mod

    monkeypatch.setattr(runner_mod.Runner, "is_busy", staticmethod(lambda: True))
    c, _ = client
    r = c.post("/api/runs/trigger")
    assert r.status_code == 409


def test_reports_empty(client):
    c, _ = client
    assert c.get("/api/reports").json() == []
    assert c.get("/api/reports/total").json() == {"total": 0}


def test_report_detail_404(client):
    c, _ = client
    assert c.get("/api/reports/b99999").status_code == 404


def _seed_version(s: Session, tag="b11518"):
    s.add(Version(
        tag=tag, published_at="2026-10-09T01:00:00Z", commit_count=2,
        commits_raw=json.dumps([{"sha": "abc1234", "message": "ADD: --foo"}]),
        positive_items=json.dumps([{"item": "x", "reason": "y"}], ensure_ascii=False),
        commit_notes=json.dumps([{"sha": "abc1234", "summary": "新增 --foo", "positive": False}]),
        launch_impact=json.dumps({"notes": "无"}),
        suggested_flags=json.dumps([]),
        help_diffed=1, analyzed=1,
    ))
    s.add(NewCommand(tag=tag, flag="foo", source="text", description="test"))
    s.commit()


def test_report_list_and_detail(client):
    c, TestingSession = client
    with TestingSession() as s:
        _seed_version(s)

    r = c.get("/api/reports")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["tag"] == "b11518"
    assert items[0]["positive_items"][0]["item"] == "x"
    assert items[0]["commit_notes"][0]["sha"] == "abc1234"
    assert items[0]["help_diffed"] == 1

    r = c.get("/api/reports/b11518")
    assert r.status_code == 200
    detail = r.json()
    assert detail["commits_raw"][0]["sha"] == "abc1234"
    assert detail["commit_notes"][0]["summary"] == "新增 --foo"
    assert detail["new_commands"][0]["flag"] == "foo"
    assert detail["new_commands"][0]["source"] == "text"


def test_reports_pagination(client):
    c, TestingSession = client
    with TestingSession() as s:
        for i in range(25):
            _seed_version(s, tag=f"b116{i:02d}")

    r = c.get("/api/reports", params={"page": 2, "page_size": 20})
    assert len(r.json()) == 5
    assert c.get("/api/reports/total").json() == {"total": 25}


@pytest.fixture()
def client_with_stale_runs(tmp_path, monkeypatch):
    """issue #23：在 app 启动前预置 run 行（含一条 running），验证启动清理。"""
    engine = create_engine(f"sqlite:///{tmp_path}/api.db", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSession)
    monkeypatch.setattr(config, "_ENV_DEFAULTS", {
        "model_base_url": "http://localhost:4000",
        "model_api_key": "env-key",
        "model_name": "Swift-Qwen3.8-27B",
        "proxy": "http://127.0.0.1:7897",
    })
    with TestingSession() as s:
        s.add(Run(trigger="scheduled", status="running", started_at="2026-10-10 01:00:00"))
        s.add(Run(trigger="manual", status="ok",
                  started_at="2026-10-10 01:00:00", ended_at="2026-10-10 01:05:00"))
        s.add(Run(trigger="manual", status="failed",
                  started_at="2026-10-10 01:00:00", ended_at="2026-10-10 01:05:00", error="boom"))
        s.add(Run(trigger="manual", status="partial",
                  started_at="2026-10-10 01:00:00", ended_at="2026-10-10 01:05:00"))
        s.commit()
    with TestClient(app) as c:  # 进 lifespan，触发启动清理
        yield c, TestingSession


def test_startup_cleanup_marks_running_failed(client_with_stale_runs):
    """issue #23：启动时遗留 running 行落为 failed（error「服务重启中断」、ended_at 补当前时间）。"""
    _, TestingSession = client_with_stale_runs
    with TestingSession() as s:
        run = s.get(Run, 1)
        assert run.status == "failed"
        assert "服务重启中断" in (run.error or "")
        assert run.ended_at is not None


def test_startup_cleanup_keeps_finished_runs(client_with_stale_runs):
    """issue #23：既有 ok/failed/partial 行不受启动清理影响。"""
    _, TestingSession = client_with_stale_runs
    with TestingSession() as s:
        assert s.get(Run, 2).status == "ok"
        assert s.get(Run, 3).status == "failed"
        assert s.get(Run, 3).error == "boom"
        assert s.get(Run, 4).status == "partial"


def test_run_out_serialization():
    r = Run(trigger="manual", status="ok", versions_processed=json.dumps(["b11518"]))
    out = _run_out(r)
    assert out["versions_processed"] == ["b11518"]
    assert out["status"] == "ok"


def test_version_out_serialization():
    v = Version(
        tag="b1",
        positive_items=json.dumps([{"item": "a", "reason": "b"}]),
        commit_notes=json.dumps([{"sha": "abc", "summary": "s", "positive": False}]),
    )
    out = _version_out(v)
    assert out["positive_items"] == [{"item": "a", "reason": "b"}]
    assert out["commit_notes"] == [{"sha": "abc", "summary": "s", "positive": False}]
    assert out["launch_impact"] == {}
    # commit_notes 为空（None）时序列化为 []
    empty = _version_out(Version(tag="b2"))
    assert empty["commit_notes"] == []


def _parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _assert_next_run_in_window(client, interval_minutes):
    """GET /api/schedule → 断言 next_run_time 落在「现在」到「现在+间隔」之间。"""
    c, _ = client
    r = c.get("/api/schedule")
    body = r.json()
    now = datetime.now(timezone.utc)
    nxt = _parse_utc(body["next_run_time"])
    assert now <= nxt <= now + timedelta(minutes=interval_minutes, seconds=5)
    return body


def test_schedule_shape(client):
    """issue #17：GET /api/schedule 返回 200，含 next_run_time 与 interval_minutes。"""
    import re
    c, _ = client
    r = c.get("/api/schedule")
    assert r.status_code == 200
    body = r.json()
    assert "next_run_time" in body
    assert "interval_minutes" in body
    assert body["next_run_time"] is not None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body["next_run_time"])


def test_schedule_interval_matches_settings(client):
    """issue #17：interval_minutes 与 settings 一致；改间隔 reschedule 后 next_run_time 反映新间隔。"""
    c, _ = client
    r = c.get("/api/schedule")
    assert r.json()["interval_minutes"] == 120

    r = c.put("/api/settings", json={"interval_minutes": 30})
    assert r.status_code == 200

    # reschedule 后 next_run_time 应在「现在」到「现在+30min」之间（新间隔）
    body = _assert_next_run_in_window(client, 30)
    assert body["interval_minutes"] == 30


def test_schedule_next_run_is_utc(client):
    """issue #17：next_run_time 是 UTC 字符串，落在「现在」到「现在+间隔」之间。

    测试环境是 UTC+8 机器：若裸 strftime（本地时间当 UTC），返回字符串会比真实
    UTC 大 8 小时，此区间断言会抓出来。
    """
    _assert_next_run_in_window(client, 120)


def test_spa_resolve_blocks_traversal(tmp_path, monkeypatch):
    """M4：_resolve_spa_file 不得解析出 dist 目录外的文件（../ 穿越）。"""
    import backend.main as main_mod
    from backend.main import _resolve_spa_file

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>")
    (dist / "app.js").write_text("console.log(1)")
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET_MARKER_DO_NOT_LEAK")

    monkeypatch.setattr(main_mod, "_FRONTEND_DIST", str(dist))
    # dist 内真实文件可解析
    assert _resolve_spa_file("index.html") == str(dist / "index.html")
    assert _resolve_spa_file("app.js") == str(dist / "app.js")
    # 穿越到 dist 外 -> 拒绝（返回 None，回退 index.html）
    assert _resolve_spa_file("../secret.txt") is None
    assert _resolve_spa_file("../../etc/passwd") is None
    assert _resolve_spa_file("a/../../secret.txt") is None
    # 空路径 -> None
    assert _resolve_spa_file("") is None
