from __future__ import annotations

from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel, create_engine

from aiker.config import AppPaths


def build_engine(paths: AppPaths):
    return create_engine(paths.db_url, connect_args={"check_same_thread": False})


def init_db(paths: AppPaths) -> None:
    engine = build_engine(paths)
    try:
        SQLModel.metadata.create_all(engine, checkfirst=True)
    except OperationalError as exc:
        # Defensive guard for rare startup races where another process created tables first.
        if "already exists" not in str(exc).lower():
            raise
