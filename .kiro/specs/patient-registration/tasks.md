# Voice AI Patient Registration — Implementation Tasks

> Requirements: #[[file:.kiro/specs/patient-registration/requirements.md]]
> Design: #[[file:.kiro/specs/patient-registration/design.md]]
> Execute in order. Each task is independently verifiable. `ruff` + `mypy` clean per task.

---

## Task 1: Project skeleton & tooling

- **Description:** Create the repo scaffold: `pyproject.toml` (deps + ruff/mypy/pytest
  config), `.gitignore`, `.env.example`, `app/` package dirs with `__init__.py`,
  `docs/challenge-brief.md`. No business logic yet.
- **Files:** `pyproject.toml`, `.gitignore`, `.env.example`, `app/__init__.py`,
  `app/core/__init__.py`, `app/common/__init__.py`, `app/router/__init__.py`,
  `app/modules/__init__.py`, `docs/challenge-brief.md`
- **Acceptance Criteria:**
  - [ ] `pyproject.toml` pins fastapi, uvicorn, sqlalchemy, pydantic[email], pydantic-settings
  - [ ] ruff + mypy + pytest configured (line-length, py311, select E/F/I)
  - [ ] `.env.example` documents DATABASE_URL, VAPI_WEBHOOK_SECRET, HOST, PORT, LOG_LEVEL
  - [ ] `.gitignore` excludes `.env`, `*.db`, caches, venv
  - [ ] challenge brief transcribed to `docs/challenge-brief.md`

---

## Task 2: Core infrastructure (config, database, logging, exceptions)

- **Description:** Implement `app/core/`: `config.py` (pydantic-settings, data only),
  `database.py` (sync engine, SessionLocal, Base, `get_db`, `init_db`),
  `logging_config.py` (stdout), `exceptions.py` (AppException hierarchy).
- **Files:** `app/core/config.py`, `app/core/database.py`, `app/core/logging_config.py`,
  `app/core/exceptions.py`
- **Acceptance Criteria:**
  - [ ] `settings` reads env with sane SQLite default; config has NO logic
  - [ ] `get_db` yields a session, commits on success, rolls back on error, always closes
  - [ ] `init_db` creates tables from `Base.metadata`
  - [ ] `AppException` + `NotFoundError`(404), `ValidationError`(422), `BadRequestError`(400), `ConflictError`(409)
  - [ ] core imports nothing from `app.modules`
  - [ ] ruff + mypy pass

---

## Task 3: Common layer (CRUDBase, response envelope)

- **Description:** Implement `app/common/crud_base.py` (generic get/create/update/delete,
  flush-only) and `app/common/schemas.py` (`ok()`/`err()` envelope helpers + `ErrorDetail`).
- **Files:** `app/common/crud_base.py`, `app/common/schemas.py`
- **Acceptance Criteria:**
  - [ ] `CRUDBase[Model, Create, Update]` generic with get_by_id/get_all/create/update/delete
  - [ ] CRUD write methods flush + refresh, never commit
  - [ ] `ok(data, status)` → `{data, error:null}`; `err(code, msg, status, fields=None)` → `{data:null, error:{code,message,fields?}}` (omit `fields` key when None)
  - [ ] common imports only core
  - [ ] ruff + mypy pass

---

## Task 4: Patient module — constants, model, exceptions

- **Description:** `patient/constants.py` (`MODULE`, `SEX_VALUES`, `US_STATES`),
  `patient/models.py` (`Patient` ORM with CHECK on sex, soft-delete, timestamps,
  `to_dict()`), `patient/exceptions.py` (`PatientNotFound`, `DuplicatePatient`).
- **Files:** `app/modules/patient/{__init__,constants,models,exceptions}.py`
- **Acceptance Criteria:**
  - [ ] model matches the data model table in design (types, nullability, lengths)
  - [ ] `patient_id` UUID default; `created_at`/`updated_at`/`deleted_at` as specified
  - [ ] CHECK constraint on `sex`; `phone_number` indexed
  - [ ] `to_dict()` returns JSON-friendly dict with ISO timestamps
  - [ ] ruff + mypy pass

