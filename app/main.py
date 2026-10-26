"""HTTP-ендпоінти трекера задач."""

from pathlib import Path
import re
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from .clock import get_today
from .models import Task, TaskCreate
from .parser import FailureReason, ParseFailure, TaskParser, get_parser
from .storage import TaskStore, get_store

# Завантажуємо налаштування цього проєкту, зберігаючи пріоритет середовища.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

app = FastAPI(title="Трекер задач")


class ParseTaskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ParseTaskResponse(BaseModel):
    task: Task
    path: str = "model"
    parsed: bool = True


class ParseTaskFallbackResponse(BaseModel):
    task: Task
    path: str = "rules_fallback"
    parsed: bool = False
    reason: str
    needs_review: bool = True


def _tags(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("invalid tag")
        tag = value.strip().lower()
        if not tag or len(tag) > 50 or not re.fullmatch(r"[\w-]+", tag, flags=re.UNICODE):
            raise ValueError("invalid tag")
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    if len(result) > 5:
        raise ValueError("too many tags")
    return result


def _explicit_tags(text: str) -> list[str]:
    return _tags(re.findall(r"#([\w-]+)", text, flags=re.UNICODE))


def _fallback_tags(text: str) -> list[str]:
    tags: list[str] = []
    for raw in re.findall(r"#([\w-]+)", text, flags=re.UNICODE):
        tag = raw.strip().lower()
        if tag and len(tag) <= 50 and tag not in tags:
            tags.append(tag)
        if len(tags) == 5:
            break
    return tags


def _validated_task(proposal, text: str, today: date) -> TaskCreate:
    title = proposal.title.strip() if isinstance(proposal.title, str) else ""
    if not 1 <= len(title) <= 200:
        raise ValueError("invalid title")
    if proposal.due_date is None:
        due_date = None
    else:
        if not isinstance(proposal.due_date, str):
            raise ValueError("invalid date")
        due_date = date.fromisoformat(proposal.due_date)
        if due_date.isoformat() != proposal.due_date or due_date < today:
            raise ValueError("invalid date")
    priority = "medium" if proposal.priority is None else proposal.priority
    if priority not in {"low", "medium", "high"}:
        raise ValueError("invalid priority")
    tags = _tags([*(proposal.tags or []), *_explicit_tags(text)])
    return TaskCreate(title=title, due_date=due_date, priority=priority, tags=tags)


def _fallback_task(text: str, today: date) -> TaskCreate:
    title = text.strip()[:200]
    due_date = None
    for token in re.findall(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", text):
        try:
            candidate = date.fromisoformat(token)
        except ValueError:
            continue
        if candidate >= today:
            due_date = candidate
            break
    return TaskCreate(title=title, due_date=due_date, priority="medium", tags=_fallback_tags(text))


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


@app.post("/tasks/parse", response_model=ParseTaskResponse | ParseTaskFallbackResponse, status_code=201)
def parse_task(
    data: ParseTaskRequest,
    parser: TaskParser = Depends(get_parser),
    today: date = Depends(get_today),
    store: TaskStore = Depends(get_store),
) -> ParseTaskResponse | ParseTaskFallbackResponse:
    if not data.text.strip():
        raise HTTPException(status_code=422, detail="text must not be blank")
    original_reason: FailureReason | None = None
    proposal = None
    for attempt in range(2):
        try:
            proposal = parser.propose(data.text, today)
            task_data = _validated_task(proposal, data.text, today)
            break
        except ParseFailure as exc:
            reason = exc.reason
        except (ValueError, TypeError, AttributeError):
            reason = FailureReason.INVALID_SEMANTICS
        if original_reason is None:
            original_reason = reason
        if attempt == 0 and reason in {FailureReason.TIMEOUT, FailureReason.RATE_LIMITED}:
            continue
        task = store.add(_fallback_task(data.text, today))
        return ParseTaskFallbackResponse(task=task, reason=original_reason.value)
    task = store.add(task_data)
    return ParseTaskResponse(task=task, path="model", parsed=True)
