# Vapi voice agent — configuration (config as code)

This folder is the **voice agent's configuration, managed as code** — the pattern Vapi
recommends in its [GitOps guide](https://github.com/VapiAI/gitops) and
[enterprise environments guide](https://docs.vapi.ai/documentation/best-practices/enterprise-environments-dev-uat-prod).
The assistant's prompt, model, voice, and tool contracts live in version-controlled
files (reviewable in a PR, diffable, rollback-able) instead of only in the dashboard.

It is **not application code** — the FastAPI backend never imports it. These files are
what you load into Vapi to create the assistant that calls the backend's webhook.

## Files

| File | Role | Edit it? |
|------|------|----------|
| `system-prompt.md` | **Single source of truth for the system prompt** (between the `PROMPT:START/END` markers) plus the prompt-engineering rationale. | ✅ Edit the prompt here |
| `assistant.template.json` | Everything except the prompt: model, voice, transcriber, and the two tool schemas (`save_patient`, `lookup_patient`). Server URL + secret are **placeholders** here (never real values). | ✅ Edit model/voice/tools here |
| `build_assistant.py` | Injects the prompt (from `system-prompt.md`) and the real server URL + secret (from env vars) into the template, writing `assistant.json`. Prevents prompt drift and keeps secrets out of git. | — (run it) |
| `assistant.json` | **Generated, gitignored** deployable config (prompt + template + live secret/URL). This is what you push to Vapi. | ❌ Do not hand-edit — it's rebuilt and not committed |

> **Why a build step + env injection?** Vapi's guidance keeps the prompt as a standalone
> file (so it isn't copy-pasted and left to drift) and keeps secrets out of git. Here the
> prompt has one home (`system-prompt.md`); the webhook secret and server URL come from
> `.env` (`VAPI_WEBHOOK_SECRET`, `VAPI_SERVER_URL`); and `assistant.json` is derived from
> all of them at build time and never committed.

## Rebuild the config after editing the prompt, template, or env

```bash
# .env must set VAPI_WEBHOOK_SECRET and VAPI_SERVER_URL (your public /api/v1/voice/vapi URL)
uv run python vapi/build_assistant.py          # regenerate vapi/assistant.json
uv run python vapi/build_assistant.py --check   # CI gate: template + prompt compose cleanly
```

## Deploy to Vapi

You can do this through the dashboard (fastest for a demo) or the API.

### Option A — Dashboard (recommended for this project)

1. Create an assistant in the [Vapi dashboard](https://dashboard.vapi.ai).
2. Import / paste the contents of `assistant.json`.
3. Replace the placeholders:
   - `server.url` **and** each tool's `server.url` → `https://<your-deployed-host>/api/v1/voice/vapi`
   - `server.secret` → the **same** value as the backend's `VAPI_WEBHOOK_SECRET` env var
   - `voice.voiceId` → a real voice ID from your TTS provider
4. In **Provider Keys**, add your LLM key (Groq by default — the model is
   `llama-3.3-70b-versatile`; swap to OpenAI/Gemini/OpenRouter if you prefer).
5. Buy / attach a phone number and point it at this assistant.
6. Call the number and register a patient.

### Option B — API (programmatic)

```bash
# Private API key from dashboard.vapi.ai/org/api-keys (keep it out of git)
curl -X POST https://api.vapi.ai/assistant \
  -H "Authorization: Bearer $VAPI_PRIVATE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @vapi/assistant.json
```

## The two tools (the contract with the backend)

Both tools POST to `/api/v1/voice/vapi` with the `x-vapi-secret` header:

- **`lookup_patient(phone_number)`** — called early to detect returning callers (duplicate detection).
- **`save_patient(...all fields...)`** — validates + persists after the caller confirms.
  Validation feedback comes back as a spoken `result` string so the agent re-prompts the
  specific bad field; true failures come back as an `error`. The webhook always returns HTTP 200.

The tool JSON schemas here must match the fields the backend validates
(`app/modules/patient/schemas.py`). The backend is the source of validation truth.

## Secrets

No secrets live in this folder — only placeholders. The LLM API key goes in the **Vapi
dashboard**, not the backend. The shared webhook secret lives in the backend's `.env`
(`VAPI_WEBHOOK_SECRET`) and is pasted into the Vapi tool config as `server.secret`.

## Scaling up (production path)

For real multi-environment operation (dev → staging → prod), Vapi's
[GitOps repo](https://github.com/VapiAI/gitops) promotes the same files across orgs with
per-environment credentials, PR simulation checks, and rollback. That is intentionally
**out of scope** for this single-org demo, but this folder's "config as code" layout is
already consistent with it.
