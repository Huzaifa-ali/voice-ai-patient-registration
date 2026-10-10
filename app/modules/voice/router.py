"""Vapi voice webhook endpoint.

Receives tool calls from the Vapi assistant and returns results in Vapi's contract.
ALWAYS responds HTTP 200 (Vapi ignores other statuses and tells the caller "no
result"). A bad/missing secret or a DB failure comes back as a tool ``error`` string;
validation feedback comes back as a ``result`` string so the agent re-prompts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.modules.voice import service
from app.modules.voice.schemas import ToolResult, VapiResponse, extract_tool_calls
from app.modules.voice.security import verify_secret

logger = get_logger("voice.api")

router = APIRouter(prefix="/voice", tags=["voice"])


def _respond(results: list[ToolResult]) -> JSONResponse:
    """Serialise to Vapi's response body, always HTTP 200."""
    body = VapiResponse(results=results).model_dump(exclude_none=True)
    return JSONResponse(status_code=200, content=body)


@router.post("/vapi")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """Handle one or more Vapi tool calls."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    calls = extract_tool_calls(payload if isinstance(payload, dict) else {})

    # Authorise. On failure, answer every call with a graceful error (still HTTP 200).
    if not verify_secret(request.headers):
        logger.warning("Rejected Vapi webhook: bad or missing secret")
        return _respond(
            [
                ToolResult(toolCallId=c["id"], error="I can't save that right now.")
                for c in calls
            ]
            or [ToolResult(toolCallId="", error="Unauthorized.")]
        )

    results: list[ToolResult] = []
    for call in calls:
        result, error = service.handle_tool_call(db, call["name"], call["arguments"])
        results.append(ToolResult(toolCallId=call["id"], result=result, error=error))

    return _respond(results)
