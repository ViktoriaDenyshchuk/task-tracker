# Трекер задач

Мінімальний FastAPI-сервіс задач — стартовий застосунок для демонстрації розробки на основі специфікацій (Spec-Driven Development) з GitHub Spec Kit і coding agent.

| Ендпоінт | Дія |
|---|---|
| `GET /tasks` | список задач |
| `POST /tasks` | створити задачу з полів `title`, `due_date`, `priority`, `tags` |
| `DELETE /tasks/{id}` | видалити задачу |

Задачі зберігаються в пам'яті й у файлі `data/tasks.json`.

Цей корінь — baseline для заняття: окремої теки `checkpoints/00_start` немає. Основний маршрут — SDD → специфікація/критерії → план/задачі → реалізація → незалежні перевірки → приймання. У baseline AI-ендпоінт ще відсутній; його додають у наступних фазах. Див. [покроковий маршрут](../SDD_WALKTHROUGH.md) і [checkpoint index](checkpoints/README.md). Підготовлені стани копіюють в окремі робочі теки; `06_mutated`/`07_evaluated` є історичними 44-тестовими варіантами й не продовжують актуальний `05_implemented` із 52 тестами.

## Швидкий старт

```powershell
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

Після запуску відкрийте `http://127.0.0.1:8000/docs`.

## Що в теці

| Шлях | Роль |
|---|---|
| `app/` | код застосунку |
| `tests/` | тести наявних ендпоінтів (`pytest` + `TestClient`, без мережі) |
| `.specify/memory/constitution.md` | правила проєкту для агента в кожній фазі Spec Kit |
| `evals/run_eval.py`, `evals/cases.json` | eval майбутньої функції `POST /tasks/parse` на 8 фразах |
| `checkpoints/` | готовий стан проєкту після кожної фази (`01_specified` … `07_evaluated`); корінь теки — це стан `00_start` |

Покрокова інструкція всього циклу — у [`../SDD_WALKTHROUGH.md`](../SDD_WALKTHROUGH.md).
