"""SQLAlchemy engine, session factory, and table definitions.

File-backed SQLite is the production storage: the crash-durability
requirement needs data to survive a process restart, which rules out
plain in-memory storage. Tests use their own in-memory engine (see
tests/conftest.py); this module is not involved in that path.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = "sqlite:///mastery.db"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Attempt(Base):
    """One accepted practice attempt; used by the rate limiter."""

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String, index=True)
    skill_id: Mapped[str] = mapped_column(String)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Mastery(Base):
    """Current mastery score for a (student, skill) pair."""

    __tablename__ = "mastery"

    student_id: Mapped[str] = mapped_column(String, primary_key=True)
    skill_id: Mapped[str] = mapped_column(String, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    milestone_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Notification(Base):
    """A "mastery crossed above 80" milestone record."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String, index=True)
    skill_id: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables() -> None:
    """Create tables that do not exist yet. Called on app startup."""
    Base.metadata.create_all(engine)