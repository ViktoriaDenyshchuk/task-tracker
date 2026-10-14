"""Модель задачі: спільна для всіх ендпоінтів."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal["low", "medium", "high"]


class TaskCreate(BaseModel):
    """Тіло запиту POST /tasks."""

    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    priority: Priority = "medium"
    tags: list[str] = Field(default_factory=list, max_length=5)


class Task(TaskCreate):
    """Збережена задача."""

    id: int
