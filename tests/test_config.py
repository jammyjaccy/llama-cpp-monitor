"""配置层：默认值补齐、.env 模型默认（ADR-0004）、更新、非法键。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import config
from backend.database import Base
from backend.models import Setting

ENV_DEFAULTS = {
    "model_base_url": "http://localhost:4000",
    "model_api_key": "env-key",
    "model_name": "Swift-Qwen3.8-27B",
    "proxy": "http://127.0.0.1:7897",
}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    # ADR-0004/0006：.env 派生默认（模型三项 + 代理）；测试用固定值，不依赖真实 .env
    monkeypatch.setattr(config, "_ENV_DEFAULTS", dict(ENV_DEFAULTS))
    with Session() as s:
        yield s


def test_load_fills_defaults(db):
    s = config.load_settings(db)
    assert s.interval_minutes == 120
    assert s.baseline_tag == "b11514"
    assert s.proxy == "http://127.0.0.1:7897"
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


def test_load_env_reads_env_keys(tmp_path):
    """ADR-0004/0006：.env 提供模型三项 + 代理默认值。"""
    p = tmp_path / ".env"
    p.write_text(
        "MODEL_BASE_URL=http://127.0.0.1:4000\n"
        "MODEL_API_KEY=secret123\n"
        "MODEL_NAME=MyModel\n"
        "PROXY=http://127.0.0.1:7897\n",
        encoding="utf-8",
    )
    v = config.load_env(str(p))
    assert v == {
        "model_base_url": "http://127.0.0.1:4000",
        "model_api_key": "secret123",
        "model_name": "MyModel",
        "proxy": "http://127.0.0.1:7897",
    }


def test_load_env_model_key_missing_defaults_empty(tmp_path):
    """模型键缺失/空值取空串（不阻断启动，页面可补配）；但 PROXY 缺失即抛错。"""
    p = tmp_path / ".env"
    p.write_text(
        "MODEL_BASE_URL=http://localhost:4000\n"
        "MODEL_API_KEY=\n"
        "MODEL_NAME=\n"
        "PROXY=http://127.0.0.1:7897\n",
        encoding="utf-8",
    )
    v = config.load_env(str(p))
    assert v["model_base_url"] == "http://localhost:4000"
    assert v["model_api_key"] == ""
    assert v["model_name"] == ""
    assert v["proxy"] == "http://127.0.0.1:7897"


# ---- PROXY 缺失/空值（ADR-0006，比模型三键更严：启动即拒绝）----

def test_load_env_missing_proxy_raises(tmp_path):
    """缺 PROXY 键 → EnvMissingError 且指明键名。"""
    p = tmp_path / ".env"
    p.write_text(
        "MODEL_BASE_URL=http://localhost:4000\n"
        "MODEL_API_KEY=k\n"
        "MODEL_NAME=m\n",
        encoding="utf-8",
    )
    with pytest.raises(config.EnvMissingError) as exc:
        config.load_env(str(p))
    assert "PROXY" in str(exc.value)


def test_load_env_empty_proxy_raises(tmp_path):
    """PROXY 裸键（空值）→ 同样抛 EnvMissingError（比模型三键取空串更严）。"""
    p = tmp_path / ".env"
    p.write_text(
        "MODEL_BASE_URL=http://localhost:4000\n"
        "MODEL_API_KEY=k\n"
        "MODEL_NAME=m\n"
        "PROXY=\n",
        encoding="utf-8",
    )
    with pytest.raises(config.EnvMissingError) as exc:
        config.load_env(str(p))
    assert "PROXY" in str(exc.value)


def test_ensure_env_defaults_missing_raises(tmp_path, monkeypatch):
    """启动校验：.env 缺失时 ensure_env_defaults 抛错（拒绝启动）。"""
    monkeypatch.setattr(config, "_ENV_DEFAULTS", None)
    monkeypatch.setattr(config, "_default_env_path", lambda: str(tmp_path / "nope.env"))
    with pytest.raises(config.EnvMissingError):
        config.ensure_env_defaults()


def test_ensure_env_defaults_reads_env(tmp_path, monkeypatch):
    """启动校验：.env 存在时 ensure_env_defaults 读入模块缓存（含 proxy）。"""
    p = tmp_path / ".env"
    p.write_text(
        "MODEL_NAME=Cached\nMODEL_API_KEY=k\nMODEL_BASE_URL=http://x\n"
        "PROXY=http://127.0.0.1:7897\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "_ENV_DEFAULTS", None)
    monkeypatch.setattr(config, "_default_env_path", lambda: str(p))
    v = config.ensure_env_defaults()
    assert v["model_name"] == "Cached"
    assert v["proxy"] == "http://127.0.0.1:7897"
    # 幂等：再次调用返回缓存
    assert config.ensure_env_defaults()["model_name"] == "Cached"


# ---- proxy 默认值（ADR-0006）----

def test_proxy_default_from_env(db):
    """proxy 默认值取自 .env（经 _ENV_DEFAULTS 注入），STATIC_DEFAULTS 不再含 proxy。"""
    assert "proxy" not in config.STATIC_DEFAULTS
    s = config.load_settings(db)
    assert s.proxy == "http://127.0.0.1:7897"


def test_proxy_page_value_overrides_env(db):
    """页面 settings 值优先于 .env：改 proxy 后以页面值为准。"""
    config.load_settings(db)
    s = config.update_settings(db, {"proxy": "http://127.0.0.1:9999"})
    assert s.proxy == "http://127.0.0.1:9999"
    s2 = config.load_settings(db)
    assert s2.proxy == "http://127.0.0.1:9999"


def test_proxy_default_not_persisted(db, monkeypatch):
    """默认值不落库：settings 表无 proxy 行；改 .env 重启即生效。"""
    config.load_settings(db)
    assert db.get(Setting, "proxy") is None
    monkeypatch.setattr(config, "_ENV_DEFAULTS", {
        "model_base_url": "http://x", "model_api_key": "k", "model_name": "m",
        "proxy": "http://127.0.0.1:7898",
    })
    s = config.load_settings(db)
    assert s.proxy == "http://127.0.0.1:7898"
