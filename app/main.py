"""HTTP-ендпоінти трекера задач."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response

from .models import Task, TaskCreate
from .storage import TaskStore, get_store

# Завантажуємо налаштування цього проєкту, зберігаючи пріоритет середовища.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

app = FastAPI(title="Трекер задач")


@app.get("/tasks", response_model=list[Task])
def list_tasks(store: TaskStore = Depends(get_store)) -> list[Task]:
    return store.list()


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(data: TaskCreate, store: TaskStore = Depends(get_store)) -> Task:
    return store.add(data)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, store: TaskStore = Depends(get_store)) -> Response:
    if not store.delete(task_id):
        raise HTTPException(status_code=404, detail="Задачу не знайдено")
    return Response(status_code=204)
