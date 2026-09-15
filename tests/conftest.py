import os
import tempfile
from pathlib import Path
import pytest

_bootstrap = tempfile.TemporaryDirectory(prefix="sytech-test-bootstrap-")
os.environ["SYTECH_DB_PATH"] = str(Path(_bootstrap.name) / "bootstrap.db")
os.environ.pop("SYTECH_ADMIN_PASSWORD", None)
os.environ.pop("SYTECH_ADMIN_CONTACT", None)

@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    from backend.database import schema, seed
    from backend import security
    from backend.app import ACTIVE_RESET_TOKENS, connected_clients
    from backend.services import affidavit_generator
    monkeypatch.setattr(schema, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(affidavit_generator, "PDF_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SYTECH_DEMO_MODE", "1")
    security.ATTEMPTS.clear()
    security.SESSIONS.clear()
    ACTIVE_RESET_TOKENS.clear()
    connected_clients.clear()
    seed.run_seed()
    yield
    security.ATTEMPTS.clear()
    security.SESSIONS.clear()
