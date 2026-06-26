import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("verify_extraction")

# Ensure the workspace directory is in the path to import pipeline modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "unified-api")))

try:
    from pipeline.connectors.legacy_db import LegacyDBConnector
    from pipeline.connectors.saas_api import SaaSAPIConnector
    from pipeline.connectors.csv_extractor import CSVExtractor
except ImportError as e:
    logger.error(f"Failed to import connectors. Check sys.path setup. Details: {e}")
    sys.exit(1)

def verify_legacy_db():
    logger.info("--- Testing Legacy DB Connector ---")
    # Resolve URL: container env var -> host-forwarded fallback
    db_url = os.getenv(
        "LEGACY_DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5433/legacy_crm"
    )
    logger.info(f"Using Legacy DB URL: {db_url.split('@')[-1]}") # Log host/db only for safety
    try:
        connector = LegacyDBConnector(db_url=db_url)
        records = connector.extract()
        logger.info(f"SUCCESS: Extracted {len(records)} records from legacy database.")
        if records:
            logger.info("Sample record 1:")
            logger.info(records[0])
            if len(records) > 1:
                logger.info("Sample record 2:")
                logger.info(records[1])
        return len(records)
    except Exception as e:
        logger.error(f"FAILED Legacy DB extraction: {e}")
        return 0

def verify_saas_api():
    logger.info("--- Testing Mock SaaS API Connector ---")
    # Resolve URL: container env var -> host-forwarded fallback
    api_url = os.getenv("SAAS_API_URL", "http://localhost:8001")
    logger.info(f"Using SaaS API URL: {api_url}")
    try:
        connector = SaaSAPIConnector(api_url=api_url)
        records = connector.extract()
        logger.info(f"SUCCESS: Extracted {len(records)} records from mock SaaS API.")
        if records:
            logger.info("Sample record 1:")
            logger.info(records[0])
            if len(records) > 1:
                logger.info("Sample record 2:")
                logger.info(records[1])
        return len(records)
    except Exception as e:
        logger.error(f"FAILED SaaS API extraction: {e}")
        return 0

def verify_csv_extractor():
    logger.info("--- Testing CSV Extractor ---")
    # Resolve directory: container path -> local fallback
    drop_dir = os.getenv(
        "CSV_DROP_DIR", 
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "csv-drop"))
    )
    logger.info(f"Using CSV directory: {drop_dir}")
    try:
        connector = CSVExtractor(drop_dir=drop_dir)
        records = connector.extract()
        logger.info(f"SUCCESS: Extracted {len(records)} records from regional CSV exports.")
        if records:
            logger.info("Sample record 1:")
            logger.info(records[0])
            if len(records) > 1:
                logger.info("Sample record 2:")
                logger.info(records[1])
        return len(records)
    except Exception as e:
        logger.error(f"FAILED CSV extraction: {e}")
        return 0

def main():
    logger.info("Starting source connector validation runs...")
    
    legacy_count = verify_legacy_db()
    print("\n" + "="*50 + "\n")
    
    saas_count = verify_saas_api()
    print("\n" + "="*50 + "\n")
    
    csv_count = verify_csv_extractor()
    print("\n" + "="*50 + "\n")
    
    total = legacy_count + saas_count + csv_count
    logger.info(f"Verification completed. Extracted raw record counts:")
    logger.info(f" - Legacy CRM DB: {legacy_count}")
    logger.info(f" - Mock SaaS API: {saas_count}")
    logger.info(f" - CSV Exports  : {csv_count}")
    logger.info(f" - Total Extracted: {total}")
    
    if total == 0:
        logger.error("No records extracted from any source. Verification failed.")
        sys.exit(1)
    else:
        logger.info("Source connector verification succeeded.")

if __name__ == "__main__":
    main()
