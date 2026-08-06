"""Fail-closed campaign budget pacing using current SP campaign metrics."""
import logging
import os
from datetime import date, timedelta

from google.cloud import bigquery
from core.acos_policy import get_target_acos
from core.config import settings
from shared.amazon_client import amazon_client

logger = logging.getLogger(__name__)
LOOKBACK_DAYS = 14
MAX_DATA_AGE_DAYS = 2
UNDERPACE_THRESHOLD = 0.70
INCREASE_FACTOR = 1.10


def proposed_budget(current_budget, spend, sales, latest_date, target_acos):
    """Return a safe increased budget, or None when evidence is insufficient."""
    if not latest_date or latest_date < date.today() - timedelta(days=MAX_DATA_AGE_DAYS):
        return None
    current_budget = float(current_budget or 0)
    spend = float(spend or 0)
    sales = float(sales or 0)
    if current_budget <= 0 or spend <= 0 or sales <= 0:
        return None
    pacing_ratio = spend / (current_budget * LOOKBACK_DAYS)
    acos = spend / sales
    if pacing_ratio >= UNDERPACE_THRESHOLD or acos >= target_acos:
        return None
    return round(current_budget * INCREASE_FACTOR, 2)


def _performance(client):
    table = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.sp_campaign_performance"
    sql = f"""
        SELECT campaign_id, MAX(date) AS latest_date,
               SUM(cost) AS spend, SUM(sales) AS sales
        FROM `{table}`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {LOOKBACK_DAYS} DAY)
        GROUP BY campaign_id
    """
    return {int(row.campaign_id): row for row in client.query(sql).result()}


def run_budget_pacer():
    """Increase only fresh, genuinely under-paced, below-target campaigns."""
    logger.info("Running budget pacer (fail-closed)")
    performance = _performance(bigquery.Client(project=settings.PROJECT_ID))
    target = get_target_acos()
    changes = 0
    for campaign in amazon_client.list_sp_campaigns_v3(state_filter="ENABLED"):
        campaign_id = int(campaign.get("campaignId"))
        metrics = performance.get(campaign_id)
        budget = campaign.get("dailyBudget")
        if budget is None and isinstance(campaign.get("budget"), dict):
            budget = campaign["budget"].get("budget")
        new_budget = proposed_budget(
            budget, getattr(metrics, "spend", None), getattr(metrics, "sales", None),
            getattr(metrics, "latest_date", None), target,
        )
        if new_budget is None:
            logger.info("Skipped campaign %s: missing, stale, or ineligible data", campaign_id)
            continue
        if os.getenv("DRY_RUN", "false").lower() not in {"1", "true", "yes"}:
            amazon_client.update_campaign_budget(campaign_id, new_budget)
        logger.info("Budget campaign %s %.2f -> %.2f", campaign_id, budget, new_budget)
        changes += 1
    logger.info("Budget pacer completed. Changes: %s", changes)
    return changes
