# Implementation Plan: Створення задачі з тексту

**Branch**: `001-parse-task-from-text` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-parse-task-from-text/spec.md`

## Summary

Додати `POST /tasks/parse`, що приймає звичайний текст, отримує пропозицію полів задачі від OpenAI або OpenRouter через OpenAI-сумісний SDK-клієнт, детерміновано перевіряє й нормалізує ці поля та додає задачу до спільного JSON-сховища. Для недоступної/непридатної відповіді застосовуються правила fallback і метадані перевірки. Поточну дату надає залежність `get_today` у `app/clock.py` з часовим поясом Europe/Kyiv. SDK timeout становить 20 секунд, `max_retries=0`; застосунок сам робить рівно один retry лише для `timeout` і `rate_limited`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, Pydantic v2, офіційний `openai` SDK, python-dotenv
**Storage**: Існуючий in-memory `TaskStore` зі збереженням у JSON-файл
**Testing**: pytest, FastAPI TestClient, `app.dependency_overrides`; жодних мережевих викликів у тестах
**Target Platform**: Python-середовище, що підтримує застосунок FastAPI
**Project Type**: Одинарний backend web service
**Performance Goals**: Один виклик моделі не довше 20 секунд; для timeout/rate limit допускається ще один виклик
**Constraints**: Pydantic v2; новий маршрут не змінює наявні контракти; SDK retries вимкнені; тести не змінюють `tests/test_tasks.py`; секрети лише з `.env`; evals/ на 8 фразах використовує `get_parser` і `get_today`.
**Scale/Scope**: Один новий endpoint, залежності parser/clock, модельні та транспортні схеми, перевірки й ізольований eval; без БД, UI, auth чи фонового виконання.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Тести без мережі й без ключів — PASS.** Parser і today підмінюються через FastAPI `dependency_overrides`; unit/endpoint тести працюють із заглушкою, eval залишається окремим live-інструментом.
- **II. Модель пропонує, застосунок вирішує — PASS.** Транспортна структура й кожне поле перевіряються прикладним кодом перед створенням `Task`.
- **III. Поточну дату дає застосунок — PASS.** `get_today` інкапсулює Europe/Kyiv і передається до парсера/валідації; тести та eval можуть її фіксувати.
- **IV. Секрети лише в `.env` — PASS.** Конфігурація читає ключ з оточення; секрети не потрапляють у дані помилок чи звіт.
- **V. Малі зміни, наявна поведінка незмінна — PASS.** Додається маршрут і суміжні модулі; `tests/test_tasks.py` та контракти наявних endpoint не змінюються. Новий пакет не потрібен.
- **VI. Кожен критерій має evidence — PASS із планом evidence.** Контрактні та інтеграційні тести покривають AC1–AC7, 8-фразовий live eval — AC2/AC8; кожна причина retry/fallback і кожне поле матимуть незалежні перевірки.

**Post-design gate**: PASS. Обрані модулі зберігають мережеву межу в parser, час — у clock, валідацію — у застосунку, а запис роблять існуючі моделі та сховище; винятків конституції немає.

## Project Structure

### Documentation (this feature)

```text
specs/001-parse-task-from-text/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── post-tasks-parse.md
```

### Source Code (repository root)

```text
app/
├── main.py       # новий POST /tasks/parse; існуючі маршрути без змін
├── models.py     # TaskCreate/Task лишаються спільною моделлю збереженої задачі
├── parser.py     # parser protocol, провайдер-конфігурація, SDK-виклик і класифікація помилок
├── clock.py      # get_today у Europe/Kyiv
└── storage.py    # існуючий TaskStore

tests/
├── conftest.py
├── test_tasks.py # не змінюється
└── test_parse_task.py # нові unit/endpoint тести із dependency_overrides

evals/
├── cases.json
└── run_eval.py   # наявний live eval; той самий get_parser/get_today контракт
```

**Structure Decision**: Один наявний FastAPI застосунок; дотриматися домовлених меж `app.parser.get_parser` і `app.clock.get_today`, щоб tests і `evals/run_eval.py` інжектували залежності без знання провайдера.

## Complexity Tracking

Немає порушень конституції, що потребують обґрунтування.
