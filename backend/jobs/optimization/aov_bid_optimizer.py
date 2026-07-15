# jobs/optimization/aov_bid_optimizer.py
# Note: Uses absolute imports relative to backend directory (Docker container root)
from google.cloud import bigquery
from core.config import (
    AOV_TIERS, PERFORMANCE_MULTIPLIERS, MATCH_TYPE_MULTIPLIERS,
    get_time_multiplier, MAX_BID_AS_PERCENT_OF_AOV, settings
)
from aov_fetcher import aov_fetcher
from shared.amazon_client import amazon_client
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


class AOVBidOptimizer:
    def __init__(self):
        self._bq_client = None
        self.amazon_client = amazon_client

    @property
    def bq_client(self):
        """Lazy initialization of BigQuery client."""
        if self._bq_client is None:
            self._bq_client = bigquery.Client(project=settings.PROJECT_ID)
        return self._bq_client

    def get_aov_tier(self, aov: float) -> str:
        """Determine the AOV tier using exclusive upper bounds."""
        if aov is None:
            return "L"

        for tier_code, tier in AOV_TIERS.items():
            if tier.min_aov <= aov < tier.max_aov:
                return tier_code

        if aov >= AOV_TIERS["X"].max_aov:
            return "X"
        return "L"

    def get_performance_tier(self, keyword_data: dict) -> str:
        """Classify keyword performance into tiers A-E."""
        acos = float(keyword_data.get("acos") or 0)
        cvr = float(keyword_data.get("cvr") or 0)
        conversions = int(keyword_data.get("conversions_30d") or 0)
        clicks = int(keyword_data.get("clicks_30d") or 0)

        # Check the most severe zero-order condition first so Tier E is reachable.
        if conversions == 0 and clicks > 50:
            return "E"
        if acos > 0.45 or (conversions == 0 and clicks > 20):
            return "D"
        if conversions >= 5 and acos <= 0.25 and cvr >= 0.12:
            return "A"
        if conversions >= 3 and acos <= 0.35 and cvr >= 0.08:
            return "B"
        if conversions >= 1 and acos <= 0.45:
            return "C"
        return "C"

    def calculate_optimal_bid(self, keyword_data: dict, current_hour: int) -> dict:
        """Calculate a safe optimal bid using AOV, performance, and loss gates."""
        aov = float(keyword_data.get("aov") or 30)
        match_type = str(keyword_data.get("match_type", "EXACT")).upper()
        current_bid = float(keyword_data.get("current_bid") or settings.MIN_BID)
        clicks = int(keyword_data.get("clicks_30d") or 0)
        conversions = int(keyword_data.get("conversions_30d") or 0)
        cost = float(keyword_data.get("cost_30d") or 0)
        acos = float(keyword_data.get("acos") or 0)
        target_acos = float(keyword_data.get("target_acos") or 0.30)

        aov_tier_code = self.get_aov_tier(aov)
        aov_tier = AOV_TIERS[aov_tier_code]
        performance_tier = self.get_performance_tier(keyword_data)

        ceiling = (
            aov_tier.base_ceiling_exact
            * PERFORMANCE_MULTIPLIERS[performance_tier]
            * MATCH_TYPE_MULTIPLIERS.get(match_type, 0.75)
            * get_time_multiplier(current_hour, performance_tier)
        )
        aov_safety_ceiling = aov * MAX_BID_AS_PERCENT_OF_AOV
        ceiling = min(ceiling, aov_safety_ceiling, settings.MAX_BID)

        pause_recommended = False
        decision = "performance_adjustment"

        # Zero-order traffic must never be interpreted as excellent ACOS.
        if conversions == 0:
            if clicks >= settings.PAUSE_CLICKS_MIN or cost >= settings.PAUSE_SPEND_MIN:
                new_bid = current_bid * (1 - settings.MAX_DOWN_PCT_PER_RUN)
                pause_recommended = True
                decision = "zero_order_pause_gate"
            elif clicks >= settings.LOSE_CLICKS_MIN or cost >= settings.LOSE_SPEND_MIN:
                new_bid = current_bid * 0.85
                decision = "zero_order_loss_gate"
            else:
                new_bid = current_bid
                decision = "insufficient_zero_order_data"
        elif acos < target_acos * 0.70:
            new_bid = min(current_bid * 1.15, ceiling)
        elif acos < target_acos:
            new_bid = min(current_bid * 1.05, ceiling)
        elif acos < target_acos * 1.30:
            new_bid = current_bid
        else:
            decrease_factor = max(1 - settings.MAX_DOWN_PCT_PER_RUN, target_acos / acos)
            new_bid = current_bid * decrease_factor

        # Per-run movement rails.
        max_allowed = current_bid * (1 + settings.MAX_UP_PCT_PER_RUN)
        min_allowed = current_bid * (1 - settings.MAX_DOWN_PCT_PER_RUN)
        new_bid = min(new_bid, max_allowed)
        new_bid = max(new_bid, min_allowed)

        # Global and AOV-based rails.
        new_bid = min(new_bid, ceiling, settings.MAX_BID)
        new_bid = max(settings.MIN_BID, new_bid)

        # Ignore changes smaller than five percent.
        if current_bid > 0 and abs(new_bid - current_bid) / current_bid < 0.05:
            new_bid = current_bid

        reasoning = (
            f"AOV: ${aov:.2f} (Tier {aov_tier_code}) | "
            f"Perf: Tier {performance_tier} | Match: {match_type} | "
            f"Hour: {current_hour} | Orders: {conversions} | Clicks: {clicks} | "
            f"Spend: ${cost:.2f} | ACOS: {acos:.1%} vs Target: {target_acos:.1%} | "
            f"Decision: {decision} | Ceiling: ${ceiling:.2f}"
        )

        return {
            "new_bid": round(new_bid, 2),
            "ceiling": round(ceiling, 2),
            "aov_tier": aov_tier_code,
            "performance_tier": performance_tier,
            "pause_recommended": pause_recommended,
            "decision": decision,
            "reasoning": reasoning,
            "aov": aov,
            "safety_ceiling": round(aov_safety_ceiling, 2),
        }

    def optimize_all_keywords(self) -> list:
        """Get all keywords and calculate optimal bids."""
        logger.info("Fetching real-time AOV data...")
        try:
            aov_fetcher.fetch_all()
        except Exception as exc:
            logger.error(f"Failed to fetch AOV data: {exc}")
            logger.info("Continuing with default AOV values...")

        current_hour = datetime.now(ZoneInfo(settings.TIMEZONE)).hour

        query = """
        WITH keyword_performance AS (
          SELECT
            k.keyword_id,
            k.keyword_text,
            k.bid as current_bid,
            k.match_type,
            k.campaign_id,
            SUM(kp.clicks) as clicks_30d,
            SUM(kp.purchases) as conversions_30d,
            SUM(kp.cost) as cost_30d,
            SUM(kp.sales) as sales_30d,
            SAFE_DIVIDE(CAST(SUM(kp.purchases) AS FLOAT64), CAST(SUM(kp.clicks) AS FLOAT64)) as cvr,
            SAFE_DIVIDE(SUM(kp.cost), NULLIF(SUM(kp.sales), 0)) as acos
          FROM `{project}.{dataset}.keywords` k
          LEFT JOIN `{project}.{dataset}.sp_keyword_performance` kp
            ON k.keyword_id = kp.keyword_id
            AND kp.sync_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
          WHERE k.state = 'ENABLED'
          GROUP BY k.keyword_id, k.keyword_text, k.bid, k.match_type, k.campaign_id
        )
        SELECT
          keyword_id,
          keyword_text,
          current_bid,
          match_type,
          campaign_id,
          COALESCE(clicks_30d, 0) as clicks_30d,
          COALESCE(conversions_30d, 0) as conversions_30d,
          COALESCE(cost_30d, 0.0) as cost_30d,
          COALESCE(sales_30d, 0.0) as sales_30d,
          COALESCE(cvr, 0.0) as cvr,
          COALESCE(acos, 0.0) as acos
        FROM keyword_performance
        WHERE clicks_30d >= 1
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)

        try:
            results = self.bq_client.query(query).result()
        except Exception as exc:
            logger.error(f"Query failed: {exc}")
            return []

        optimizations = []
        for row in results:
            keyword_data = dict(row)
            campaign_id = keyword_data.get("campaign_id")
            aov_data = aov_fetcher.get_aov(campaign_id)
            keyword_data["aov"] = aov_data.aov
            keyword_data["aov_confidence"] = aov_data.confidence
            keyword_data["target_acos"] = 0.30

            try:
                optimization = self.calculate_optimal_bid(keyword_data, current_hour)
                if optimization["new_bid"] != float(keyword_data["current_bid"]):
                    optimizations.append({
                        "keyword_id": keyword_data["keyword_id"],
                        "keyword_text": keyword_data["keyword_text"],
                        "campaign_id": campaign_id,
                        "current_bid": float(keyword_data["current_bid"]),
                        "aov_confidence": aov_data.confidence,
                        **optimization,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as exc:
                logger.error(f"Failed to optimize keyword {keyword_data.get('keyword_id')}: {exc}")

        logger.info(f"Found {len(optimizations)} keywords to optimize")
        if optimizations:
            self._log_optimizations(optimizations)
        return optimizations

    def _log_optimizations(self, optimizations: list):
        """Log optimization decisions to BigQuery."""
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.bid_optimizations"
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
        )
        try:
            job = self.bq_client.load_table_from_json(optimizations, table_id, job_config=job_config)
            job.result()
            logger.info(f"Logged {len(optimizations)} optimizations to BigQuery")
        except Exception as exc:
            logger.error(f"Failed to log optimizations: {exc}")

    def apply_bid_changes(self, optimizations: list, dry_run: bool = False):
        """Apply bid changes using the shared Amazon client."""
        if dry_run:
            logger.info(f"DRY RUN: Would update {len(optimizations)} bids")
            return
        if not optimizations:
            logger.info("No bid changes to apply")
            return

        batch_size = 100
        successful_updates = 0
        failed_updates = 0
        for i in range(0, len(optimizations), batch_size):
            batch = optimizations[i:i + batch_size]
            try:
                self.amazon_client.update_keyword_bids_batch(batch)
                successful_updates += len(batch)
                logger.info(f"Updated batch {i // batch_size + 1} ({len(batch)} keywords)")
            except Exception as exc:
                logger.error(f"Failed to update batch: {exc}")
                failed_updates += len(batch)

        logger.info(f"Bid update summary: {successful_updates} successful, {failed_updates} failed")


def run_aov_optimizer():
    """Entry point for Cloud Run job."""
    import os

    logging.basicConfig(level=logging.INFO)
    logger.info("Starting AOV-based bid optimizer...")
    dry_run = os.getenv("DRY_RUN", "False").lower() in ["true", "1", "yes"]
    optimizer = AOVBidOptimizer()
    optimizations = optimizer.optimize_all_keywords()
    logger.info(f"Optimization complete: {len(optimizations)} bids to update")

    if optimizations:
        optimizer.apply_bid_changes(optimizations, dry_run=dry_run)
        tier_summary = {}
        for optimization in optimizations:
            tier = optimization["aov_tier"]
            tier_summary[tier] = tier_summary.get(tier, 0) + 1
        logger.info("Optimization Summary by AOV Tier:")
        for tier, count in sorted(tier_summary.items()):
            logger.info(f"Tier {tier}: {count} keywords")
        logger.info(f"Total optimizations: {len(optimizations)}")
    else:
        logger.info("No keywords needed optimization")


if __name__ == "__main__":
    run_aov_optimizer()
