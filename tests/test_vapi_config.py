"""Guard tests for the Vapi assistant configuration (config as code).

The committed source of truth is ``vapi/assistant.template.json`` +
``vapi/system-prompt.md``. The deployable ``vapi/assistant.json`` is a GENERATED,
gitignored artifact (it carries the live webhook secret and an environment-specific
server URL), so these tests validate the committed template, not the artifact.

Ensures the template:
  1. is valid JSON,
  2. composes cleanly with the prompt (build --check passes),
  3. exposes exactly the two tools the backend's webhook implements,
  4. keeps the save_patient contract aligned with the backend schema,
  5. contains NO real secrets — only placeholders (secret is injected at build time).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
# The committed source of truth is the EXAMPLE template (the working template is
# gitignored). Prefer the example so tests pass on a fresh clone / CI.
_TEMPLATE = _ROOT / "vapi" / "assistant.template.example.json"
_BUILD = _ROOT / "vapi" / "build_assistant.py"

_SECRET_PLACEHOLDER = "REPLACE_WITH_VAPI_WEBHOOK_SECRET"
_URL_PLACEHOLDER = "https://YOUR-DEPLOYED-HOST/api/v1/voice/vapi"


def _load_template() -> dict:
    return json.loads(_TEMPLATE.read_text(encoding="utf-8"))


def test_template_is_valid_json() -> None:
    assert isinstance(_load_template(), dict)


def test_template_and_prompt_compose_cleanly() -> None:
    """`build_assistant.py --check` composes template + prompt without error."""
    result = subprocess.run(
        [sys.executable, str(_BUILD), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_exposes_the_two_backend_tools() -> None:
    d = _load_template()
    tools = {t["function"]["name"] for t in d["model"]["tools"]}
    assert tools == {"save_patient", "lookup_patient"}


def test_save_patient_required_fields_match_backend() -> None:
    d = _load_template()
    save = next(t for t in d["model"]["tools"] if t["function"]["name"] == "save_patient")
    required = set(save["function"]["parameters"]["required"])
    assert required == {
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone_number",
        "address_line_1",
        "city",
        "state",
        "zip_code",
    }
    # Sex enum must match the backend's canonical values exactly.
    sex_enum = save["function"]["parameters"]["properties"]["sex"]["enum"]
    assert sex_enum == ["Male", "Female", "Other", "Decline to Answer"]


def test_committed_template_has_no_real_secrets() -> None:
    """The committed template must carry placeholders, never a real secret/URL."""
    raw = _TEMPLATE.read_text(encoding="utf-8")
    assert _SECRET_PLACEHOLDER in raw
    assert _URL_PLACEHOLDER in raw
    # No obvious real API-key material committed.
    assert "sk-" not in raw
