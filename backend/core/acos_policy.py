"""Canonical ACOS policy - single source of truth.

Mirrors campaign-optimizer/acos_policy.py. Duplicated rather than shared
because backend/ and campaign-optimizer/ are separate Cloud Run
deployables with separate Docker build contexts, so they can't import a
shared module directly. If a real shared package becomes worth the setup
cost, that's where this logic should move.

See campaign-optimizer/acos_policy.py for the full history of the 7+
disagreeing ACOS values this replaces (this file's own TARGET_ACOS_DEFAULT
in config.py, at 0.30, was one of them).
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
    for 15 minutes."""
    if _cache["value"] is not None and (time.time() - _cache["ts"]) < _CACHE_TTL_SECONDS:
        return _cache["value"]

    value = DEFAULT_TARGET_ACOS
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "amazon-ppc-bid-optimizer"))
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
