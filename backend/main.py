import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    job_type = os.getenv('JOB_TYPE', 'unknown')
    logger.info(f"Starting job: {job_type}")
    print(f"✅ Job '{job_type}' completed successfully")

if __name__ == "__main__":
    main()
