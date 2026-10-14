import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import TaskStore, get_store


@pytest.fixture
def store(tmp_path):
    return TaskStore(tmp_path / "tasks.json")


@pytest.fixture
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
