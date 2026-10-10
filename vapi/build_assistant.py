"""Compose a deployable Vapi assistant config from its parts.

Follows Vapi's "config as code" guidance (https://github.com/VapiAI/gitops):
the system prompt lives as a standalone Markdown file (the single source of
truth) and is injected into the assistant JSON at build time. This avoids the
drift that happens when the prompt is copy-pasted into the JSON by hand.

Secrets and the (ephemeral) server URL are NEVER committed. The template keeps
placeholders; this script injects real values from the environment at build
time, and the generated ``assistant.json`` is gitignored.

Source of truth (committed):
  - vapi/system-prompt.md         → the prompt text (between the PROMPT markers)
  - vapi/assistant.template.json   → everything else, with placeholders for
                                     the server URL and secret

Injected from env (not committed):
  - VAPI_WEBHOOK_SECRET  → replaces the secret placeholder
  - VAPI_SERVER_URL      → replaces the server-URL placeholder (your public
                           https webhook, e.g. the ngrok/Render URL ending in
                           /api/v1/voice/vapi)

Output (gitignored, contains live values):
  - vapi/assistant.json  → the composed config you push to Vapi

Usage:
  uv run python vapi/build_assistant.py           # writes vapi/assistant.json
  uv run python vapi/build_assistant.py --check    # verify template+prompt in sync (CI)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).parent
_PROMPT_MD = _HERE / "system-prompt.md"
_TEMPLATE = _HERE / "assistant.template.json"
_TEMPLATE_EXAMPLE = _HERE / "assistant.template.example.json"
_OUTPUT = _HERE / "assistant.json"


def _template_path() -> Path:
    """Use the local template if present, else fall back to the committed example.

    On a fresh clone only ``assistant.template.example.json`` exists (the real
    template is gitignored); building from the example still works with
    placeholders, and env injection fills in the server URL + secret.
    """
    return _TEMPLATE if _TEMPLATE.exists() else _TEMPLATE_EXAMPLE

# Placeholders that live in the committed template and are swapped at build time.
_SECRET_PLACEHOLDER = "REPLACE_WITH_VAPI_WEBHOOK_SECRET"
_URL_PLACEHOLDER = "https://YOUR-DEPLOYED-HOST/api/v1/voice/vapi"

# The prompt text is delimited in the Markdown by these HTML comment markers so
# the human-readable rationale around it never leaks into the assistant.
_PROMPT_RE = re.compile(
    r"<!--\s*PROMPT:START\s*-->(.*?)<!--\s*PROMPT:END\s*-->", re.DOTALL
)


def extract_prompt() -> str:
    """Return the canonical system prompt text from the Markdown file."""
    text = _PROMPT_MD.read_text(encoding="utf-8")
    match = _PROMPT_RE.search(text)
    if not match:
        raise SystemExit(
            "Could not find <!-- PROMPT:START --> / <!-- PROMPT:END --> markers "
            f"in {_PROMPT_MD.name}"
        )
    body = match.group(1).strip()
    # The prompt is wrapped in a ```text ... ``` fence for Markdown readability;
    # strip the fences so only the prompt text is injected into the JSON.
    body = re.sub(r"^```[a-zA-Z]*\n", "", body)
    body = re.sub(r"\n```$", "", body)
    return body.strip()


def compose(inject_env: bool) -> dict:
    """Build the assistant config dict.

    Always injects the prompt. When ``inject_env`` is True, also replaces the
    server-URL and secret placeholders with values from the environment.
    """
    raw = _template_path().read_text(encoding="utf-8")

    if inject_env:
        load_dotenv(_HERE.parent / ".env")
        secret = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()
        url = os.getenv("VAPI_SERVER_URL", "").strip()
        if secret:
            raw = raw.replace(_SECRET_PLACEHOLDER, secret)
        if url:
            raw = raw.replace(_URL_PLACEHOLDER, url)

    template = json.loads(raw)
    prompt = extract_prompt()
    messages = template.setdefault("model", {}).setdefault("messages", [])
    for msg in messages:
        if msg.get("role") == "system":
            msg["content"] = prompt
            break
    else:
        messages.insert(0, {"role": "system", "content": prompt})
    return template


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the template+prompt compose cleanly (CI gate; no env injection).",
    )
    args = parser.parse_args()

    if args.check:
        # Check mode validates that the sources compose into valid JSON with the
        # prompt in sync — it does NOT compare against the live, secret-injected
        # assistant.json (which is gitignored and environment-specific).
        try:
            compose(inject_env=False)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Compose failed: {exc}", file=sys.stderr)
            return 1
        print("vapi template + prompt compose cleanly.")
        return 0

    composed = compose(inject_env=True)
    rendered = json.dumps(composed, indent=2, ensure_ascii=False) + "\n"
    _OUTPUT.write_text(rendered, encoding="utf-8")

    # Warn if placeholders remain (env vars were not set).
    warnings = []
    if _SECRET_PLACEHOLDER in rendered:
        warnings.append("VAPI_WEBHOOK_SECRET not set — secret placeholder remains")
    if _URL_PLACEHOLDER in rendered:
        warnings.append("VAPI_SERVER_URL not set — server URL placeholder remains")

    print(f"Wrote {_OUTPUT.relative_to(_HERE.parent)} (prompt injected from {_PROMPT_MD.name}).")
    for w in warnings:
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
