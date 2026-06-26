import os
import logging
from sqlalchemy import create_engine, text

# Set up logger
logger = logging.getLogger(__name__)

class LegacyDBConnector:
    """Connector to extract raw customer data from the legacy PostgreSQL database."""
    
    def __init__(self, db_url: str = None):
        # Fallback to env var if database URL is not provided
        self.db_url = db_url or os.getenv(
            "LEGACY_DATABASE_URL", 
            "postgresql://postgres:postgres@legacy-db:5432/legacy_crm"
        )
        self.engine = create_engine(self.db_url)

    def extract(self) -> list[dict]:
        """Queries legacy_customers and returns list of raw records."""
        query = text("""
            SELECT id, cust_nm, email_addr, phone_no, addr_line1, city_name, postal_code, created_at
            FROM legacy_customers
        """)
        
        records = []
        try:
            logger.info("Connecting to legacy database to extract records...")
            with self.engine.connect() as conn:
                result = conn.execute(query)
                # Map SQL rows to dictionaries
                for row in result:
                    records.append({
                        "id": str(row.id),
                        "cust_nm": row.cust_nm,
                        "email_addr": row.email_addr,
                        "phone_no": row.phone_no,
                        "addr_line1": row.addr_line1,
                        "city_name": row.city_name,
                        "postal_code": row.postal_code,
                        "created_at": row.created_at
                    })
            logger.info(f"Successfully extracted {len(records)} records from legacy database.")
        except Exception as e:
            logger.error(f"Failed to extract records from legacy database: {e}")
            raise e
            
        return records
