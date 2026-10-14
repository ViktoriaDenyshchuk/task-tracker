"""In-memory сховище задач зі збереженням у JSON-файл."""

import json
import os
from pathlib import Path

from .models import Task, TaskCreate

DEFAULT_DATA_PATH = Path("data/tasks.json")


class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._tasks: list[Task] = []
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._tasks = [Task.model_validate(item) for item in raw]

    def list(self) -> list[Task]:
        return list(self._tasks)

    def add(self, data: TaskCreate) -> Task:
        next_id = max((task.id for task in self._tasks), default=0) + 1
        task = Task(id=next_id, **data.model_dump())
        self._tasks.append(task)
        self._save()
        return task

    def delete(self, task_id: int) -> bool:
        before = len(self._tasks)
        self._tasks = [task for task in self._tasks if task.id != task_id]
        if len(self._tasks) == before:
            return False
        self._save()
        return True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [task.model_dump(mode="json") for task in self._tasks]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


_store: TaskStore | None = None


def get_store() -> TaskStore:
    """Залежність FastAPI: одне сховище на процес. Тести підміняють її через dependency_overrides."""
    global _store
    if _store is None:
        _store = TaskStore(Path(os.getenv("TASK_TRACKER_DATA", DEFAULT_DATA_PATH)))
    return _store
