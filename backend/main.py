"""
Main entry point for Amazon PPC Bid Optimizer backend jobs
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
    
    job_type = os.getenv('JOB_TYPE', 'aov_optimizer')
    
    logger.info(f"Starting job: {job_type}")
    
    if job_type == 'aov_optimizer':
        from backend.jobs.optimization.aov_bid_optimizer import run_aov_optimizer
        run_aov_optimizer()
    else:
        logger.error(f"Unknown job type: {job_type}")
        sys.exit(1)
    
    logger.info("Job completed successfully")

if __name__ == "__main__":
    main()
