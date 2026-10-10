# Voice AI Patient Registration — Technical Design

> Requirements: #[[file:.kiro/specs/patient-registration/requirements.md]]
> Challenge brief: #[[file:docs/challenge-brief.md]]
> Architecture lineage: Mishkat-labs VLE modular monolith (router → service → crud → models)

## Architecture Overview

```
Caller (phone)
   │  speech
   ▼
Vapi Assistant  ── owns: phone number, STT, TTS, LLM loop, system prompt, tools
   │  HTTPS tool calls (save_patient / lookup_patient), shared-secret header
   ▼
FastAPI backend (this repo)
   │  app/modules/patient/    ── REST API  (/api/v1/patients)
   │  app/modules/voice/      ── Vapi webhook (/api/v1/voice/vapi)
   │  app/modules/dashboard/  ── read-only HTML (/)
   ▼
SQLite (patients.db)  ── SQLAlchemy, persistent on disk
```

The backend is a **modular monolith** following the VLE vertical-slice layering,
adapted to a single-tenant, synchronous SQLite app:

- **No** Cognito/Redis/Celery/multi-tenancy (not needed for this challenge).
- **Sync** SQLAlchemy (`Session`), not async — SQLite + low concurrency makes sync
  simpler and avoids an async driver. Layer rules are otherwise identical to VLE.
- `patient` is the core domain module; `voice` and `dashboard` are thin modules that
  call `patient.service` (cross-module = service only, exactly like VLE).

## Folder Structure

```
voice-patient-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, lifespan, exception handlers, router mount, /health
│   ├── core/                       # infrastructure leaves (import nothing from modules)
│   │   ├── config.py               # pydantic-settings, singleton `settings` (data only)
│   │   ├── database.py             # engine, SessionLocal, Base, get_db(), init_db()
│   │   ├── logging_config.py       # stdout logging setup
│   │   └── exceptions.py           # AppException hierarchy
│   ├── common/
│   │   ├── crud_base.py            # generic CRUDBase (get/create/update/...)
│   │   └── schemas.py              # response envelope helpers (ok/err), ErrorDetail
│   ├── router/
│   │   └── endpoints.py            # api_router = APIRouter(prefix=/api/v1); mounts module routers
│   └── modules/
│       ├── patient/                # CORE DOMAIN — owns the data + validation + REST
│       │   ├── constants.py        # MODULE slug, SEX_VALUES, US_STATES
│       │   ├── models.py           # Patient ORM model
│       │   ├── schemas.py          # PatientCreate / PatientUpdate / PatientResponse + validators
│       │   ├── crud.py             # CRUDPatient (data access, soft-delete, filters, phone lookup)
│       │   ├── service.py          # business logic (create/get/list/update/soft-delete/duplicate)
│       │   ├── exceptions.py       # PatientNotFound, DuplicatePatient
│       │   └── router.py           # /patients endpoints (thin)
│       ├── voice/                  # Vapi webhook adapter
│       │   ├── schemas.py          # Vapi tool-call request/response shapes
│       │   ├── service.py          # map tool args → PatientCreate, call patient.service
│       │   ├── security.py         # verify shared-secret header
│       │   └── router.py           # /voice/vapi endpoint
│       └── dashboard/              # read-only demo UI
│           └── router.py           # GET / -> HTML table (calls patient.service)
├── vapi/
│   ├── assistant.json              # Vapi assistant config (model, voice, tools, server URL)
│   └── system-prompt.md            # the LLM system prompt (documented & commented)
├── tests/
│   ├── conftest.py                 # test client + in-memory DB override
│   ├── test_patient_api.py         # REST CRUD + validation + soft-delete
│   ├── test_validation.py          # field-level rule tests (DOB, phone, state, ...)
│   └── test_voice_webhook.py       # Vapi tool-call contract tests
├── scripts/
│   └── seed.py                     # insert 1–2 demo patients
├── docs/
│   └── challenge-brief.md          # transcribed challenge PDF
├── .env.example
├── .gitignore
├── pyproject.toml                  # deps + ruff/mypy/pytest config
├── Procfile / render.yaml          # deploy config
└── README.md
```

