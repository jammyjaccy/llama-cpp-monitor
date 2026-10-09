"""配置层：默认值补齐、.env 模型默认（ADR-0004）、更新、非法键。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import config
from backend.database import Base
from backend.models import Setting

MODEL_DEFAULTS = {
    "model_base_url": "http://localhost:4000",
    "model_api_key": "env-key",
    "model_name": "Swift-Qwen3.8-27B",
}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    # ADR-0004：模型默认值来自 .env；测试用固定值，不依赖真实 .env
    monkeypatch.setattr(config, "_MODEL_DEFAULTS", dict(MODEL_DEFAULTS))
    with Session() as s:
        yield s


def test_load_fills_defaults(db):
    s = config.load_settings(db)
    assert s.interval_minutes == 120
    assert s.baseline_tag == "b11514"
    assert s.proxy == "http://127.0.0.1:7981"
    assert s.model_name == "Swift-Qwen3.8-27B"
    assert "--spec-type draft-mtp" in s.launch_command


def test_model_defaults_from_env(db):
    """ADR-0004：模型三项默认值取自 .env（经 _MODEL_DEFAULTS 注入）。"""
    s = config.load_settings(db)
    assert s.model_base_url == "http://localhost:4000"
    assert s.model_api_key == "env-key"
    assert s.model_name == "Swift-Qwen3.8-27B"


def test_page_value_overrides_env(db):
    """页面 settings 值优先于 .env：改 model_name 后以页面值为准。"""
    config.load_settings(db)
    s = config.update_settings(db, {"model_name": "custom-model"})
    assert s.model_name == "custom-model"
    # 重复加载仍是页面值（已落库）
    s2 = config.load_settings(db)
    assert s2.model_name == "custom-model"


def test_update_known_key(db):
    config.load_settings(db)
    s = config.update_settings(db, {"interval_minutes": "60"})
    assert s.interval_minutes == 60
    # 其他键不受影响
    assert s.baseline_tag == "b11514"


def test_update_rejects_unknown_key(db):
    config.load_settings(db)
    with pytest.raises(ValueError):
        config.update_settings(db, {"not_a_key": "x"})


def test_update_persists(db):
    config.load_settings(db)
    config.update_settings(db, {"baseline_tag": "b11600"})
    s2 = config.load_settings(db)
    assert s2.baseline_tag == "b11600"


def test_load_fills_null_value_in_place(db):
    """L3：行存在但 value 为 NULL 时就地更新默认值，不触发主键冲突。"""
    db.add(Setting(key="interval_minutes", value=None))
    db.commit()
    s = config.load_settings(db)
    assert s.interval_minutes == 120
    # 重复加载仍稳定（幂等）
    s2 = config.load_settings(db)
    assert s2.interval_minutes == 120


# ---- .env 读取（ADR-0004）----

def test_load_env_missing_raises(tmp_path):
    with pytest.raises(config.EnvMissingError):
        config.load_env(str(tmp_path / "nope.env"))


def test_load_env_reads_model_keys(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "MODEL_BASE_URL=http://127.0.0.1:4000\n"
        "MODEL_API_KEY=secret123\n"
        "MODEL_NAME=MyModel\n",
        encoding="utf-8",
    )
    v = config.load_env(str(p))
    assert v == {
        "model_base_url": "http://127.0.0.1:4000",
        "model_api_key": "secret123",
        "model_name": "MyModel",
    }


def test_load_env_missing_key_defaults_empty(tmp_path):
    """文件存在但某键缺失时该项取空串（不阻断启动，页面可补配）。"""
    p = tmp_path / ".env"
    p.write_text("MODEL_BASE_URL=http://localhost:4000\n", encoding="utf-8")
    v = config.load_env(str(p))
    assert v["model_base_url"] == "http://localhost:4000"
    assert v["model_api_key"] == ""
    assert v["model_name"] == ""


def test_ensure_model_defaults_missing_raises(tmp_path, monkeypatch):
    """启动校验：.env 缺失时 ensure_model_defaults 抛错（拒绝启动）。"""
    monkeypatch.setattr(config, "_MODEL_DEFAULTS", None)
    monkeypatch.setattr(config, "_default_env_path", lambda: str(tmp_path / "nope.env"))
    with pytest.raises(config.EnvMissingError):
        config.ensure_model_defaults()


def test_ensure_model_defaults_reads_env(tmp_path, monkeypatch):
    """启动校验：.env 存在时 ensure_model_defaults 读入模块缓存。"""
    p = tmp_path / ".env"
    p.write_text("MODEL_NAME=Cached\nMODEL_API_KEY=k\nMODEL_BASE_URL=http://x\n",
                 encoding="utf-8")
    monkeypatch.setattr(config, "_MODEL_DEFAULTS", None)
    monkeypatch.setattr(config, "_default_env_path", lambda: str(p))
    v = config.ensure_model_defaults()
    assert v["model_name"] == "Cached"
    # 幂等：再次调用返回缓存
    assert config.ensure_model_defaults()["model_name"] == "Cached"


def test_load_settings_does_not_persist_defaults(db, monkeypatch):
    """ADR-0004：默认值不落库——settings 表只存页面显式覆盖，改 .env 重启即生效。"""
    config.load_settings(db)
    # 模型三项未落库（无行）
    assert db.get(Setting, "model_name") is None
    # 模拟 .env 变更：模块缓存换新值后加载即取新值（无需重启落库）
    monkeypatch.setattr(config, "_MODEL_DEFAULTS", {
        "model_base_url": "http://new", "model_api_key": "k", "model_name": "changed-model",
    })
    s = config.load_settings(db)
    assert s.model_name == "changed-model"
