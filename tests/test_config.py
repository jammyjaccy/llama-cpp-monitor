"""配置层：默认值补齐、更新、非法键。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.database import Base
from app.models import Setting


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with Session() as s:
        yield s


def test_load_fills_defaults(db):
    s = config.load_settings(db)
    assert s.interval_minutes == 120
    assert s.baseline_tag == "b11514"
    assert s.proxy == "http://127.0.0.1:7981"
    assert s.model_name == "Swift-Qwen3.8-27B"
    assert "--spec-type draft-mtp" in s.launch_command


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
