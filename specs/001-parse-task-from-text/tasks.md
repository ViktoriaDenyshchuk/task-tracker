---
description: "Actionable tasks for creating tasks from natural language"
---

# Tasks: Створення задачі з тексту

**Input**: Design documents from `/specs/001-parse-task-from-text/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/post-tasks-parse.md`

**Tests**: Required by the feature acceptance criteria and project constitution. Automated tests use injected parser/date dependencies and make no network calls. The live evaluation remains a separate, explicit operation.

**Organization**: Tasks are grouped by user story. Existing routes (`GET /tasks`, `POST /tasks`, `DELETE /tasks/{id}`) and `tests/test_tasks.py` must remain unchanged.

## Phase 1: Setup

**Purpose**: Add the model SDK dependency and prepare feature-specific evaluation data.

- [ ] T001 Add the official OpenAI SDK dependency in `pyproject.toml` and update its resolved entries in `uv.lock`
- [ ] T002 [P] Add the eight evaluation phrases and independently specified expected fields in `evals/cases.json`; this file has no dependency on the SDK manifest or lockfile

---

## Phase 2: Foundational

**Purpose**: Establish injectable time and parser boundaries required by the feature.

- [ ] T003 [P] Implement the Europe/Kyiv `get_today` dependency in `app/clock.py`
- [ ] T004 [P] Define parser proposal types, controlled failure reasons, parser interface, and `get_parser` dependency in `app/parser.py`

**Checkpoint**: Date and parser dependencies are independently replaceable by endpoint tests and evals.

---

## Phase 3: User Story 1 - Створити задачу з описової фрази (Priority: P1) 🎯 MVP

**Goal**: Parse a natural-language phrase into a validated task, persist it, and return the created task.

**Independent Test**: Inject a parser proposal and fixed date, POST a valid phrase, then verify HTTP 201, parsed task fields, and presence in `GET /tasks`.

### Tests for User Story 1

- [ ] T005 [P] [US1] Add endpoint tests for successful model parsing, response shape, persistence, and visibility through `GET /tasks` in `tests/test_parse_task.py`
- [ ] T006 [P] [US1] Add parser tests for provider configuration, structured proposal decoding, timeout settings, disabled SDK retries, and SDK failure classification in `tests/test_parser.py`

### Implementation for User Story 1

- [ ] T007 [US1] Configure OpenAI and OpenRouter SDK clients with a 20-second timeout and `max_retries=0` in `app/parser.py`
- [ ] T008 [US1] Implement model proposal decoding and map provider responses and exceptions to controlled parser results in `app/parser.py`
- [ ] T009 [US1] Add parse request/response schemas and the `POST /tasks/parse` route in `app/main.py`, without editing existing route handlers
- [ ] T010 [US1] Validate model title, due date, priority, and tags before constructing `TaskCreate` in the new parse flow in `app/main.py`
- [ ] T011 [US1] Save validated tasks through the existing `TaskStore` and return `path: "model"` and `parsed: true` in the new parse flow in `app/main.py`

**Checkpoint**: A valid model proposal creates a validated, persisted task without changing the `Task` schema or existing route behavior.

---

## Phase 4: User Story 2 - Обробити відсутні або неоднозначні деталі (Priority: P2)

**Goal**: Reject invalid input before model calls and provide safe defaults, bounded retries, and review-marked fallback for valid text.

**Independent Test**: Inject parser outcomes and a fixed date; verify input rejection/no parser call, missing-field defaults, each retry/fallback reason and count, fallback fields, date validation, and tag normalization.

### Tests for User Story 2

- [ ] T012 [US2] Add tests for empty, whitespace-only, 500-character, and over-limit input, asserting rejected requests never invoke the parser or save a task in `tests/test_parse_task.py`
- [ ] T013 [US2] Add tests for absent date/priority defaults, explicit ISO fallback dates, title truncation, and hashtag extraction in `tests/test_parse_task.py`
- [ ] T014 [US2] Add parameterized tests for model validation failures, all retryable and non-retryable reasons, retry counts, original reason preservation, and fallback response metadata in `tests/test_parse_task.py`
- [ ] T015 [US2] Add tests for Europe/Kyiv date injection, model and explicit tag normalization/deduplication, invalid tags, and invalid or past model dates in `tests/test_parse_task.py`

