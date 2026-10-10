"""Vapi tool-call request/response shapes.

Vapi POSTs ``{ "message": { "toolCalls": [ { "id", "function": { "name",
"arguments" } } ] } }`` and expects ``{ "results": [ { "toolCallId", "result" } ] }``
back with HTTP 200. ``arguments`` may arrive as a dict or a JSON string, so we parse
loosely rather than binding a strict model (robustness over strictness at the edge).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """One tool-call result. Exactly one of ``result``/``error`` is set.

    Both are flat strings per Vapi's contract. ``result`` is used for success AND for
    validation feedback (so the agent reads our message and re-prompts); ``error`` is
    reserved for infrastructure failures (bad secret, DB down) where Vapi's generic
    spoken failure message is acceptable.
    """

    toolCallId: str
    result: str | None = None
    error: str | None = None


class VapiResponse(BaseModel):
    """Top-level webhook response body."""

    results: list[ToolResult]


def extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the tool-call list out of a Vapi webhook payload defensively.

    Returns a list of ``{"id", "name", "arguments": dict}`` entries. Tolerates the
    ``message.toolCalls`` nesting and ``arguments`` arriving as dict or JSON string.
    """
    import json

    message = payload.get("message") or {}
    raw_calls = message.get("toolCalls") or payload.get("toolCalls") or []

    calls: list[dict[str, Any]] = []
    for call in raw_calls:
        fn = call.get("function") or {}
        name = fn.get("name") or call.get("name") or ""
        args = fn.get("arguments")
        if args is None:
            args = call.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        calls.append(
            {"id": call.get("id") or call.get("toolCallId") or "", "name": name, "arguments": args}
        )
    return calls
