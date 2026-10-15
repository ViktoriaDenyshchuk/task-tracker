# Трекер задач

Мінімальний FastAPI-сервіс задач — стартовий застосунок для демонстрації розробки на основі специфікацій (Spec-Driven Development) з GitHub Spec Kit і coding agent.

| Ендпоінт | Дія |
|---|---|
| `GET /tasks` | список задач |
| `POST /tasks` | створити задачу з полів `title`, `due_date`, `priority`, `tags` |
| `DELETE /tasks/{id}` | видалити задачу |
| `POST /tasks/parse` | створити задачу з текстової фрази через OpenAI або OpenRouter |

Задачі зберігаються в пам'яті й у файлі `data/tasks.json`.

Цей корінь — baseline для заняття: окремої теки `checkpoints/00_start` немає. Основний маршрут — SDD → специфікація/критерії → план/задачі → реалізація → незалежні перевірки → приймання. У baseline AI-ендпоінт ще відсутній; його додають у наступних фазах. Див. [покроковий маршрут](../SDD_WALKTHROUGH.md) і [checkpoint index](checkpoints/README.md). Підготовлені стани копіюють в окремі робочі теки; `06_mutated`/`07_evaluated` є історичними 44-тестовими варіантами й не продовжують актуальний `05_implemented` із 52 тестами.

## Швидкий старт

```powershell
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

Після запуску відкрийте `http://127.0.0.1:8000/docs`.

## Створення задачі з тексту

`POST /tasks/parse` приймає JSON `{"text":"Здати звіт до п'ятниці, терміново #робота"}`. Успішний розбір повертає HTTP 201 із `task`, `path: "model"` і `parsed: true`. Якщо провайдер не відповідає або повертає невалідні поля, сервіс створює задачу з детермінованими правилами, повертає `path: "rules_fallback"`, `reason` і `needs_review: true`. Повторюється лише timeout або rate limit, рівно один раз. Порожній, лише пробільний або довший за 500 символів текст повертає HTTP 422.

Для OpenAI задайте `OPENAI_API_KEY` та, за потреби, `OPENAI_MODEL` у локальному `.env`. Для OpenRouter задайте `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY` та, за потреби, `OPENROUTER_MODEL` і `OPENROUTER_BASE_URL`. Типова модель — `gpt-4o-mini` для OpenAI і `openai/gpt-4o-mini` для OpenRouter. Ключі не додавайте до git.

Офлайн тести не потребують ключа чи мережі: `uv run pytest`. Окремий live eval викликає налаштованого провайдера і перевіряє вісім фраз: `uv run python evals/run_eval.py --provider openai` або `uv run python evals/run_eval.py --provider openrouter`. Eval звітує провайдера, модель, дату запуску, результат із 8 і кількість невалідних збережених значень.

## Що в теці

| Шлях | Роль |
|---|---|
| `app/` | код застосунку |
| `tests/` | тести наявних ендпоінтів (`pytest` + `TestClient`, без мережі) |
| `.specify/memory/constitution.md` | правила проєкту для агента в кожній фазі Spec Kit |
| `evals/run_eval.py`, `evals/cases.json` | eval майбутньої функції `POST /tasks/parse` на 8 фразах |
| `checkpoints/` | готовий стан проєкту після кожної фази (`01_specified` … `07_evaluated`); корінь теки — це стан `00_start` |

Покрокова інструкція всього циклу — у [`../SDD_WALKTHROUGH.md`](../SDD_WALKTHROUGH.md).