### Layer rules (inherited from VLE engineering rules)
- Router: parse HTTP → call ONE service function → return. No queries, no business `if`.
- Service: business rules, validation orchestration, calls own crud + other modules' services.
- CRUD: pure data access via `CRUDBase` + named query methods. Returns models or `None`.
- Models: ORM only. Schemas: Pydantic only. Exceptions: `AppException` subclasses.
- Cross-module: `voice`/`dashboard` import `patient.service` (aliased) — never its crud/models.
- `core`/`common` import nothing from `modules`.

## Data Model

### Table `patients`

| Column | Type | Null | Notes |
|--------|------|------|-------|
| `patient_id` | String(36) PK | no | UUID4, generated |
| `first_name` | String(50) | no | |
| `last_name` | String(50) | no | |
| `date_of_birth` | String(10) | no | ISO `YYYY-MM-DD` |
| `sex` | String(20) | no | CHECK in SEX_VALUES |
| `phone_number` | String(10) | no | normalized digits, indexed |
| `email` | String(254) | yes | |
| `address_line_1` | String(200) | no | |
| `address_line_2` | String(200) | yes | |
| `city` | String(100) | no | |
| `state` | String(2) | no | |
| `zip_code` | String(10) | no | |
| `insurance_provider` | String(100) | yes | |
| `insurance_member_id` | String(50) | yes | |
| `preferred_language` | String(50) | yes | default "English" |
| `emergency_contact_name` | String(100) | yes | |
| `emergency_contact_phone` | String(10) | yes | |
| `created_at` | DateTime(tz) | no | default UTC now |
| `updated_at` | DateTime(tz) | no | onupdate UTC now |
| `deleted_at` | DateTime(tz) | yes | NULL = active (soft-delete marker) |

- CHECK constraint `sex IN (...)` keeps DB and app validation aligned.
- `phone_number` indexed for duplicate lookup.
- Soft-delete: all read queries filter `deleted_at IS NULL` by default.

## API Design (REST)

All under `/api/v1`, all responses in `{ "data": ..., "error": ... }`.

### POST /patients
- Body → `PatientCreate` (full server-side validation).
- `201` created record | `422` validation (see envelope below) | `400` bad JSON | `500` write failure.

### GET /patients
- Query: `last_name`, `date_of_birth`, `phone_number` (all optional, combinable).
- `200` list (newest first), non-deleted only.

### GET /patients/{patient_id}
- `200` record | `404` not found / soft-deleted.

### PUT /patients/{patient_id}
- Body → `PatientUpdate` (partial; provided fields validated).
- `200` updated | `404` missing | `422` validation.

### DELETE /patients/{patient_id}
- Soft-delete: set `deleted_at`. `200` `{patient_id, deleted_at}` | `404` missing.

### Error envelope

One canonical shape for every non-2xx REST response:

```json
{ "data": null, "error": { "code": "VALIDATION_ERROR", "message": "...", "fields": [ { "field": "date_of_birth", "message": "..." } ] } }
```

- `code`: SCREAMING_SNAKE machine code (`VALIDATION_ERROR`, `NOT_FOUND`, `BAD_REQUEST`, `INTERNAL_ERROR`).
- `message`: short human string.
- `fields`: **list** of per-field errors — present ONLY on `422`; omitted (absent key) otherwise.
  Named `fields` (not `details`) to avoid colliding with VLE's `details: dict` convention, since
  Pydantic validation naturally produces a *list* of field errors. `err()` accepts an optional
  `fields` list and omits the key when `None`.

