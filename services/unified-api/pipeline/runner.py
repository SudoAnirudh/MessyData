import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path to resolve imports correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.logging_config import setup_logging
logger = setup_logging("pipeline_runner")


from pipeline.connectors.legacy_db import LegacyDBConnector
from pipeline.connectors.saas_api import SaaSAPIConnector
from pipeline.connectors.csv_extractor import CSVExtractor
from pipeline.engine import ReconciliationEngine

def run_etl():
    """Runs the full ETL consolidation pipeline."""
    # Resolve connection URL for the Unified database (target store)
    unified_db_url = os.getenv(
        "UNIFIED_DATABASE_URL",
        "postgresql://postgres:postgres@unified-db:5432/unified_crm"
    )
    
    logger.info("Initializing database connection for unified target store...")
    engine_db = create_engine(unified_db_url)
    Session = sessionmaker(bind=engine_db)
    session = Session()
    
    pipeline = ReconciliationEngine(session)
    run_id = pipeline.start_run()
    
    try:
        # 1. Initialize Connectors
        legacy_conn = LegacyDBConnector()
        saas_conn = SaaSAPIConnector()
        csv_conn = CSVExtractor()
        
        # 2. Extract Data from all sources
        logger.info("Starting extraction phase...")
        
        legacy_records = []
        try:
            legacy_records = legacy_conn.extract()
        except Exception as ex:
            logger.error(f"Error during Legacy DB extraction: {ex}. Continuing with other sources.")
            
        saas_records = []
        try:
            saas_records = saas_conn.extract()
        except Exception as ex:
            logger.error(f"Error during SaaS API extraction: {ex}. Continuing with other sources.")
            
        csv_records = []
        try:
            csv_records = csv_conn.extract()
        except Exception as ex:
            logger.error(f"Error during CSV extraction: {ex}. Continuing with other sources.")
            
        total_extracted = len(legacy_records) + len(saas_records) + len(csv_records)
        pipeline.extracted_count = total_extracted
        logger.info(f"Extraction completed. Extracted {total_extracted} records in total.")
        
        # 3. Processing and Loading Phase
        logger.info("Starting processing and reconciliation phase...")
        
        # A. Process Legacy Records
        logger.info(f"Processing {len(legacy_records)} Legacy DB records...")
        for rec in legacy_records:
            pipeline.ingest_record(
                run_id=run_id,
                raw_record=rec,
                source_system="legacy_db",
                source_record_id=rec["id"]
            )
            
        # B. Process SaaS API Records
        logger.info(f"Processing {len(saas_records)} SaaS API records...")
        for rec in saas_records:
            pipeline.ingest_record(
                run_id=run_id,
                raw_record=rec,
                source_system="saas_api",
                source_record_id=str(rec["id"])
            )
            
        # C. Process CSV Records
        logger.info(f"Processing {len(csv_records)} CSV records...")
        for rec in csv_records:
            pipeline.ingest_record(
                run_id=run_id,
                raw_record=rec,
                source_system="csv",
                source_record_id=rec["id"]
            )
            
        # Commit transaction and complete run
        session.commit()
        pipeline.complete_run(run_id, "success")
        
        logger.info("="*60)
        logger.info("ETL Pipeline Run Summary:")
        logger.info(f" - Extracted: {pipeline.extracted_count}")
        logger.info(f" - Processed (New/Unique): {pipeline.processed_count}")
        logger.info(f" - Merged/Linked (Auto): {pipeline.merged_count}")
        logger.info(f" - Flagged for Review  : {pipeline.flagged_count}")
        logger.info(f" - New Profiles Created : {pipeline.created_count}")
        logger.info(f" - Skipped (Idempotent) : {pipeline.skipped_count}")
        logger.info("="*60)
        
    except Exception as e:
        session.rollback()
        logger.error(f"Pipeline execution aborted due to unhandled error: {e}")
        pipeline.complete_run(run_id, "failed", error_message=str(e))
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    run_etl()
