"""SQLite persistence for the single admin user and their API keys.

Deliberately small: one file, no external service. Mount the path on a PVC so
accounts and keys survive restarts.
"""
import os

from sqlmodel import Session, SQLModel, create_engine

from .config import DB_PATH

# Ensure the parent directory exists (e.g. /data on a mounted volume). Ignore
# read-only filesystems so importing the app never fails; the engine will
# surface a clear error if the path truly isn't writable.
try:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
except OSError:
    pass

# check_same_thread=False: FastAPI serves requests across threads.
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency yielding a DB session."""
    with Session(engine) as session:
        yield session