**Where the 422 is produced (thin-router rule respected):** Pydantic raises
`pydantic.ValidationError` when `PatientCreate(**body)` / `PatientUpdate(**body)` is constructed.
The construction happens in the **router**, wrapped in a single `try/except ValidationError` that
calls `err("VALIDATION_ERROR", ..., fields=flatten(exc))`. This is request-shape handling (HTTP
concern), not business logic — the router does not make domain decisions, it only translates a
malformed request body into the 422 envelope. Domain errors (`PatientNotFound`) are still raised by
the service and rendered by the global `AppException` handler. Rendered by that global handler + an
unhandled-exception handler that logs full detail server-side and returns a sanitized `500`.

## Voice Webhook Design (`modules/voice`)

### Endpoint `POST /api/v1/voice/vapi`
Handles Vapi tool calls. Vapi's contract (confirmed from docs):

**Request** (relevant shape):
```json
{ "message": { "toolCalls": [
  { "id": "call_abc", "function": { "name": "save_patient", "arguments": { ...fields } } }
] } }
```
`arguments` may arrive as a dict or a JSON string — handle both.

**Response** (ALWAYS HTTP 200):
```json
{ "results": [ { "toolCallId": "call_abc", "result": "flat string" } ] }
```
- `result` / `error` must be **flat strings**; a given toolCallId uses one or the other, never both.
- Non-200 is ignored by Vapi → assistant says "no result".
- **Validation failures use `result`, NOT `error`** (deliberate). Per Vapi's docs, an `error`
  field makes Vapi speak its generic canned "Request Failed" message and ignore the content —
  which would prevent field-specific re-prompting. We want the agent to *read our specific
  message and re-ask the bad field*, so we return the field-named guidance as a normal `result`
  string. `error` is reserved for true infrastructure failures (bad secret, DB down) where a
  generic graceful apology is acceptable.

### Security
- Shared secret: Vapi sends a configured header (e.g. `x-vapi-secret`); `voice.security`
  compares it to `settings.VAPI_WEBHOOK_SECRET`. Missing/mismatch → reject (treated as a
  failed tool result). If no secret configured (local dev), the check is skipped.

### Tools
| Tool | Args | Behavior |
|------|------|----------|
| `save_patient` | all demographic fields | map → `PatientCreate`; on success return (as `result`) "Saved. Patient [First] [Last] registered."; on `ValidationError` return (as `result`, not `error`) a string naming the first bad field so the agent re-prompts |
| `lookup_patient` | `phone_number` | `patient.service.find_by_phone`; return (as `result`) match name+id or "no existing record" |

**Voice argument coercion:** optional string fields arriving as empty string or whitespace
(common from speech when the caller declines) are coerced to `None` before building
`PatientCreate`, so an unspoken email does not fail `EmailStr` validation. This coercion lives in
`voice.service` (adapter concern), keeping `patient.schemas` strict for the REST path.

### Flow
```
Vapi tool call → voice.router
  → voice.security.verify(header)                 # 200 + error string if bad
  → voice.service.handle_tool_call(name, args)
       save_patient → patient.service.create_patient(PatientCreate(**args))
       lookup_patient → patient.service.find_by_phone(args["phone_number"])
  → log final payload + outcome to stdout
  → return { results: [ { toolCallId, result|error } ] }  (HTTP 200)
```

## Service Layer Design (`modules/patient/service.py`)

```python
def create_patient(db, data: PatientCreate) -> Patient            # insert, commit
def get_patient(db, patient_id) -> Patient                        # raises PatientNotFound if missing/soft-deleted
def list_patients(db, *, last_name=None, date_of_birth=None,
                  phone_number=None) -> list[Patient]             # filters, non-deleted
def update_patient(db, patient_id, data: PatientUpdate) -> Patient # loads (or raises), partial, bump updated_at
def soft_delete_patient(db, patient_id) -> Patient                # loads (or raises), set deleted_at
def find_by_phone(db, phone_number) -> Patient | None             # duplicate detection (None = no match, not an error)
```
Service owns `commit`; CRUD only `add`/`flush` (VLE transaction model, sync variant).