---

## Task 5: Patient module — schemas & validation

- **Description:** `patient/schemas.py` with `PatientCreate` (all required rules),
  `PatientUpdate` (partial), reusable validators (phone, name, dob, state, zip, sex).
- **Files:** `app/modules/patient/schemas.py`
- **Dependencies:** Task 4 (constants)
- **Acceptance Criteria:**
  - [ ] `normalize_phone` strips formatting, drops leading 1, enforces 10 digits + area-code rule
  - [ ] `validate_dob` accepts MM/DD/YYYY + ISO, rejects future + <1900, stores ISO
  - [ ] name/city/state/zip/sex/email rules per FR-7
  - [ ] `PatientUpdate` validates only provided fields
  - [ ] ruff + mypy pass

---

## Task 6: Patient module — CRUD & service

- **Description:** `patient/crud.py` (`CRUDPatient`: get_active, list_filtered,
  get_by_phone) and `patient/service.py` (create/get/list/update/soft_delete/find_by_phone).
- **Files:** `app/modules/patient/crud.py`, `app/modules/patient/service.py`
- **Dependencies:** Tasks 3, 4, 5
- **Acceptance Criteria:**
  - [ ] all reads exclude `deleted_at IS NOT NULL` by default
  - [ ] `list_filtered` combines last_name (ilike) / dob / normalized phone
  - [ ] `get_by_phone` normalizes before matching
  - [ ] service owns commit; `get/update/soft_delete` take `patient_id` and raise `PatientNotFound` when missing/soft-deleted
  - [ ] soft_delete sets `deleted_at`; update bumps `updated_at`; `find_by_phone` returns `None` on no match (not an error)
  - [ ] no business logic in crud; no raw queries in service beyond crud calls
  - [ ] ruff + mypy pass

---

## Task 7: Patient module — REST router

- **Description:** `patient/router.py` with the five endpoints, envelope responses,
  correct status codes; register in `app/router/endpoints.py`.
- **Files:** `app/modules/patient/router.py`, `app/router/endpoints.py`
- **Dependencies:** Task 6
- **Acceptance Criteria:**
  - [ ] POST 201 / 422 / 400 / 500; GET list + filters; GET by id 200/404; PUT 200/404/422; DELETE 200/404
  - [ ] router wraps `PatientCreate`/`PatientUpdate` construction in `try/except pydantic.ValidationError` → `err("VALIDATION_ERROR", ..., fields=flattened)` (422). This is request-shape translation, not business logic
  - [ ] 404 for missing/soft-deleted comes from the service raising `PatientNotFound`, rendered by the global handler
  - [ ] every response uses `{data, error}` envelope
  - [ ] router thin: deps → service → return; no queries/business logic
  - [ ] router mounted under `/api/v1`
  - [ ] ruff + mypy pass

---

## Task 8: App entry point (main.py) + health

- **Description:** `app/main.py`: FastAPI app, lifespan `init_db`, CORS, global
  `AppException` + unhandled-exception handlers (sanitized 500), mount api_router,
  `GET /health`.
- **Files:** `app/main.py`
- **Dependencies:** Task 7
- **Acceptance Criteria:**
  - [ ] exception handlers render the error envelope; 500 is sanitized + logged
  - [ ] `/health` returns 200 when DB reachable, 503 otherwise, JSON body
  - [ ] `uvicorn app.main:app` boots; `/docs` available
  - [ ] ruff + mypy pass

---

## Task 9: Voice module — Vapi webhook

- **Description:** `voice/security.py` (shared-secret check), `voice/schemas.py` (Vapi
  tool-call shapes), `voice/service.py` (`handle_tool_call`: save_patient / lookup_patient
  via `patient.service`), `voice/router.py` (`POST /voice/vapi`). Register router.
- **Files:** `app/modules/voice/{__init__,security,schemas,service,router}.py`,
  `app/router/endpoints.py`
