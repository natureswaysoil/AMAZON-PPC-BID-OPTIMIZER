"""
Main entry point for Amazon PPC Bid Optimizer backend jobs

Note: Imports use absolute paths relative to the backend directory
since in the Docker container, backend/ is copied to /app/ root.
"""
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point - route to specific job based on environment"""
    import os
    from datetime import datetime
    
    job_type = os.getenv('JOB_TYPE', 'aov_optimizer')
    
    # Print banner like the working job
    logger.info("=" * 60)
    logger.info("🚀 Starting Bid Optimizer")
    logger.info(f"Project: {os.getenv('GOOGLE_CLOUD_PROJECT', 'N/A')}")
    logger.info(f"Dataset: {os.getenv('BIGQUERY_DATASET', 'amazon_ppc')}")
    logger.info(f"Dry Run: {os.getenv('DRY_RUN', 'False')}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 60)
    logger.info("")
    
    # Initialize authentication
    logger.info("🔑 Step 1: Refreshing Amazon API token...")
    try:
        from shared.token_manager import token_manager
        token_manager.get_access_token()  # Force token refresh
        logger.info("✅ Token ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize authentication: {e}")
        sys.exit(1)
    
    logger.info("")
    
    if job_type in ['aov_optimizer', 'bid_optimizer']:
        from jobs.optimization.aov_bid_optimizer import run_aov_optimizer
        run_aov_optimizer()
    elif job_type == 'ads_sync':
        from jobs.data_sync.amazon_ads_sync import run_amazon_ads_sync
        run_amazon_ads_sync()
    else:
        logger.error(f"Unknown job type: {job_type}")
        sys.exit(1)
    
    logger.info("Job completed successfully")

if __name__ == "__main__":
    main()
