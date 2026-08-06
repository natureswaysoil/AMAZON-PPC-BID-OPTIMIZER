"""
Main entry point for Amazon PPC Bid Optimizer backend jobs.

Imports use absolute paths relative to the backend directory because the
backend directory is copied to /app in the Docker image.
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def _validate_optimizer_data():
    """Stop before optimization when required BigQuery inputs are absent."""
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery
    from core.config import settings

    client = bigquery.Client(project=settings.PROJECT_ID)
    required_tables = (
        "keywords",
        "keyword_performance",
        "sp_advertised_product_metrics",
    )
    missing = []
    for table_name in required_tables:
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.{table_name}"
        try:
            client.get_table(table_id)
        except NotFound:
            missing.append(table_name)

    if missing:
        raise RuntimeError(
            "Optimizer cannot run because required BigQuery tables are missing: "
            + ", ".join(missing)
            + ". Complete the data sync/setup before running bid-optimizer."
        )


def main():
    """Route to a specific job based on the JOB_TYPE environment variable."""
    import os
    from datetime import datetime

    job_type = os.getenv("JOB_TYPE", "aov_optimizer")

    logger.info("=" * 60)
    logger.info("Starting job: %s", job_type)
    logger.info("Project: %s", os.getenv("GOOGLE_CLOUD_PROJECT", "N/A"))
    logger.info("Dataset: %s", os.getenv("BIGQUERY_DATASET", "amazon_ppc"))
    logger.info("Dry Run: %s", os.getenv("DRY_RUN", "False"))
    logger.info("Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
    logger.info("=" * 60)

    # BigQuery-only maintenance jobs do not need Amazon Ads credentials.
    if job_type != "aov_refresh":
        logger.info("Refreshing Amazon API token...")
        try:
            from shared.token_manager import token_manager

            token_manager.get_access_token()
            logger.info("Token ready")
        except Exception as exc:
            logger.error("Failed to initialize authentication: %s", exc)
            sys.exit(1)

    try:
        if job_type in ["aov_optimizer", "bid_optimizer"]:
            _validate_optimizer_data()
            from jobs.optimization.aov_bid_optimizer import run_aov_optimizer

            run_aov_optimizer()
        elif job_type == "preview_optimization":
            _validate_optimizer_data()
            from jobs.optimization.aov_bid_optimizer import run_preview_optimization

            run_preview_optimization()
        elif job_type == "keyword_harvester":
            from jobs.optimization.keyword_harvester import run_keyword_harvester

            run_keyword_harvester()
        elif job_type == "budget_pacer":
            from jobs.optimization.budget_pacer import run_budget_pacer

            run_budget_pacer()
        elif job_type == "ads_sync":
            from jobs.data_sync.amazon_ads_sync import run_amazon_ads_sync

            run_amazon_ads_sync()
        elif job_type == "aov_refresh":
            from jobs.ingestion.aov_refresh import run_aov_refresh

            run_aov_refresh()
        else:
            raise ValueError(f"Unknown job type: {job_type}")
    except Exception as exc:
        logger.exception("Job failed: %s", exc)
        sys.exit(1)

    logger.info("Job completed successfully")


if __name__ == "__main__":
    main()
