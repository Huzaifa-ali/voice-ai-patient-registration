# Deployment & Live Demo

This document explains how the system is hosted for review, the trade-off behind that
choice, and exactly how to run and verify it yourself.

---

## Hosting approach (and the honest trade-off)

The backend is served from a local instance exposed to the internet with an **ngrok**
HTTPS tunnel. The Vapi voice assistant (phone number, STT/TTS, LLM) is cloud-hosted and
calls that tunnel as its webhook.

**Why ngrok instead of a cloud PaaS:** as of 2026, the common free app hosts
(Railway, Render, Fly.io, Koyeb) all require a credit card at signup, and Hugging Face
Docker Spaces moved to a paid plan. Rather than block the submission on a payment method,
the system runs locally behind ngrok — which the assessment explicitly allows:

> *"What if I can't get a phone number provisioned in time? ... Provide a working local
> setup with clear instructions for us to test. You will not be penalized for vendor
> issues, but you will be evaluated on how you handled the blocker."* — challenge brief

The application is **fully cloud-ready** (see [Moving to a permanent host](#moving-to-a-permanent-host)):
`DATABASE_URL` already supports Postgres, and `railway.json` / `render.yaml` are included.
Switching to a paid-tier host is a 5-minute change, not a rewrite.

---

## Live demo endpoints

> The tunnel is live during review windows. If a URL is unreachable, it means the local
> instance is paused — **contact me to bring it up**, or run it yourself in ~2 minutes
> (below); the phone number and behaviour are identical.

| | |
|---|---|
| ☎️ **Phone number** | `+1 (864) 625-5296` (call from any phone; US number) |
| 🌐 **API base URL** | `https://238f-110-38-240-147.ngrok-free.app/api/v1` |
| 📊 **Dashboard** | `https://238f-110-38-240-147.ngrok-free.app/` |
| 📘 **API docs** | `https://238f-110-38-240-147.ngrok-free.app/docs` |

Quick checks:

```bash
# health
curl https://238f-110-38-240-147.ngrok-free.app/health

# list patients
curl https://238f-110-38-240-147.ngrok-free.app/api/v1/patients
```

> **ngrok browser notice:** opening an ngrok free URL in a *browser* first shows a
> one-time ngrok warning page — click **"Visit Site"** to continue. API clients (curl,
> Postman, and Vapi's webhook calls) bypass it automatically, so this does not affect the
> voice agent or programmatic access.

---

## Run it yourself (≈2 minutes)

No account or key needed to run the REST API + dashboard locally.

```bash
# prerequisites: Python 3.11+ and uv (https://docs.astral.sh/uv/)
git clone https://github.com/Huzaifa-ali/voice-ai-patient-registration.git
cd voice-ai-patient-registration

uv sync
cp .env.example .env          # defaults work out of the box (SQLite)
uv run python scripts/seed.py # optional: a couple of demo patients
uv run uvicorn app.main:app --reload
```

Then open:
- Dashboard → http://localhost:8000/
- API docs → http://localhost:8000/docs
- Health → http://localhost:8000/health

Run the test suite:

```bash
uv run pytest        # 36 tests
uv run ruff check .  # lint
uv run mypy app/     # types
```

---

## Reproduce the voice agent (optional)

To stand up the phone agent against your own backend:

1. **Expose the backend** (deployed host, or `ngrok http 8000` for local).
2. **Set env** in `.env`: `VAPI_WEBHOOK_SECRET` (any long random string) and
   `VAPI_SERVER_URL=https://<your-host>/api/v1/voice/vapi`, plus `VAPI_PRIVATE_API_KEY`
   from the Vapi dashboard.
3. **Build + push the assistant** (config as code — see [`vapi/README.md`](vapi/README.md)):
   ```bash
   uv run python vapi/build_assistant.py   # compose assistant.json from prompt + template + env
   uv run python vapi/push_assistant.py    # create/update the Vapi assistant
   uv run python vapi/push_tools.py        # register the two tools and attach them
   ```
4. **Attach a phone number** to the assistant in the Vapi dashboard and call it.

---

## Moving to a permanent host

When a payment method is available, deploy to any PaaS with no code changes:

1. Create a service from this GitHub repo (configs: `railway.json`, `render.yaml`, `Procfile`).
2. Add a **Postgres** instance and set `DATABASE_URL` to it — the app normalizes
   `postgres://` / `postgresql://` to the psycopg driver automatically.
3. Set `VAPI_WEBHOOK_SECRET`.
4. Take the public URL, set `VAPI_SERVER_URL=https://<host>/api/v1/voice/vapi`, and
   re-run `vapi/build_assistant.py` + `vapi/push_assistant.py`.

The phone number then works 24/7 without the local tunnel.
