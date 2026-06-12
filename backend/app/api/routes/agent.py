import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import decode_token
from app.db.models.agent_run import AgentRun
from app.db.models.user import User
from app.db.session import get_db, get_db_session

router = APIRouter(prefix="/agent", tags=["agent"])

POLL_INTERVAL_SECONDS = 1.0
MAX_STREAM_SECONDS = 3600.0

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # disable Nginx buffering
}


def _run_to_dict(run: AgentRun) -> dict:
    return {
        "id": str(run.id),
        "store_id": str(run.store_id),
        "run_type": run.run_type,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "current_phase": run.current_phase,
        "result_summary": run.result_summary,
        "error_message": run.error_message,
        "credits_reserved": run.credits_reserved,
        "credits_used": run.credits_used,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat(),
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def run_event_stream(
    run_id: str,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    max_seconds: float = MAX_STREAM_SECONDS,
):
    """Poll the run row and emit an SSE event whenever its state changes.

    Sync generator on purpose: StreamingResponse runs it in a threadpool,
    and each poll opens a short-lived session so Celery's committed
    progress updates are visible.
    """
    yield _sse({"type": "connected", "run_id": run_id})

    last_state: tuple | None = None
    deadline = time.monotonic() + max_seconds

    while time.monotonic() < deadline:
        with get_db_session() as db:
            run = db.query(AgentRun).filter_by(id=run_id).first()
            if run is None:
                yield _sse(
                    {"type": "failed", "run_id": run_id, "error": "Run not found"}
                )
                return
            state = (run.status, run.progress_pct, run.current_phase)
            result = run.result_summary
            error = run.error_message

        if state != last_state:
            last_state = state
            status, progress, phase = state
            if status == "completed":
                yield _sse(
                    {
                        "type": "completed",
                        "run_id": run_id,
                        "result": result,
                        "progress": 100,
                    }
                )
                return
            if status in ("failed", "cancelled"):
                yield _sse({"type": "failed", "run_id": run_id, "error": error})
                return
            yield _sse(
                {
                    "type": "progress",
                    "run_id": run_id,
                    "status": status,
                    "phase": phase,
                    "progress": progress,
                }
            )

        time.sleep(poll_interval)

    yield _sse({"type": "timeout", "run_id": run_id})


def _user_from_query_token(token: str, db: Session) -> User:
    """EventSource can't send headers, so the JWT arrives as ?token=."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            401, detail={"code": "TOKEN_INVALID", "message": "Invalid or expired token"}
        )
    user = (
        db.query(User)
        .filter(User.id == payload["sub"], User.deleted_at.is_(None))
        .first()
    )
    if not user:
        raise HTTPException(
            401, detail={"code": "TOKEN_INVALID", "message": "User not found"}
        )
    return user


def _get_owned_run(run_id: str, user: User, db: Session) -> AgentRun:
    run = db.query(AgentRun).filter_by(id=run_id, user_id=user.id).first()
    if not run:
        raise HTTPException(
            404, detail={"code": "NOT_FOUND", "message": "Run not found"}
        )
    return run


@router.get("/runs/{run_id}", response_model=dict)
def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = _get_owned_run(run_id, current_user, db)
    return {"data": _run_to_dict(run)}


@router.get("/runs/{run_id}/stream")
def stream_run(
    run_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    user = _user_from_query_token(token, db)
    _get_owned_run(run_id, user, db)
    return StreamingResponse(
        run_event_stream(run_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
