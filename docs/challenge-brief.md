# Voice AI Agent — Patient Registration (Challenge Brief)

> Transcribed from the CareCloud take-home assessment PDF. Reference copy for the spec.
> Role: Voice AI / Conversational AI Engineer. Time limit: 3 hours. Difficulty: Intermediate–Advanced.

## Overview

Build a voice-based AI agent reachable via a real phone number that collects standard
US patient demographic information through natural conversation, persists that data to a
database, and exposes it through a lightweight web service. When the reviewer calls the
number, they should be able to speak naturally to register a new patient — and when they
call back, data from the previous call must still be there.

Evaluates integration of multiple systems (telephony, LLM, database, API) into a
cohesive, production-oriented solution under time pressure.

## System Architecture

A caller dials a phone number. A voice AI agent answers, greets, and conversationally
collects all required demographics. On completion the agent confirms the information back,
saves the record to a persistent database, and ends the call. A companion REST API allows
querying and viewing stored patient records.

```
Phone Call (Caller) ↔ Voice AI Agent (LLM + Telephony) ↔ Database (Persistent)
                                                              ↓
                                                     Web Service (REST API)
```

## Functional Requirements

### 1. Telephony & Voice Agent
- **Phone Number:** provision a real, dialable US number (Twilio, Vonage, Vapi, Retell, Bland.ai).
- **Voice Interaction:** natural conversational flow — not a rigid IVR menu.
- **LLM-Powered:** any LLM; must understand varied phrasing, ask clarifying questions, handle corrections.
- **Confirmation:** before saving, read back all collected info and ask to confirm/correct.
- **Error Handling:** on invalid data (3-digit phone, future DOB) re-prompt specifically for that field.
- **Call Completion:** brief confirmation ("You're all set, [First Name].") then end gracefully.

### 2. Patient Demographic Data Model

| Field | Type | Validation | Req |
|-------|------|-----------|-----|
| first_name | String | 1–50 chars, alpha + hyphen/apostrophe | Yes |
| last_name | String | 1–50 chars, alpha + hyphen/apostrophe | Yes |
| date_of_birth | Date | valid, not future, MM/DD/YYYY | Yes |
| sex | Enum | Male, Female, Other, Decline to Answer | Yes |
| phone_number | String | valid US 10-digit | Yes |
| email | String | valid email | No |
| address_line_1 | String | street address | Yes |
| address_line_2 | String | apt/suite/unit | No |
| city | String | 1–100 chars | Yes |
| state | String | valid 2-letter US abbreviation | Yes |
| zip_code | String | 5-digit or ZIP+4 | Yes |
| insurance_provider | String | name of insurer | No |
| insurance_member_id | String | alphanumeric | No |
| preferred_language | String | default English | No |
| emergency_contact_name | String | full name | No |
| emergency_contact_phone | String | valid US 10-digit | No |
| created_at | Timestamp | auto UTC | Auto |
| updated_at | Timestamp | auto UTC | Auto |
| patient_id | UUID | auto | Auto |

Conversational note: the agent does NOT need every optional field each call. Collect
required fields, then offer insurance / emergency contact / preferred language and let the
caller opt in.

### 3. Persistent Database
- Any relational or document DB (PostgreSQL, SQLite, MySQL, MongoDB...).
- Data must survive restarts. Register on call 1 → exists when queried on call 2.
- Schema enforces the data model with proper types and constraints.
- Optionally seed 1–2 demo records.

### 4. Web Service (REST API)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /patients | List all; optional `?last_name=`, `?date_of_birth=`, `?phone_number=` |
| GET | /patients/:id | Retrieve one by patient_id (UUID) |
| POST | /patients | Create; returns created record with patient_id |
| PUT | /patients/:id | Update existing; partial updates allowed |
| DELETE | /patients/:id | Soft-delete (set deleted_at; do not hard-delete) |

API standards:
- Proper HTTP status codes (200, 201, 400, 404, 422, 500).
- Validate all inputs server-side (do not rely solely on the voice agent).
- JSON responses with a consistent envelope: `{ "data": {...}, "error": null }`.

### 5. Voice Agent ↔ Database Integration
- On caller confirmation, agent triggers `POST /patients` (or equivalent DB write).
- Agent relays outcome: success confirmation or graceful error if the write fails.
- **Bonus:** if the caller's phone matches an existing patient, recognize it and offer to update.

## Non-Functional Requirements
- **Deployment:** running and callable at review time (Railway, Render, Fly.io, Replit, ngrok, AWS, GCP...).
- **Code Quality:** clean, readable, intentional structure.
- **README:** setup, architecture, tech-stack justification, env vars, known limitations/trade-offs.
- **Security:** no hardcoded keys; env vars; basic input sanitization.
- **Observability:** log agent conversations (at minimum the final collected payload) to stdout/log.

## Evaluation Criteria (20% each)
1. Working System — end to end; call completes a registration; data persisted & retrievable; second call without data loss.
2. Conversational Quality — natural, handles corrections, confirms before saving, handles interruptions/out-of-order.
3. Technical Architecture — separation of concerns (telephony vs LLM vs data vs API); good schema; RESTful validated endpoints; thoughtful documented prompt engineering.
4. Code Quality & Documentation — organized, readable; complete README; documented trade-offs; LLM system message included and commented.
5. Edge Cases & Resilience — invalid DOB; dropped connection; failed DB write (error not silence); caller wants to start over.

## Bonus Challenges (not required)
- Duplicate detection (returning callers by phone).
- Appointment scheduling after registration (mock data fine).
- Multi-language support ("Hablo español" → switch to Spanish).
- Call recording/transcript stored and linked to the patient.
- Dashboard web UI listing registered patients.
- Automated tests for the API layer.

## Submission
1. Repository (public or private with reviewer access).
2. Live phone number and API base URL in the README.
3. Submit within 3 hours; partial working submissions valued over ambitious non-functional ones.
4. Send: repository URL, phone number, API base URL, any credentials/notes, dashboard.

## FAQ highlights
- Voice AI platforms (Vapi/Retell/etc.) are encouraged — the goal is integration & system design, not building STT/TTS.
- No HIPAA/real PHI — use fake data.
- If no number can be provisioned, document what was tried and provide a working local setup.
- AI coding assistants permitted; understanding and explaining decisions is what matters.
- If out of time, submit what exists and document "Next Steps".