### Implementation for User Story 2

- [ ] T016 [US2] Reject blank and over-500-character text with HTTP 422 before invoking the parser in the new parse flow in `app/main.py`
- [ ] T017 [US2] Apply `medium` priority and null due-date defaults when valid model proposals omit those fields in the new parse flow in `app/main.py`
- [ ] T018 [US2] Implement deterministic fallback title, explicit non-past `YYYY-MM-DD` extraction, medium priority, and explicit hashtag extraction in the new parse flow in `app/main.py`
- [ ] T019 [US2] Retry exactly once for `timeout` and `rate_limited`, and preserve the first failure reason when fallback follows a failed retry in the new parse flow in `app/main.py`
- [ ] T020 [US2] Return HTTP 201 with `rules_fallback`, `parsed: false`, `reason`, and `needs_review: true` for parser failures in the new parse flow in `app/main.py`
- [ ] T021 [US2] Normalize explicit and model-suggested tags and enforce existing tag constraints before saving in the new parse flow in `app/main.py`
- [ ] T022 Inspect the existing `evals/run_eval.py` against the eight-case contract; adapt it only where needed to use `get_parser` and `get_today`, isolate live model calls from tests, and report provider, model, run date, score out of 8, and count of invalid saved values. Do not recreate the runner; keep it an explicit live-eval command.

**Checkpoint**: Invalid text is rejected without model activity; valid text always creates either a validated model task or a review-marked fallback, never an HTTP 500 for model failures.

---

## Phase 5: User Story 3 - Зберегти наявну роботу трекера (Priority: P2)

**Goal**: Keep list, manual creation, and deletion contracts unchanged.

**Independent Test**: Exercise the existing `GET /tasks`, `POST /tasks`, and `DELETE /tasks/{id}` contracts after adding the parse route.

### Tests for User Story 3

- [ ] T023 [US3] Add regression assertions for `GET /tasks`, `POST /tasks`, and `DELETE /tasks/{id}` in the new `tests/test_parse_task.py`; leave `tests/test_tasks.py` unchanged and do not alter existing endpoint expectations

### Implementation for User Story 3

- [ ] T024 [US3] Integrate only the new `POST /tasks/parse` flow with the existing `TaskStore` in `app/main.py`; preserve existing GET/POST/DELETE route handlers and request/response contracts, leave `tests/test_tasks.py` untouched, and do not change `Task`/`TaskCreate` schemas in `app/models.py`

**Checkpoint**: Existing tracker clients retain their current endpoint contracts; compatibility evidence comes from unchanged existing tests plus T023 regression assertions and review of the diff.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Document configuration and reproducible verification steps.

- [ ] T025 [P] Document provider configuration, fallback behavior, and offline/live evaluation commands in `README.md`
- [ ] T026 [P] Keep manual API and evaluation instructions aligned with the contract in `specs/001-parse-task-from-text/quickstart.md`

---

## Acceptance Criteria Traceability

