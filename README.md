<div align="center">

# 🎙️ Voice AI Patient Registration

**Call a phone number, talk naturally to an AI intake coordinator, and get registered as a patient — the data lands in a real database, queryable over a REST API and visible on a live dashboard.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)](https://www.sqlalchemy.org/)
[![Vapi](https://img.shields.io/badge/Voice-Vapi-5B21B6)](https://vapi.ai/)
[![uv](https://img.shields.io/badge/packaged%20with-uv-DE5FE9)](https://docs.astral.sh/uv/)
[![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)]()
[![Checks](https://img.shields.io/badge/ruff%20%2B%20mypy-clean-brightgreen)]()

</div>

---

## Overview

A caller dials a phone number and has a natural, spoken conversation with **"Avery,"** an AI patient-intake coordinator. Avery collects the standard US demographic dataset, reads it back for confirmation, handles corrections and spelling, and persists the record — then confirms and ends the call.

The voice layer is [**Vapi**](https://vapi.ai) (phone number, speech-to-text, text-to-speech, and the LLM turn-taking loop). Vapi calls **this FastAPI backend** over an authenticated webhook as **function tools** (`save_patient`, `lookup_patient`). The same records are fully manageable through a versioned **REST API** and viewable on a server-rendered **dashboard**.

**All validation is enforced server-side** — a 3-digit phone number or a future date of birth is rejected whether it arrives by voice or by API. The voice agent is never trusted as the source of truth.

### Live demo

| | |
|---|---|
| ☎️ **Phone number** | `+1 (864) 625-5296` |
| 🌐 **API base URL** | `<set after deploy>` · locally `http://localhost:8000/api/v1` |
| 📊 **Dashboard** | `<set after deploy>` · locally `http://localhost:8000/` |
| 📘 **Interactive API docs** | `/docs` (Swagger UI) |

> The phone number is bound to a live Vapi assistant whose webhook points at the deployed backend. During local development the webhook is exposed via ngrok.

---

## Table of contents

- [Architecture](#architecture)
- [Tech stack & rationale](#tech-stack--rationale)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [REST API reference](#rest-api-reference)
- [Patient data model](#patient-data-model)
- [Voice agent (Vapi)](#voice-agent-vapi)
- [Deployment](#deployment)
- [Testing & quality](#testing--quality)
- [Security](#security)
- [Observability](#observability)
- [Known limitations & trade-offs](#known-limitations--trade-offs)
- [Roadmap / next steps](#roadmap--next-steps)
- [Project layout](#project-layout)

---

## Architecture

Three cooperating pieces — the Vapi voice front end, this FastAPI backend, and a SQLite database:

```
            Caller (phone)
                 │  speech
                 ▼
      ┌────────────────────────┐
      │     Vapi Assistant      │  owns: phone number, STT, TTS, LLM loop,
      │       ("Avery")         │  system prompt, tool definitions
      └───────────┬────────────┘
                  │  HTTPS tool calls  (save_patient / lookup_patient)
                  │  authenticated with x-vapi-secret
                  ▼
      ┌────────────────────────┐
      │     FastAPI backend     │
      │  /api/v1/voice/vapi     │  ← Vapi webhook           (voice module)
      │  /api/v1/patients       │  ← REST CRUD              (patient module)
      │  /                      │  ← Jinja + Tailwind UI    (dashboard module)
      │  /health  /docs         │
      └───────────┬────────────┘
                  │  SQLAlchemy (sync Session)
                  ▼
      ┌────────────────────────┐
      │   SQLite (patients.db)  │  persistent on disk
      └────────────────────────┘
```

### Design: a modular monolith (vertical slices)

The backend follows a **domain-first modular-monolith** pattern (adapted from a production FastAPI codebase). Each feature is a self-contained slice under `app/modules/`, and every slice uses the same strict layering:

```
router → service → crud → models        (+ schemas, constants, exceptions)
```

- **router** — thin HTTP layer: parse request, call one service function, return. No business logic, no queries.
- **service** — the single source of truth for business rules (validation orchestration, soft-delete, duplicate detection, 404 ownership). Shared by both the REST API and the voice webhook.
- **crud** — pure data access over the ORM models.
- **models / schemas** — SQLAlchemy tables / Pydantic request-response contracts.

Cross-module calls go **through services only** (`voice` and `dashboard` call `patient.service`, never its crud or models). Shared infrastructure lives in `app/core` (config, db, logging, exceptions) and `app/common` (generic CRUD base, response-envelope helpers). A single router registry (`app/router/endpoints.py`) applies the `/api/v1` prefix once.

---

## Tech stack & rationale

| Layer | Choice | Why |
|-------|--------|-----|
| **API** | FastAPI + Pydantic v2 | Declarative, strong server-side validation in one place; auto-generated OpenAPI docs at `/docs`; fast. |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero-config, real on-disk persistence (survives restarts, spans calls). Engine-agnostic — point `DATABASE_URL` at Postgres and nothing else changes. |
| **Concurrency** | Synchronous SQLAlchemy | SQLite + low expected concurrency makes sync simpler and avoids an async driver, with identical layering rules. |
| **Voice** | Vapi | Fastest path to a clean, callable US number; abstracts STT/TTS/LLM turn-taking; the backend only implements two webhook tools. |
| **LLM** | Google `gemini-2.5-flash` (via Vapi) | Cheapest high-quality option with low latency and reliable function calling — critical for the two tools. Swappable in the assistant config. |
| **UI** | Jinja2 + Tailwind (CDN) | Server-rendered dashboard with no build step / Node toolchain. |
| **Tooling** | uv · ruff · mypy · pytest | Reproducible installs, linting, type-checking, and tests. |

---

## Quick start

**Prerequisites:** Python 3.11+ · [uv](https://docs.astral.sh/uv/) · (for voice) a [Vapi](https://vapi.ai) account.

```bash
# 1. Install dependencies into a managed virtualenv
uv sync

# 2. Create your local env file (then edit values as needed)
cp .env.example .env

# 3. Run the API with autoreload
uv run uvicorn app.main:app --reload
```

Then open:

| URL | What |
|-----|------|
| http://localhost:8000/ | Dashboard (patient list + search + detail) |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/health | Readiness probe |

Common tasks:

```bash
uv run python scripts/seed.py     # seed a couple of demo patients (idempotent)
uv run pytest                     # run the test suite
uv run ruff check .               # lint
uv run mypy app/                  # type-check
```

---

## Environment variables

All configuration comes from environment variables (via `.env` locally). The backend reads only **Section 1**; the rest are used by the Vapi tooling.

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | no (default) | SQLAlchemy URL. Default `sqlite:///./patients.db`. Point at Postgres in production. |
| `VAPI_WEBHOOK_SECRET` | recommended | Shared secret the webhook checks against the `x-vapi-secret` header Vapi sends. Blank disables the check (local only). |
| `HOST` / `PORT` | no (default) | Bind host/port. Hosts inject `PORT` automatically. |
| `LOG_LEVEL` | no (default) | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `VAPI_SERVER_URL` | voice only | Public HTTPS URL of the webhook (`.../api/v1/voice/vapi`); used by the Vapi build script. |
| `VAPI_PRIVATE_API_KEY` | voice only | Vapi private key — used only by the one-off push scripts, never by the server. |
| `VAPI_ASSISTANT_ID` / `VAPI_TOOL_IDS` | voice only | Recorded by the push scripts so re-runs update instead of duplicating. |

> `.env` is git-ignored; only `.env.example` is committed.

---

## REST API reference

Base path **`/api/v1`**. Every response uses the envelope `{ "data": ..., "error": ... }`. On success `error` is `null`; on failure `data` is `null` and `error` is `{ code, message, fields? }` (`fields` only on `422`).

| Method & path | Description |
|---------------|-------------|
| `GET /api/v1/patients` | List active patients, newest first. Optional filters: `last_name`, `date_of_birth`, `phone_number`. |
| `GET /api/v1/patients/{id}` | Fetch one patient by UUID. `404` if missing or soft-deleted. |
| `POST /api/v1/patients` | Create a patient → `201` with the created record. |
| `PUT /api/v1/patients/{id}` | Partial update; only provided fields change and are validated. |
| `DELETE /api/v1/patients/{id}` | **Soft-delete** (sets `deleted_at`; row retained, excluded from reads). |

**Status codes:** `200` · `201` · `400` (bad JSON) · `404` (not found / soft-deleted) · `422` (validation) · `500` (sanitized; detail logged server-side).

<details>
<summary><b>Example — create a patient</b></summary>

```bash
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane", "last_name": "Doe",
    "date_of_birth": "03/14/1990", "sex": "Female",
    "phone_number": "(415) 555-0142",
    "address_line_1": "1 Market St", "city": "San Francisco",
    "state": "ca", "zip_code": "94105", "email": "jane.doe@example.com"
  }'
```

```json
{
  "data": {
    "patient_id": "f3c1b7a2-9d4e-4a1b-8c2f-0b9e6d5a1c23",
    "first_name": "Jane", "last_name": "Doe",
    "date_of_birth": "1990-03-14", "sex": "Female",
    "phone_number": "4155550142", "state": "CA",
    "created_at": "2026-10-10T12:00:00+00:00",
    "updated_at": "2026-10-10T12:00:00+00:00",
    "deleted_at": null
  },
  "error": null
}
```

Note the server-side normalization: phone → 10 digits, `state` upper-cased, DOB → ISO `YYYY-MM-DD`.
</details>

<details>
<summary><b>Example — validation error (422)</b></summary>

```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "fields": [
      { "field": "phone_number", "message": "must be a valid US 10-digit phone number" },
      { "field": "date_of_birth", "message": "date_of_birth cannot be in the future" }
    ]
  }
}
```
</details>

---

## Patient data model

Validation rules live in `app/modules/patient/schemas.py` and apply identically to the REST API and the voice webhook.

| Field | Req | Rules |
|-------|-----|-------|
| `first_name` / `last_name` | ✅ | 1–50 chars; letters, space, hyphen, apostrophe. |
| `date_of_birth` | ✅ | `MM/DD/YYYY` or ISO; not in the future; stored as `YYYY-MM-DD`. |
| `sex` | ✅ | `Male` · `Female` · `Other` · `Decline to Answer`. |
| `phone_number` | ✅ | US 10-digit; formatting stripped, leading `1` dropped. |
| `address_line_1` | ✅ | non-empty |
| `city` | ✅ | 1–100 chars |
| `state` | ✅ | 2-letter US abbreviation (upper-cased) |
| `zip_code` | ✅ | 5-digit or ZIP+4 |
| `email` | — | valid email if provided |
| `address_line_2` · `insurance_provider` · `insurance_member_id` · `preferred_language` · `emergency_contact_name` · `emergency_contact_phone` | — | optional |

**Auto-managed:** `patient_id` (UUID), `created_at`, `updated_at`, `deleted_at` (soft-delete marker).

---

## Voice agent (Vapi)

The voice agent is managed **as code** in [`vapi/`](vapi/) and deployed to Vapi via the API — see [`vapi/README.md`](vapi/README.md) for the full workflow. In short:

```bash
# .env must set VAPI_WEBHOOK_SECRET, VAPI_SERVER_URL, VAPI_PRIVATE_API_KEY
uv run python vapi/build_assistant.py   # compose assistant.json (prompt + template + env)
uv run python vapi/push_assistant.py    # create/update the Vapi assistant
uv run python vapi/push_tools.py        # register the two tools + attach by id
```

- **System prompt** — single source of truth in [`vapi/system-prompt.md`](vapi/system-prompt.md) (with documented rationale), injected into the assistant at build time so it never drifts.
- **Tools** — `save_patient` and `lookup_patient`, each pointing at `/api/v1/voice/vapi` and carrying the shared secret.
- **Turn-taking** — tuned `startSpeakingPlan` (smart endpointing + wait) and `stopSpeakingPlan` so the agent lets callers finish and ignores brief acknowledgements.
- **Validation feedback loop** — on a bad field the webhook returns a spoken `result` naming the field so the agent re-prompts just that field; infrastructure failures return an `error` and the agent apologizes.

---

## Deployment

The repo ships a Render blueprint (`render.yaml`), a `Procfile`, and `runtime.txt`.

```
build:  uv sync
start:  uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
health: /health
```

Set `VAPI_WEBHOOK_SECRET` (and, for durable storage, `DATABASE_URL`) in the host's dashboard, then point the Vapi assistant's server URL at `https://<your-host>/api/v1/voice/vapi` and re-push.

> **SQLite on an ephemeral filesystem:** on free tiers the file may not survive redeploys — attach a persistent disk or set `DATABASE_URL` to Postgres. For local webhook exposure without deploying, use `ngrok http 8000`.

---

## Testing & quality

```bash
uv run pytest        # 36 tests: API CRUD, validation table, voice contract, dashboard, Vapi config
uv run ruff check .  # lint (clean)
uv run mypy app/     # type-check (clean)
```

Tests use a disposable temp-file SQLite database per run, so the real `patients.db` is never touched. Coverage spans the REST lifecycle, field-level validation (future DOB, 3-digit phone, bad state/zip/sex), the Vapi webhook contract (`{results:[{toolCallId, result}]}`, always HTTP 200), the dashboard pages, and the Vapi config integrity.

---

## Security

- **No secrets in source** — all secrets come from environment variables; `.env` and generated Vapi config are git-ignored.
- **Webhook authentication** — the Vapi webhook verifies a shared secret (`x-vapi-secret`) in constant time; mismatches are rejected and nothing is written.
- **Server-side validation** — the backend re-validates every field; the voice agent is never trusted.
- **Error hygiene** — unhandled errors are logged server-side and returned to clients as a sanitized `500`.
- **No real PHI** — a demonstration system built with fake data; not HIPAA-compliant.

---

## Observability

Logging goes to stdout at `LOG_LEVEL`. Each successful voice registration logs the final collected payload (`"Patient registered via voice: {...}"`); REST writes log the affected `patient_id`; `/health` reports database reachability (503 if down).

---

## Known limitations & trade-offs

- **SQLite on ephemeral hosting** loses data across redeploys unless a disk/Postgres is used.
- **Single-tenant, no auth on the REST API** — the only auth is the voice webhook secret.
- **Vapi free-trial minutes** limit call time.
- **Not HIPAA-compliant** — fake data only.

---

## Roadmap / next steps

- Postgres + Alembic migrations for durable, versioned storage.
- Authentication / RBAC on the REST API.
- Bonus flows: appointment scheduling, multi-language (Spanish), call-transcript storage.
- Richer dashboard: pagination, edit/delete actions, per-call history.

---

## Project layout

```
voice-patient-agent/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, handlers, /health
│   ├── core/                   # config, database, logging, exceptions
│   ├── common/                 # CRUD base, {data,error} envelope helpers
│   ├── router/endpoints.py     # /api/v1 registry
│   └── modules/
│       ├── patient/            # domain: models, schemas, crud, service, router
│       ├── voice/              # Vapi webhook adapter → patient.service
│       └── dashboard/          # Jinja + Tailwind UI
├── vapi/                       # voice agent as code (prompt, template, build/push scripts)
├── tests/                      # pytest suite
├── scripts/seed.py             # demo data
├── render.yaml · Procfile      # deployment
└── pyproject.toml              # deps + ruff/mypy/pytest config (uv)
```

---

<div align="center">
<sub>Built as a take-home assessment — a working end-to-end system over an over-engineered one.</sub>
</div>
