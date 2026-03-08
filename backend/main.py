import os
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    job_type = os.getenv('JOB_TYPE', 'unknown')
    logger.info(f"Starting job: {job_type} at {datetime.now()}")
    
    try:
        if job_type == 'ads_sync':
            from backend.jobs.data_sync.ads_data_sync import run_ads_sync
            run_ads_sync()
        
        elif job_type == 'bid_optimizer':
            from backend.jobs.optimization.aov_bid_optimizer import run_aov_optimizer
            run_aov_optimizer()
        
        else:
            logger.info(f"Job type '{job_type}' - placeholder")
            print(f"✅ Job '{job_type}' completed")
        
        logger.info("Job completed successfully")
        
    except Exception as e:
        logger.error(f"Job failed: {job_type}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
