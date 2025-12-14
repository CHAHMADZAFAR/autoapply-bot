
import sys
import os
import time
import argparse
import random
from pathlib import Path

# Add src to python path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.logger import setup_logger
from src.core.config_loader import ConfigLoader
from src.core.secrets_manager import SecretsManager
from src.core.database import Database
from src.discovery.job_searcher import JobSearcher
from src.executor.app_submitter import AppSubmitter

def main():
    parser = argparse.ArgumentParser(description="AutoApply Bot v2.1")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config file")
    parser.add_argument("--secrets", default="config/secrets.yaml", help="Path to secrets file")
    args = parser.parse_args()

    # Initialize Core Components
    # Load Config First to get log settings
    try:
        config_loader = ConfigLoader(args.config)
        config = config_loader.load()
    except Exception as e:
        print(f"Failed to load config: {e}")
        sys.exit(1)

    # Setup Logger
    cw_config = config.get('aws')
    logger = setup_logger("AutoApplyBot", cloudwatch_config=cw_config)
    logger.info("Starting AutoApply Bot v2.1...")

    try:
        logger.info("Configuration loaded successfully.")

        # Load Secrets
        secrets_manager = SecretsManager(args.secrets, config.get('aws', {}).get('region', 'us-east-1'))
        secrets = secrets_manager.get_secrets()
        logger.info("Secrets loaded/verified.")

        # Initialize Database
        db = Database()
        logger.info("Database initialized.")
        
        # Initialize Modules
        job_searcher = JobSearcher(config, db)
        app_submitter = AppSubmitter(config, db, secrets)
        
        # Main Loop
        logger.info("Entering main execution loop...")
        
        while True:
            try:
                # 1. Get Search Parameters from Config or Rotate
                keywords = config.get('job_search', {}).get('keywords', [])
                locations = config.get('job_search', {}).get('locations', [])

                if not keywords:
                    logger.warning("No keywords found in config. Sleeping...")
                    time.sleep(600)
                    continue

                for keyword in keywords:
                    for location in locations:
                        logger.info(f"Running search cycle: {keyword} in {location}")
                        
                        # 2. Search
                        found_jobs = job_searcher.search_linkedin(keyword, location)
                        
                        if not found_jobs:
                            logger.info("No new jobs found for this criteria.")
                            continue

                        # 3. Apply
                        app_submitter.apply_to_jobs(found_jobs)
                        
                        # 4. Check Limits (Basic check)
                        # In production, check daily limit from DB count
                        
                        # Random delay between keywords
                        time.sleep(random.uniform(30, 60))

                logger.info("Cycle complete. Sleeping before next run...")
                time.sleep(3600) # Run every hour (or use cron/scheduler)

            except KeyboardInterrupt:
                logger.info("Stopping bot...")
                break
            except Exception as loop_e:
                logger.error(f"Error in main loop: {loop_e}", exc_info=True)
                time.sleep(60) # Prevent tight crash loop
                
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
