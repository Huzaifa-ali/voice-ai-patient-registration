# Voice AI Patient Registration — Requirements

> Challenge: CareCloud Voice AI Agent Take-Home Assessment
> Reference: `docs/challenge-brief.md` (original PDF transcription)
> Architecture: adapted from Mishkat-labs VLE modular monolith (FastAPI vertical slices)

## Context

Build a voice-based AI agent reachable on a real US phone number that collects
standard US patient demographics through natural conversation, persists them to a
durable database, and exposes them through a REST API. The system must be live and
callable at review time, and data registered on one call must still exist on the
next call and via the API.

The system has three cooperating pieces:
1. **Voice front-end** — a Vapi assistant (owns the phone number, STT, TTS, and the
   LLM conversation loop). It calls our backend as a *tool* to read/write patients.
2. **Backend** — a FastAPI modular monolith owning the data model, validation, the
   patient service layer, the public REST API, the Vapi webhook, and a dashboard.
3. **Database** — SQLite via SQLAlchemy (persistent file on disk).

The backend is the graded engineering artifact; Vapi is configuration that rides on
top of it. The same service layer backs both the REST API and the voice webhook, so
validation and persistence rules live in exactly one place.

## Functional Requirements

### FR-1: Create a patient (REST)

WHEN a client POSTs a patient payload to `POST /api/v1/patients`,
THE system SHALL:
1. Validate every field server-side against the data model (FR-7), independent of
   any validation the voice agent performed.
2. Reject invalid payloads with `422` and a per-field error list — no row written.
3. On success, generate `patient_id` (UUID), `created_at`, and `updated_at`, insert
   the row, and return `201` with the created record in the `{ data, error }` envelope.

### FR-2: Retrieve patients (REST)

1. WHEN a client calls `GET /api/v1/patients`, THE system SHALL return all
   non-deleted patients, newest first.
2. THE system SHALL support optional filters `?last_name=`, `?date_of_birth=`, and
   `?phone_number=`, combinable, matching on normalized values.
3. WHEN a client calls `GET /api/v1/patients/{patient_id}` for an existing,
   non-deleted patient, THE system SHALL return it with `200`.
4. WHEN the id does not exist or is soft-deleted, THE system SHALL return `404`.

### FR-3: Update a patient (REST)

WHEN a client calls `PUT /api/v1/patients/{patient_id}` with a partial payload,
THE system SHALL:
1. Return `404` if the patient does not exist or is soft-deleted.
2. Validate only the provided fields (same rules as FR-7); reject with `422` on failure.
3. Apply the changes, bump `updated_at`, and return `200` with the updated record.

### FR-4: Soft-delete a patient (REST)

WHEN a client calls `DELETE /api/v1/patients/{patient_id}`,
THE system SHALL set `deleted_at` (never hard-delete), exclude the row from future
reads, and return `200`. A delete on a missing/already-deleted id returns `404`.

### FR-5: Voice tool — save patient

WHEN the Vapi assistant invokes the `save_patient` tool after the caller confirms
their information,
THE system SHALL:
1. Authenticate the webhook via a shared secret header; on a missing/mismatched secret,
   return (HTTP 200) a tool `error` string that makes the agent apologize gracefully,
   and do NOT write any row. (HTTP 200 is required by Vapi's contract even for failures;
   the secret check still fully gates persistence.)
2. Validate the collected fields through the SAME service/validation path as FR-1.
3. On success, persist the patient and return a Vapi tool result (HTTP 200) whose
   `result` string tells the agent the save succeeded and includes the patient's name.