**404 ownership (resolves the thin-router question):** `get/update/soft_delete` take a
`patient_id`, call `crud.get_active`, and raise `PatientNotFound` (a `NotFoundError` → 404) when
the row is absent or soft-deleted. The router does NOT null-check — it calls the service and
returns. `find_by_phone` is the one exception: a non-match is a normal `None` (duplicate detection,
not an error), consumed by `voice.service`.

## CRUD Layer Design (`modules/patient/crud.py`)

```python
class CRUDPatient(CRUDBase[Patient, None, None]):
    def get_active(db, patient_id) -> Patient | None               # deleted_at IS NULL
    def list_filtered(db, *, last_name, date_of_birth, phone) -> list[Patient]
    def get_by_phone(db, phone_digits) -> Patient | None
```
Non-trivial queries are named methods (not `CRUDBase` kwargs soup), per VLE 7.1.

## Validation Design (`modules/patient/schemas.py`)

Reusable validators (shared by create + update):
- `normalize_phone`: strip non-digits, drop leading `1` on 11-digit, require 10 digits,
  area code not starting 0/1.
- `normalize_name`: 1–50 chars, regex letters/space/hyphen/apostrophe.
- `validate_dob`: parse MM/DD/YYYY or ISO, reject future and absurd (<1900), store ISO.
- `sex`: title-case + aliases (M/F) → enum.
- `state`: upper, membership in `US_STATES`.
- `zip_code`: `^\d{5}(-\d{4})?$`.
- `email`: Pydantic `EmailStr`.

`PatientCreate` enforces all required fields; `PatientUpdate` makes all optional and
validates only those present (via `model_validator(mode="after")`).

## Vapi System Prompt (prompt engineering — documented in `vapi/system-prompt.md`)

Key design points (full text + rationale comments live in that file):
- Role framing: warm, efficient patient intake coordinator.
- Ordered flow: greet → (bonus) phone-first duplicate check → required fields → offer
  optional groups → read-back confirmation → `save_patient` → brief sign-off.
- Explicit correction/spelling handling and "start over" handling.
- Tool-use rules: never claim saved until `save_patient` returns success; on an error
  result, re-prompt only the named field.
- Spoken-input normalization guidance (spell names, confirm DOB as month/day/year, read
  phone back in groups).

## Error Responses

| Scenario | REST HTTP | Code | Voice behavior |
|----------|-----------|------|----------------|
| Validation failure | 422 | `VALIDATION_ERROR` | tool **`result`** names the bad field → agent re-prompts (NOT `error`, see rationale above) |
| Patient not found | 404 | `NOT_FOUND` | n/a |
| Bad JSON body | 400 | `BAD_REQUEST` | n/a |
| Bad / missing webhook secret | — | — | tool `error` "I can't save that right now." (HTTP 200) |
| DB write failure | 500 | `INTERNAL_ERROR` | tool `error` graceful spoken message (HTTP 200) |

## Testing Strategy

- `conftest.py`: `TestClient` with `get_db` overridden to a fresh in-memory SQLite per test.
- API: create→read→update→soft-delete lifecycle; filters; 404s; 422 bodies.
- Validation: table-driven cases for DOB (future/malformed), phone (3-digit/11-digit),
  state, zip, sex, name.
- Voice: post a Vapi-shaped tool call for `save_patient` (valid + invalid) and
  `lookup_patient`; assert the `{results:[{toolCallId,result}]}` contract and HTTP 200.

## Deployment

- **Render** (free web service) or **Fly.io**; `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- `DATABASE_URL` env (defaults to local SQLite file). On ephemeral FS, use a mounted
  disk or Postgres — documented trade-off in README.
- `VAPI_WEBHOOK_SECRET` env matches the secret header configured on the Vapi tool.
- Vapi assistant `server.url` points at `https://<deployed-host>/api/v1/voice/vapi`.
