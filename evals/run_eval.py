"""Eval функції POST /tasks/parse на 8 фразах із фіксованою датою «сьогодні».

Запуск (з кореня проєкту, ключ у .env):
    uv run python evals/run_eval.py --provider openai
    uv run python evals/run_eval.py --provider openrouter --save

Скрипт викликає справжню модель через той самий HTTP-ендпоінт, що й користувач,
але підміняє дві залежності: дату (get_today -> 2026-10-12) і сховище (тимчасовий файл).
Тести (pytest) перевіряють застосунок на заданих виходах заглушки; eval — поведінку реальної моделі.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CASES_PATH = Path(__file__).with_name("cases.json")
RESULTS_DIR = Path(__file__).with_name("results")
ALLOWED_PRIORITIES = {"low", "medium", "high"}


def load_app():
    """Імпортує застосунок і залежності, які фіксує plan.md: get_parser і get_today."""
    try:
        from fastapi.testclient import TestClient

        from app.clock import get_today
        from app.main import app
        from app.parser import get_parser
        from app.storage import TaskStore, get_store
    except ImportError as error:
        sys.exit(
            "Eval потребує реалізованої функції POST /tasks/parse із залежностями "
            f"app.parser.get_parser і app.clock.get_today. Імпорт не вдався: {error}"
        )
    if not any(getattr(route, "path", None) == "/tasks/parse" for route in app.routes):
        sys.exit("Ендпоінт POST /tasks/parse ще не реалізовано.")
    return TestClient, app, get_parser, get_today, TaskStore, get_store


class RecordingParser:
    """Обгортка над справжнім парсером: запам'ятовує останній вихід моделі для таблиці."""

    def __init__(self, inner):
        self.inner = inner
        self.last_output = None
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def propose(self, *args, **kwargs):
        self.calls += 1
        self.last_output = None
        result = self.inner.propose(*args, **kwargs)
        self.last_output = result
        return result


def invalid_fields(task: dict, today: date) -> list[str]:
    """Жорстка умова: збережена задача не може містити невалідних значень."""
    problems = []
    title = task.get("title") or ""
    if not 1 <= len(title) <= 200:
        problems.append("title")
    if task.get("priority") not in ALLOWED_PRIORITIES:
        problems.append("priority")
    due = task.get("due_date")
    if due is not None:
        try:
            if date.fromisoformat(due) < today:
                problems.append("due_date<today")
        except ValueError:
            problems.append("due_date")
    tags = task.get("tags") or []
    if len(tags) > 5 or len(set(tags)) != len(tags) or any(tag != tag.lower() or not tag for tag in tags):
        problems.append("tags")
    return problems


def check_expectations(result: dict, expect: dict) -> list[str]:
    misses = []
    task = result.get("task", result)
    for key, expected in expect.items():
        if key == "tags_include":
            if expected not in (task.get("tags") or []):
                misses.append(f"tags не містить «{expected}»")
        elif key == "priority_not":
            if task.get("priority") == expected:
                misses.append(f"priority = {expected}")
        elif key in {"path", "reason", "parsed", "needs_review"}:
            if result.get(key) != expected:
                misses.append(f"{key}: очікувано {expected!r}, отримано {result.get(key)!r}")
        elif task.get(key) != expected:
            misses.append(f"{key}: очікувано {expected!r}, отримано {task.get(key)!r}")
    return misses


def describe_output(output) -> str:
    if output is None:
        return "—"
    if hasattr(output, "model_dump"):
        output = output.model_dump(mode="json")
    text = json.dumps(output, ensure_ascii=False)
    return text if len(text) <= 160 else text[:157] + "..."