4. On validation failure, return (HTTP 200) a tool **`result`** string (not `error`) naming the
   invalid field so the agent can re-prompt the caller specifically for that field. (`error` would
   trigger Vapi's generic canned failure message and suppress field-specific re-prompting.)
5. Log the final collected patient payload to stdout (observability).

### FR-6: Voice tool — duplicate lookup (bonus)

WHEN the Vapi assistant invokes the `lookup_patient` tool with a phone number,
THE system SHALL return (HTTP 200) a tool result indicating whether an existing
non-deleted patient matches that number, and if so the patient's first/last name and
id, so the agent can offer to update instead of create.

### FR-7: Patient demographic data model + validation

THE system SHALL enforce the following fields and rules server-side:

| Field | Req | Rule |
|-------|-----|------|
| `first_name` | Yes | 1–50 chars; letters, hyphen, apostrophe, space |
| `last_name` | Yes | 1–50 chars; letters, hyphen, apostrophe, space |
| `date_of_birth` | Yes | valid date, not in future; accept MM/DD/YYYY or YYYY-MM-DD; store ISO |
| `sex` | Yes | one of: Male, Female, Other, Decline to Answer |
| `phone_number` | Yes | valid US 10-digit (strip formatting; drop leading country code 1) |
| `email` | No | valid email format |
| `address_line_1` | Yes | non-empty street address |
| `address_line_2` | No | apt/suite/unit |
| `city` | Yes | 1–100 chars |
| `state` | Yes | valid 2-letter US abbreviation (50 states + DC + territories) |
| `zip_code` | Yes | 5-digit or ZIP+4 |
| `insurance_provider` | No | free text |
| `insurance_member_id` | No | alphanumeric |
| `preferred_language` | No | default "English" |
| `emergency_contact_name` | No | full name |
| `emergency_contact_phone` | No | valid US 10-digit |
| `patient_id` | Auto | UUID |
| `created_at` | Auto | UTC timestamp at creation |
| `updated_at` | Auto | UTC timestamp on modification |
| `deleted_at` | Auto | UTC timestamp on soft-delete (NULL = active) |

### FR-8: Conversational behavior (Vapi system prompt)

The assistant's system prompt SHALL direct it to:
1. Greet as a patient intake coordinator and speak naturally (not a rigid IVR).
2. Collect required fields first; then offer optional groups (insurance, emergency
   contact, preferred language) and let the caller opt in.
3. Handle corrections and spelling ("D-A-V-I-S, not D-A-V-I-E-S") and out-of-order
   answers.
4. Read back all collected fields and ask for confirmation before calling `save_patient`.
5. On a tool error naming a field, re-prompt specifically for that field.
6. On success, give a brief confirmation ("You're all set, [First Name].") and end.
7. (Bonus) Call `lookup_patient` with the phone number first; if a match exists, offer
   to update instead of create.

### FR-9: Dashboard (bonus)

THE system SHALL serve a read-only web page at `GET /` that lists registered
(non-deleted) patients from the database for demonstration.

### FR-10: Health check

THE system SHALL expose `GET /health` returning `200` with a JSON body when the
database is reachable, `503` otherwise (deployment readiness probe).

## Non-Functional Requirements

### NFR-1: Persistence
Data MUST survive server restarts. A patient registered on call 1 MUST be retrievable
on call 2 and via the API. SQLite file persists to disk; on ephemeral hosts a mounted
volume (or Postgres via `DATABASE_URL`) is used — documented as a trade-off.

### NFR-2: Security
- No secrets in source. DB URL and the Vapi webhook secret come from environment variables.
- The webhook validates a shared secret header; mismatches are rejected.
- All inputs validated and sanitized server-side; client/vendor error text is never
  echoed to API consumers (sanitized envelope only).

### NFR-3: Observability
Every tool call logs the final collected patient payload (and outcome) to stdout.
REST writes log the affected `patient_id`.

### NFR-4: Code quality & architecture
- Follow the VLE modular-slice layering: `router → service → crud → models`, with
  `schemas`, `constants`, `exceptions` per module.
- Consistent response envelope `{ "data": ..., "error": ... }` on all REST routes.
- Proper status codes: 200, 201, 400, 404, 422, 500.
- `ruff` + `mypy` clean.

### NFR-5: Resilience / edge cases
- Invalid DOB (future / malformed) → specific `422` field error → agent re-prompts.
- DB write failure → `500` with sanitized message (REST) / graceful spoken error (voice),
  never silence.
- Caller restarts mid-conversation → handled by the assistant's prompt (fresh collection).
- Dropped call before confirmation → no partial row written (save only on confirm).

## Out of Scope
- Real PHI / HIPAA compliance (explicitly excluded by the brief — use fake data).
- Authn/authz on the REST API beyond the webhook secret (single-tenant demo).
- Appointment scheduling and multi-language (noted as optional bonuses; prompt-level only).
- Building STT/TTS (delegated to Vapi).

## Trade-offs (documented, intentional)
- **SQLite over Postgres**: zero-config, real persistence, matches the brief's
  "smart shortcut" guidance. Swappable via `DATABASE_URL`.
- **Vapi over raw Twilio**: fastest path to a clean, callable number without a trial
  banner; keeps the graded logic in our own backend. The backend is telephony-agnostic
  — a Twilio webhook adapter could be added without touching the service layer.
- **No multi-tenancy / RBAC**: the VLE patterns include `school_id` + Cognito RBAC;
  this challenge is single-tenant, so those layers are intentionally omitted while the
  module/layer structure is preserved.
