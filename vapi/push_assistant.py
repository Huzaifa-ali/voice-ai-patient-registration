"""Push vapi/assistant.json to Vapi (create or update the assistant).

Reads the private API key from the environment / .env (VAPI_PRIVATE_API_KEY) so
the key is never passed on the command line. Creates a new assistant; if
VAPI_ASSISTANT_ID is set, updates that one instead.

Usage:
  uv run python vapi/push_assistant.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).parent
_ASSISTANT = _HERE / "assistant.json"
_API = "https://api.vapi.ai/assistant"


def main() -> int:
    load_dotenv(_HERE.parent / ".env")
    key = os.getenv("VAPI_PRIVATE_API_KEY", "").strip()
    if not key:
        print("VAPI_PRIVATE_API_KEY is not set (put it in .env).", file=sys.stderr)
        return 1

    config = json.loads(_ASSISTANT.read_text(encoding="utf-8"))
    # ``_notes`` is our own documentation field; Vapi's API rejects unknown keys.
    config.pop("_notes", None)

    # If permanent tools have been created (push_tools.py recorded their IDs in
    # VAPI_TOOL_IDS), attach them by ID and strip the inline tool definitions so
    # a push never silently reverts permanent tools back to inline ones.
    tool_ids_raw = os.getenv("VAPI_TOOL_IDS", "").strip()
    if tool_ids_raw:
        try:
            tool_ids = list(json.loads(tool_ids_raw).values())
        except json.JSONDecodeError:
            tool_ids = []
        if tool_ids:
            config.setdefault("model", {}).pop("tools", None)
            config["model"]["toolIds"] = tool_ids

    assistant_id = os.getenv("VAPI_ASSISTANT_ID", "").strip()
    url = f"{_API}/{assistant_id}" if assistant_id else _API
    method = "PATCH" if assistant_id else "POST"

    data = json.dumps(config).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Cloudflare at Vapi's edge rejects the default urllib UA (err 1010).
            "User-Agent": "voice-patient-agent/1.0 (+https://vapi.ai)",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code} from Vapi:\n{detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - network/edge
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    aid = body.get("id", "(no id returned)")
    print(f"{'Updated' if assistant_id else 'Created'} assistant.")
    print(f"Assistant ID: {aid}")
    print(f"Name        : {body.get('name')}")
    model = body.get("model", {})
    print(f"Model       : {model.get('provider')} {model.get('model')}")
    inline = model.get("tools", []) or []
    tool_ids = model.get("toolIds", []) or []
    if inline:
        print(f"Tools       : {[t.get('function', {}).get('name') for t in inline]} (inline)")
    else:
        print(f"Tools       : {len(tool_ids)} attached by id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
