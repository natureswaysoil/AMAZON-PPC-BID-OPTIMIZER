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
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TARGET_ACOS = 0.25
CIRCUIT_BREAKER_CEILING = 0.38

# Per-campaign circuit-breaker tiers (2026-07-16 incident response). A single
# flat ceiling can't tell a low-margin product (can't survive 38% ACOS) from
# a high-LTV one (can) apart, so the breaker needs a ceiling per campaign,
# not one number for the whole account. Sourced from the existing
# products.target_acos column (Stage 2's per-product override, already the
# canonical per-product ACOS knob - not a new, seventh config source).
# CONSERVATIVE_CEILING is the mandatory default when a campaign has no
# product with target_acos set: never fall back to "no limit."
CONSERVATIVE_CEILING = 0.25
CIRCUIT_BREAKER_FLOOR_BID = 0.02  # Amazon's practical SP keyword bid minimum

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


def get_all_campaign_acos_ceilings() -> Dict[str, float]:
    """Per-campaign circuit-breaker ceiling for every campaign that has
    advertised at least one product with a products.target_acos override.
    Campaigns not present in the returned dict have no product-level
    override and must use CONSERVATIVE_CEILING as their ceiling - never
    treat a missing entry as "no limit."

    A campaign can advertise more than one ASIN (e.g. AUTO_DISCOVERY); when
    it does, the MIN() of its products' target_acos is used so the breaker
    never applies a more permissive ceiling than the tightest-margin product
    in that campaign warrants.
    """
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
        query = """
            SELECT m.campaign_id, MIN(p.target_acos) AS ceiling
            FROM `amazon-ppc-bid-optimizer.amazon_ppc.sp_advertised_product_metrics` m
            JOIN `amazon-ppc-bid-optimizer.amazon_ppc.products` p
              ON (m.asin != '' AND m.asin = p.asin) OR (m.sku != '' AND m.sku = p.sku)
            WHERE p.target_acos IS NOT NULL
            GROUP BY m.campaign_id
        """
        return {str(row.campaign_id): float(row.ceiling) for row in client.query(query).result()}
    except Exception as exc:
        logger.warning(f"Failed to load per-campaign ACOS ceilings, all campaigns will use the conservative default: {exc}")
        return {}


def get_campaign_acos_ceiling(campaign_id: str, ceilings: Optional[Dict[str, float]] = None) -> float:
    """Ceiling for a single campaign. Pass a pre-fetched `ceilings` dict
    (from get_all_campaign_acos_ceilings) when checking many campaigns in a
    loop to avoid a BigQuery round-trip per campaign."""
    table = ceilings if ceilings is not None else get_all_campaign_acos_ceilings()
    return table.get(str(campaign_id), CONSERVATIVE_CEILING)