def run(provider: str, save: bool) -> int:
    os.environ["LLM_PROVIDER"] = provider
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
        os.environ["LLM_PROVIDER"] = provider
    except ImportError:
        pass

    TestClient, app, get_parser, get_today, TaskStore, get_store = load_app()
    spec = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    today = date.fromisoformat(spec["today"])

    real_parser = get_parser()
    if getattr(real_parser, "client", True) is None:
        sys.exit(
            f"Ключ для провайдера {provider} не знайдено в .env. Без ключа всі фрази підуть у rules_fallback, "
            "і це вже не eval моделі. Додайте ключ або покажіть збережений результат з evals/results/."
        )
    parser = RecordingParser(real_parser)
    provider_name = getattr(parser.inner, "provider", provider)
    model_name = getattr(parser.inner, "model", "невідомо")

    rows, passed, invalid_saved, fallbacks = [], 0, 0, []
    with tempfile.TemporaryDirectory() as tmp:
        store = TaskStore(Path(tmp) / "eval_tasks.json")
        app.dependency_overrides[get_today] = lambda: today
        app.dependency_overrides[get_parser] = lambda: parser
        app.dependency_overrides[get_store] = lambda: store
        try:
            with TestClient(app) as client:
                for case in spec["cases"]:
                    response = client.post("/tasks/parse", json={"text": case["text"]})
                    if response.status_code != 201:
                        result = {"status": response.status_code}
                        task_result = result
                        misses = [f"HTTP {response.status_code}"]
                        problems = ["http"]
                        persisted = None
                        persisted_problems = []
                    else:
                        result = response.json()
                        task_result = result.get("task") or {}
                        misses = check_expectations(result, case["expect"])
                        persisted_response = client.get("/tasks")
                        persisted_tasks = (
                            persisted_response.json()
                            if persisted_response.status_code == 200
                            else []
                        )
                        persisted = next(
                            (
                                task
                                for task in persisted_tasks
                                if isinstance(task, dict) and task.get("id") == (result.get("task") or {}).get("id")
                            ),
                            None,
                        ) if isinstance(persisted_tasks, list) else None
                        persisted_problems = []
                        if persisted is None:
                            persisted_problems.append("not_persisted")
                            misses.append("задачу не знайдено в GET /tasks")
                        else:
                            persisted_problems.extend(invalid_fields(persisted, today))
                            fields = ("title", "due_date", "priority", "tags")
                            if any(persisted.get(field) != task_result.get(field) for field in fields):
                                persisted_problems.append("response_persistence_mismatch")
                            if any(key in persisted for key in ("parsed", "path", "reason", "needs_review")):
                                persisted_problems.append("provenance_persisted")
                            if persisted_problems:
                                misses.append("збережений запис не відповідає контракту задачі")
                        problems = invalid_fields(task_result, today) + persisted_problems
                    ok = not misses and not problems
                    passed += ok
                    invalid_saved += bool(persisted_problems)
                    if result.get("path") == "rules_fallback":
                        fallbacks.append(f"{case['id']}:{result.get('reason')}")
                    rows.append(
                        {
                            "id": case["id"],
                            "text": case["text"],
                            "model_output": describe_output(parser.last_output),
                            "calls": parser.calls,
                            "path": result.get("path", "—"),
                            "reason": result.get("reason") or "—",
                            "saved": {
                                k: (persisted if persisted is not None else task_result).get(k)
                                for k in ("title", "due_date", "priority", "tags")
                            },
                            "ok": ok,
                            "notes": "; ".join(misses + [f"невалідне поле: {p}" for p in problems]) or "—",
                        }
                    )
                    parser.calls = 0
        finally:
            app.dependency_overrides.clear()

    acceptance = spec["acceptance"]
    accepted = passed >= acceptance["min_passed"] and invalid_saved <= acceptance["max_invalid_saved"]
    run_at = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M %Z")

    lines = [
        f"# Результат eval POST /tasks/parse — {run_at}",
        "",
        f"- Провайдер: `{provider_name}`",
        f"- Модель: `{model_name}`",
        f"- Дата «сьогодні» для eval: {today.isoformat()} ({spec['timezone']})",
        f"- Пройдено: **{passed}/{len(rows)}** (поріг ≥{acceptance['min_passed']})",
        f"- Порушень перевірки збереження або невалідних збережених значень: **{invalid_saved}** (поріг {acceptance['max_invalid_saved']})",
        f"- `rules_fallback`: {len(fallbacks)} ({', '.join(fallbacks) or 'немає'})",
        f"- Висновок: **{'прийнято' if accepted else 'не прийнято'}**",
        "",
        "| № | Фраза | Вихід моделі | Викликів | path | reason | Збережено | Збіг | Примітка |",
        "|---|---|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        saved = json.dumps(row["saved"], ensure_ascii=False)
        cells = [row["id"], row["text"], row["model_output"], str(row["calls"]), row["path"], row["reason"], saved, "✓" if row["ok"] else "✗", row["notes"]]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    lines += [
        "",
        "Межа доказу: це зріз поведінки однієї моделі в один день на 8 синтетичних фразах, а не гарантія якості.",
    ]
    report = "\n".join(lines) + "\n"

    if save:
        RESULTS_DIR.mkdir(exist_ok=True)
        slug = re.sub(r"[^a-z0-9.-]+", "-", f"{provider_name}-{model_name}".lower()).strip("-")
        out = RESULTS_DIR / f"{datetime.now():%Y-%m-%d}-{slug}.md"
        out.write_text(report, encoding="utf-8")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    if save:
        print(f"Збережено: {out.relative_to(ROOT)}")
    return 0 if accepted else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["openai", "openrouter"], default=os.getenv("LLM_PROVIDER", "openai"))
    parser.add_argument("--save", action="store_true", help="зберегти звіт у evals/results/")
    args = parser.parse_args()
    sys.exit(run(args.provider, args.save))


if __name__ == "__main__":
    main()
