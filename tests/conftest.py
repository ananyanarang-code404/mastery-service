"""Shared test fixtures: an isolated in-memory SQLite DB per test."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from mastery_service.db import Base


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()