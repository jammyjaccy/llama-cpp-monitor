"""REST API 测试（TestClient，临时 DB）。"""
import json

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
    # ADR-0004：lifespan 会 ensure_model_defaults()（读真实 .env）；测试注入固定值
    monkeypatch.setattr(config, "_MODEL_DEFAULTS", {
        "model_base_url": "http://localhost:4000",
        "model_api_key": "env-key",
        "model_name": "Swift-Qwen3.8-27B",
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
    assert items[0]["help_diffed"] == 1

    r = c.get("/api/reports/b11518")
    assert r.status_code == 200
    detail = r.json()
    assert detail["commits_raw"][0]["sha"] == "abc1234"
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


def test_run_out_serialization():
    r = Run(trigger="manual", status="ok", versions_processed=json.dumps(["b11518"]))
    out = _run_out(r)
    assert out["versions_processed"] == ["b11518"]
    assert out["status"] == "ok"


def test_version_out_serialization():
    v = Version(tag="b1", positive_items=json.dumps([{"item": "a", "reason": "b"}]))
    out = _version_out(v)
    assert out["positive_items"] == [{"item": "a", "reason": "b"}]
    assert out["launch_impact"] == {}


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