- **Dependencies:** Task 6, 7
- **Acceptance Criteria:**
  - [ ] parses `message.toolCalls[]`; handles arguments as dict OR JSON string
  - [ ] ALWAYS returns HTTP 200 with `{results:[{toolCallId, result|error}]}` (flat strings)
  - [ ] `save_patient` success → confirmation string (as `result`) with name; validation fail → field-named string **as `result`** (not `error`)
  - [ ] bad/missing secret and DB failure → `error` string; both still return HTTP 200
  - [ ] `lookup_patient` → match name+id or "no existing record"
  - [ ] secret mismatch → graceful error result (HTTP 200); skipped if no secret set
  - [ ] logs final collected payload + outcome to stdout
  - [ ] cross-module call uses `patient.service` only (aliased)
  - [ ] ruff + mypy pass

---

## Task 10: Dashboard module (bonus)

- **Description:** `dashboard/router.py` serving `GET /` — a minimal HTML table of
  non-deleted patients via `patient.service.list_patients`. Mounted on the app root
  (unversioned).
- **Files:** `app/modules/dashboard/{__init__,router.py}`, wire into `main.py`
- **Acceptance Criteria:**
  - [ ] `GET /` returns HTML listing patients (name, dob, phone, city/state, created_at)
  - [ ] reads via patient.service (no direct DB access)
  - [ ] no secrets / PII beyond demo data; safe HTML escaping
  - [ ] ruff + mypy pass

---

## Task 11: Vapi assistant config + system prompt

- **Description:** `vapi/system-prompt.md` (full, commented prompt per FR-8) and
  `vapi/assistant.json` (model/voice/tools with `save_patient` + `lookup_patient` schemas,
  server URL + secret header placeholders).
- **Files:** `vapi/system-prompt.md`, `vapi/assistant.json`
- **Acceptance Criteria:**
  - [ ] prompt covers greet, duplicate check, required-then-optional, read-back confirm,
        correction/spelling, re-prompt on field error, brief sign-off, start-over
  - [ ] tool JSON schemas match the fields `save_patient`/`lookup_patient` accept
  - [ ] no real secrets committed — placeholders only
  - [ ] prompt-engineering rationale documented inline

---

## Task 12: Seed script + tests

- **Description:** `scripts/seed.py` (1–2 demo patients) and the test suite
  (`tests/`): API lifecycle, validation table, voice webhook contract.
- **Files:** `scripts/seed.py`, `tests/conftest.py`,
  `tests/test_patient_api.py`, `tests/test_validation.py`, `tests/test_voice_webhook.py`
- **Dependencies:** Tasks 7, 9
- **Acceptance Criteria:**
  - [ ] seed is idempotent (skip if present)
  - [ ] API tests cover create/read/update/soft-delete + filters + 404 + 422
  - [ ] validation tests cover future DOB, 3-digit & 11-digit phone, bad state/zip, bad sex
  - [ ] voice tests assert the Vapi `{results:[{toolCallId,result}]}` contract + HTTP 200
  - [ ] `pytest` green; ruff + mypy pass

---

## Task 13: Deployment config + README

- **Description:** Deploy files (`render.yaml`/`Procfile`) and a complete `README.md`
  (setup, architecture, tech-stack justification, env vars, API reference, Vapi setup,
  known limitations, next steps). Add placeholders for live phone number + API base URL.
- **Files:** `render.yaml` (or `Procfile`), `README.md`
- **Acceptance Criteria:**
  - [ ] README: setup steps, architecture diagram, env var table, API examples (curl),
        Vapi configuration walkthrough, trade-offs, next steps
  - [ ] deploy config runs uvicorn binding `$PORT`
  - [ ] placeholders clearly marked for phone number / API base URL / dashboard URL

---

## Task 14: Final verification

- **Description:** Run full checks locally; smoke-test the whole flow with the test client.
- **Acceptance Criteria:**
  - [ ] `ruff check .` passes
  - [ ] `mypy app/` passes
  - [ ] `pytest` passes
  - [ ] manual: boot server, POST a patient, GET it back, simulate a Vapi tool call, view dashboard
  - [ ] no secrets in the diff; `.env` not committed
