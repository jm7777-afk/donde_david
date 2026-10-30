import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ["ENVIRONMENT"] = "testing"
TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"tesis-restaurante-tests-{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"


def pytest_sessionfinish(session, exitstatus):
    from backend.app.core.database import engine

    engine.dispose()
    for path in (TEST_DATABASE_PATH, Path(f"{TEST_DATABASE_PATH}-wal"), Path(f"{TEST_DATABASE_PATH}-shm")):
        if path.exists():
            path.unlink()
