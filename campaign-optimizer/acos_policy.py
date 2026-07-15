"""Canonical ACOS policy - single source of truth.

Before this module existed, at least 7 different ACOS-related values were
scattered across this codebase and others, mostly unwired dead code:
backend/core/config.py's TARGET_ACOS_DEFAULT=0.30, this service's own
WINNER_MAX_ACOS=0.35 env-var default, config/campaign_rules.json's
target_acos_fallback=0.35, the root optimizer_config.json's
TOP_PERFORMER/PROFITABLE/MARGINAL scheme (0.35/0.65/1.5), the original
four-tier bug-report policy (25/25/32/38%), and the one value that turned
out to actually be live-authoritative: amazon_ppc.optimizer_config's
target_acos row (0.25), which amazon-ppc-api's /api/settings reads.

TARGET_ACOS and CIRCUIT_BREAKER_CEILING are kept as two distinct numbers
on purpose. TARGET_ACOS is what bid-decision/promotion logic aims for.
CIRCUIT_BREAKER_CEILING is a separate, higher safety threshold - crossing
it means something has gone wrong badly enough to warrant an automatic
pause, not just a bid nudge. Collapsing them to one number would make the
circuit breaker fire on routine performance variance around the target.
CIRCUIT_BREAKER_CEILING is the value already proven safe in production
(added and verified during the original incident response).
"""
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TARGET_ACOS = 0.25
CIRCUIT_BREAKER_CEILING = 0.38

_OPTIMIZER_CONFIG_TABLE = "amazon-ppc-bid-optimizer.amazon_ppc.optimizer_config"
_CACHE_TTL_SECONDS = 900

_cache: dict = {"value": None, "ts": 0.0}


def get_target_acos() -> float:
    """Read target_acos from amazon_ppc.optimizer_config, falling back to
    DEFAULT_TARGET_ACOS if the table/row is unavailable. Cached in-process
    for 15 minutes so this isn't a BigQuery round-trip on every call."""
    if _cache["value"] is not None and (time.time() - _cache["ts"]) < _CACHE_TTL_SECONDS:
        return _cache["value"]

    value = DEFAULT_TARGET_ACOS
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
        rows = list(
            client.query(
                f"SELECT value FROM `{_OPTIMIZER_CONFIG_TABLE}` WHERE key = 'target_acos' LIMIT 1"
            ).result()
        )
        if rows:
            value = float(rows[0].value)
    except Exception as exc:
        logger.warning(
            f"Failed to read target_acos from {_OPTIMIZER_CONFIG_TABLE}, using default {DEFAULT_TARGET_ACOS}: {exc}"
        )
        value = DEFAULT_TARGET_ACOS

    _cache["value"] = value
    _cache["ts"] = time.time()
    return value


def get_circuit_breaker_ceiling() -> float:
    """Hard ACOS ceiling above which a campaign gets auto-paused. Not read
    from BigQuery on purpose - this is a safety rail, not a tuning knob that
    should silently drift if someone edits a config row."""
    return CIRCUIT_BREAKER_CEILING
