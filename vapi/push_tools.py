"""Promote the two inline tools to PERMANENT Vapi tools and attach them by ID.

Why: inline tools (defined in assistant.model.tools) work on calls but do NOT
appear in the dashboard Tools tab and can't be managed there. Permanent tools
live in the Tools library, show up in the UI, and are attached to the assistant
via model.toolIds — the pattern Vapi's GitOps model uses.

This script:
  1. reads the two tool definitions from vapi/assistant.json,
  2. creates (or updates) each as a permanent tool via POST/PATCH /tool,
  3. attaches them to the assistant via model.toolIds and clears model.tools,
  4. records the tool IDs in .env (VAPI_TOOL_IDS) so re-runs update, not duplicate.

Usage:
  uv run python vapi/push_tools.py
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).parent
_ROOT = _HERE.parent
_ASSISTANT = _HERE / "assistant.json"
_ENV = _ROOT / ".env"
_BASE = "https://api.vapi.ai"
_UA = "voice-patient-agent/1.0 (+https://vapi.ai)"


def _request(method: str, path: str, key: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} on {method} {path}:\n{e.read().decode('utf-8','replace')}")


def _tool_payload(inline: dict) -> dict:
    """Shape an inline assistant tool into a permanent-tool create payload."""
    return {
        "type": "function",
        "function": inline["function"],
        "server": inline["server"],
    }


def _update_env(tool_ids: dict[str, str]) -> None:
    """Persist name->id map to .env as VAPI_TOOL_IDS (JSON) for idempotent re-runs."""
    text = _ENV.read_text(encoding="utf-8") if _ENV.exists() else ""
    line = f"VAPI_TOOL_IDS={json.dumps(tool_ids)}"
    if re.search(r"^VAPI_TOOL_IDS=.*$", text, re.MULTILINE):
        text = re.sub(r"^VAPI_TOOL_IDS=.*$", line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + "\n\n# Permanent Vapi tool IDs (managed by push_tools.py)\n" + line + "\n"
    _ENV.write_text(text, encoding="utf-8")


def main() -> int:
    load_dotenv(_ENV)
    key = os.getenv("VAPI_PRIVATE_API_KEY", "").strip()
    aid = os.getenv("VAPI_ASSISTANT_ID", "").strip()
    if not key or not aid:
        raise SystemExit("VAPI_PRIVATE_API_KEY and VAPI_ASSISTANT_ID must be set in .env")

    existing: dict[str, str] = {}
    raw = os.getenv("VAPI_TOOL_IDS", "").strip()
    if raw:
        try:
            existing = json.loads(raw)
        except json.JSONDecodeError:
            existing = {}

    assistant = json.loads(_ASSISTANT.read_text(encoding="utf-8"))
    inline_tools = assistant["model"]["tools"]

    tool_ids: dict[str, str] = {}
    for inline in inline_tools:
        name = inline["function"]["name"]
        payload = _tool_payload(inline)
        if name in existing:
            res = _request("PATCH", f"/tool/{existing[name]}", key, payload)
            print(f"Updated tool {name} ({res.get('id')})")
        else:
            res = _request("POST", "/tool", key, payload)
            print(f"Created tool {name} ({res.get('id')})")
        tool_ids[name] = res["id"]

    # Attach by ID, drop inline tools so there is no duplication.
    update = {"model": dict(assistant["model"])}
    update["model"].pop("tools", None)
    update["model"]["toolIds"] = list(tool_ids.values())
    _request("PATCH", f"/assistant/{aid}", key, update)
    print(f"Attached toolIds to assistant {aid}: {list(tool_ids.values())}")

    _update_env(tool_ids)
    print("Recorded VAPI_TOOL_IDS in .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