| Criterion | Tasks | Required checks/evidence |
|---|---|---|
| AC1 — successful parse returns 201/`parsed: true` and task is listed | T005, T009–T011 | Stubbed endpoint test checks status, response fields, persistence, and subsequent `GET /tasks` visibility. |
| AC2 — application supplies Europe/Kyiv date context | T003, T015, T022 | Fixed-clock test verifies the date passed to the parser; live-eval report includes E1, E3, and E6 with the fixed date. |
| AC3 — every model field is validated before persistence | T010, T014–T015, T021 | Stubbed invalid-field tests cover title, date, priority, and tags; mutation check of date validation is part of developer verification. |
| AC4 — exact retry policy and safe fallback metadata; never 500 | T014, T019–T020 | Stubbed tests cover every reason, call counts, preserved original reason, fallback fields, HTTP 201, and absence of HTTP 500. |
| AC5 — blank/over-limit input yields 422 without parser call | T012, T016 | Boundary tests assert HTTP 422, parser call count zero, and no task saved. |
| AC6 — existing GET/POST/DELETE contracts remain unchanged | T023–T024 | Existing `tests/test_tasks.py` remains unchanged and passes; new regression assertions and diff review confirm existing route handlers/contracts were not edited. |
| AC7 — automated tests work offline without API keys | T005–T006, T012–T015, T023 | All model calls in tests use injected stubs; developer verification runs `uv run pytest` without `.env` and reviews the diff for network calls in tests. |
| AC8 — eight-case live eval reaches at least 7/8 with zero invalid saved values | T002, T022 | Explicit `uv run python evals/run_eval.py` live-eval report records provider, model, actual run date, score, and invalid saved-value count. |

## Dependencies & Execution Order

### Phase Dependencies

- T001 and T002 are independent: the case data is specified independently of the SDK dependency; both precede feature implementation as setup inputs.
- Setup (Phase 1) precedes Foundational (Phase 2).
- Foundational (Phase 2) blocks all user stories.
- Each user story follows test-first ordering: its relevant tests are written before the implementation they cover.
- US2 builds on the route/parser contract introduced by US1. T022 reviews and, only if necessary, adapts the pre-existing eval runner after its dependency contract is available.
- US3 compatibility checks are added in a new test file after route integration; its implementation task is restricted to the new route and must preserve all existing routes and schemas.
- Polish follows the stories selected for delivery.

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2; no dependency on another story. This is the MVP.
- **US2 (P2)**: Depends on the parse route and parser result contract from US1; complete its tests before fallback/retry changes.
- **US3 (P2)**: Depends on parse-route integration; compatibility assertions are added to `tests/test_parse_task.py`, not the existing `tests/test_tasks.py`.

### Parallel Opportunities

- T001 and T002 can proceed in parallel: they edit separate files and T002 has no dependency on the SDK manifest.
- T003 and T004 can proceed in parallel: they define independent dependencies in separate files.
- T005 and T006 can proceed in parallel after T003–T004: they edit separate test files and cover independent boundaries.
- T012–T015 must be added together or sequentially because all edit `tests/test_parse_task.py`; none is marked `[P]`.
- T016–T021 are sequenced because they change the same parse flow in `app/main.py`.
- T022 may proceed alongside route-policy implementation only after the eval runner's dependency contract is available; keep the live operation separate from automated tests.
- T025 and T026 can proceed in parallel because they edit separate documentation files and have no dependency on each other.

## Parallel Example: User Story 1

```text
Task: T005 Add stubbed endpoint and persistence tests in tests/test_parse_task.py
Task: T006 Add parser boundary tests in tests/test_parser.py
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Setup and Foundational phases.
2. Write T005–T006 tests, then implement the successful `POST /tasks/parse` model path.
3. Verify the US1 independent test criteria with injected dependencies.
4. Stop at the US1 checkpoint for an independently demonstrable MVP.

### Incremental Delivery

1. Complete US1 for successful natural-language task creation.
2. Add US2 input validation, defaults, retries, fallback, and eval-runner contract review/adaptation.
3. Complete US3 compatibility assertions for existing tracker endpoints while preserving their implementation and tests.
4. Finish documentation after the selected stories are complete.

## Notes

- Every task uses the required checkbox, sequential ID, optional parallel marker, user-story label where applicable, and at least one concrete file path.
- `[P]` is reserved for tasks that have no dependency on incomplete work and touch independent files. T002 is independent of T001; tests T012–T015 share one file and are deliberately not parallel-marked.
- Test tasks precede the implementation they cover. Tests must remain offline and leave `tests/test_tasks.py` unchanged; the live eval is not an automated test.
- T023/T024 do not authorize changes to existing GET/POST/DELETE route handlers or schemas.
