"""Регресійні тести наявних ендпоінтів. Під час додавання нової функції ці тести не змінюються."""

from app.storage import TaskStore


def test_list_is_empty_at_start(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task_returns_201_and_appears_in_list(client):
    response = client.post(
        "/tasks",
        json={"title": "Здати звіт", "due_date": "2026-10-16", "priority": "high", "tags": ["навчання"]},
    )
    assert response.status_code == 201
    task = response.json()
    assert task == {
        "id": 1,
        "title": "Здати звіт",
        "due_date": "2026-10-16",
        "priority": "high",
        "tags": ["навчання"],
    }
    assert client.get("/tasks").json() == [task]


def test_priority_defaults_to_medium(client):
    task = client.post("/tasks", json={"title": "Купити молоко"}).json()
    assert task["priority"] == "medium"
    assert task["due_date"] is None
    assert task["tags"] == []


def test_invalid_priority_is_rejected(client):
    response = client.post("/tasks", json={"title": "Задача", "priority": "critical"})
    assert response.status_code == 422


def test_empty_title_is_rejected(client):
    response = client.post("/tasks", json={"title": ""})
    assert response.status_code == 422


def test_delete_removes_task(client):
    task_id = client.post("/tasks", json={"title": "Тимчасова"}).json()["id"]
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get("/tasks").json() == []


def test_delete_unknown_task_returns_404(client):
    assert client.delete("/tasks/999").status_code == 404


def test_tasks_persist_to_json(client, store):
    client.post("/tasks", json={"title": "Зберегти мене"})
    reloaded = TaskStore(store.path)
    assert [task.title for task in reloaded.list()] == ["Зберегти мене"]
