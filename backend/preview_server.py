"""Tiny HTTP wrapper around AOVBidOptimizer.preview_optimization() so a
frontend can trigger a what-if bid-optimization preview on demand, not only
via the JOB_TYPE=preview_optimization Cloud Run Job entrypoint in main.py.

This is a separate deployable entrypoint from main.py (which stays a batch
Job - Cloud Run Jobs don't serve HTTP), but reuses the exact same, already-
tested AOVBidOptimizer code with a thin request/response layer - no logic
duplication. Run locally with:

    uvicorn preview_server:app --port 8080

Deploying this as its own Cloud Run *Service* (as opposed to the existing
Job) from the same Docker image, with a different container command, is
real infra work this file does not attempt - see the module docstring
gap noted alongside it in code review.
"""
import hmac
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jobs.optimization.aov_bid_optimizer import AOVBidOptimizer
from core.rule_engine import Rule

logger = logging.getLogger(__name__)

app = FastAPI(title="Bid Optimizer Preview Service")


def verify_internal_token(authorization: Optional[str], x_daily_optimizer_token: Optional[str]) -> None:
    """Same shared-secret scheme as campaign-optimizer/optimize_campaigns.py's
    verify_internal_token - duplicated for the same separate-Docker-context
    reason as the rest of this codebase's small duplicated modules."""
    token = os.getenv("DAILY_OPTIMIZER_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="DAILY_OPTIMIZER_TOKEN not configured")

    supplied = None
    if x_daily_optimizer_token:
        supplied = x_daily_optimizer_token.strip()
    elif authorization and authorization.startswith("Bearer "):
        supplied = authorization.replace("Bearer ", "", 1).strip()

    if not supplied:
        raise HTTPException(status_code=401, detail="Missing token")
    if not hmac.compare_digest(supplied, token):
        raise HTTPException(status_code=403, detail="Invalid token")


class RuleOverride(BaseModel):
    type: str
    enabled: bool = True
    params: Dict[str, Any] = {}


class PreviewRequest(BaseModel):
    target_acos: Optional[float] = None
    rules: Optional[List[RuleOverride]] = None


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/preview")
def preview(
    body: PreviewRequest,
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Read-only: projects what the bid optimizer would do against recent
    data with an optional hypothetical target ACOS and/or stacking rule set.
    Never writes to BigQuery, never calls the Amazon Ads API."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    rules_override = None
    if body.rules is not None:
        rules_override = [Rule(type=r.type, enabled=r.enabled, params=r.params) for r in body.rules]

    optimizer = AOVBidOptimizer()
    try:
        summary = optimizer.preview_optimization(
            target_acos_override=body.target_acos,
            rules_override=rules_override,
        )
    except Exception as exc:
        logger.exception("Preview failed")
        return JSONResponse({"error": True, "message": str(exc)}, status_code=502)

    return JSONResponse(summary)
