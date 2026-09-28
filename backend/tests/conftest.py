import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import create_app
from app.config import TestConfig
from app.extensions import db


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    finally:
        cursor.close()


@pytest.fixture
def app():
    test_app = create_app(TestConfig)
    test_app.config["TESTING"] = True

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(autouse=True)
def clean_rate_limiters():
    from app.extensions import limiter
    from app.services.llm import LLMService

    LLMService.reset_rate_limiter()
    try:
        if getattr(limiter, "_storage", None):
            limiter.reset()
    except Exception:
        pass
    yield
    LLMService.reset_rate_limiter()
    try:
        if getattr(limiter, "_storage", None):
            limiter.reset()
    except Exception:
        pass
