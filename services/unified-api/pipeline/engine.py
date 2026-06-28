import json
import logging
from datetime import datetime
from sqlalchemy import text
from .normalizer import normalize_name, normalize_email, normalize_phone, normalize_address
from .matcher import find_best_match

logger = logging.getLogger(__name__)

class ReconciliationEngine:
    """Orchestrates ingestion, normalization, fuzzy matching, and idempotent database persistence."""

    def __init__(self, session):
        self.session = session
        self.extracted_count = 0
        self.processed_count = 0
        self.merged_count = 0
        self.flagged_count = 0
        self.created_count = 0
        self.skipped_count = 0

    def start_run(self) -> int:
        """Logs the start of a pipeline run in the database and returns the run ID."""
        query = text("""
            INSERT INTO pipeline_runs (status)
            VALUES ('running')
            RETURNING id
        """)
        result = self.session.execute(query)
        run_id = result.scalar()
        self.session.commit()
        logger.info(f"Initialized pipeline run ID: {run_id}")
        return run_id

    def complete_run(self, run_id: int, status: str, error_message: str = None):
        """Updates pipeline run stats and completion status."""
        query = text("""
            UPDATE pipeline_runs
            SET completed_at = CURRENT_TIMESTAMP,
                status = :status,
                records_extracted = :extracted,
                records_processed = :processed,
                records_merged = :merged,
                records_flagged = :flagged,
                error_message = :error_message
            WHERE id = :id
        """)
        self.session.execute(query, {
            "status": status,
            "extracted": self.extracted_count,
            "processed": self.processed_count,
            "merged": self.merged_count,
            "flagged": self.flagged_count,
            "error_message": error_message,
            "id": run_id
        })
        self.session.commit()
        logger.info(f"Completed pipeline run ID: {run_id} with status: {status}")

    def is_already_processed(self, source_system: str, source_record_id: str) -> bool:
        """Ensures idempotency by checking if the source record is already unified or in the review queue."""
        # Check if already present in unified customer lineage
        query_prov = text("""
            SELECT EXISTS(
                SELECT 1 FROM customer_provenance 
                WHERE source_system = :source_system AND source_record_id = :source_record_id
            )
        """)
        result_prov = self.session.execute(query_prov, {
            "source_system": source_system,
            "source_record_id": source_record_id
        })
        if result_prov.scalar():
            return True
            
        # Check if already pending review in flagged_records (unresolved)
        query_flag = text("""
            SELECT EXISTS(
                SELECT 1 FROM flagged_records
                WHERE source_system = :source_system AND source_record_id = :source_record_id AND resolved = FALSE
            )
        """)
        result_flag = self.session.execute(query_flag, {
            "source_system": source_system,
            "source_record_id": source_record_id
        })
        return result_flag.scalar()


    def get_match_candidates(self, email: str, phone: str, name: str) -> list[dict]:
        """Queries potential matching candidates from unified_customers to minimize comparison overhead."""
        # Query by exact email, exact phone, or first word of name
        first_word = name.split()[0] + "%" if name and name.split() else ""
        
        query = text("""
            SELECT id, full_name, email, phone, address
            FROM unified_customers
            WHERE (email IS NOT NULL AND email != '' AND email = :email)
               OR (phone IS NOT NULL AND phone != '' AND phone = :phone)
               OR (full_name ILIKE :first_name)
        """)
        
        result = self.session.execute(query, {
            "email": email,
            "phone": phone,
            "first_name": first_word
        })
        
        candidates = []
        for row in result:
            candidates.append({
                "id": str(row.id),
                "full_name": row.full_name,
                "email": row.email,
                "phone": row.phone,
                "address": row.address
            })
        return candidates

    def _enrich_customer(self, customer_id: str, current_fields: dict, incoming_normalized: dict) -> bool:
        """Enriches existing customer fields if the incoming record provides more complete information."""
        updates = {}
        
        # Enrich empty email
        if not current_fields.get("email") and incoming_normalized.get("email"):
            updates["email"] = incoming_normalized["email"]
            
        # Enrich empty phone
        if not current_fields.get("phone") and incoming_normalized.get("phone"):
            updates["phone"] = incoming_normalized["phone"]
            
        # Enrich empty address
        if not current_fields.get("address") and incoming_normalized.get("address"):
            updates["address"] = incoming_normalized["address"]
            
        if updates:
            # Generate dynamically matching UPDATE query
            set_clause = ", ".join(f"{col} = :{col}" for col in updates.keys())
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            
            query = text(f"""
                UPDATE unified_customers
                SET {set_clause}
                WHERE id = :id
            """)
            
            updates["id"] = customer_id
            self.session.execute(query, updates)
            logger.info(f"Enriched unified_customer {customer_id} with columns: {list(updates.keys())}")
            return True
            
        return False

    def ingest_record(self, run_id: int, raw_record: dict, source_system: str, source_record_id: str) -> tuple[str, str | None]:
        """
        Processes, normalizes, fuzzy-matches, and upserts a single raw record.
        
        Returns (action_taken, target_uuid). Actions: 'merged', 'flagged', 'created', 'skipped'.
        """
        # 1. Idempotency Check
        if self.is_already_processed(source_system, source_record_id):
            self.skipped_count += 1
            logger.debug(f"Skipping record {source_system}:{source_record_id} - already ingested.")
            return "skipped", None
            
        self.processed_count += 1
        
        # 2. Extract and Normalize Incoming Fields
        # Handles discrepancies in key names across different connectors
        raw_name = raw_record.get("name") or raw_record.get("cust_nm") or ""
        # SaaS API uses first_name + last_name
        if not raw_name and "first_name" in raw_record:
            raw_name = f"{raw_record.get('first_name', '')} {raw_record.get('last_name', '')}"
            
        raw_email = raw_record.get("email") or raw_record.get("email_addr") or ""
        raw_phone = raw_record.get("phone") or raw_record.get("phone_no") or ""
        raw_address = raw_record.get("address") or raw_record.get("addr_line1") or ""
        
        # Handle secondary address elements in legacy database
        if source_system == "legacy_db" and raw_record.get("city_name"):
            raw_address = f"{raw_address}, {raw_record['city_name']} {raw_record.get('postal_code', '')}"
            
        normalized_record = {
            "name": normalize_name(raw_name),
            "email": normalize_email(raw_email),
            "phone": normalize_phone(raw_phone),
            "address": normalize_address(raw_address)
        }
        
        # 3. Retrieve Matches
        candidates = self.get_match_candidates(
            normalized_record["email"],
            normalized_record["phone"],
            normalized_record["name"]
        )
        
        best_match, score, reasons = find_best_match(normalized_record, candidates)
        
        raw_data_json = json.dumps(raw_record)
        
        # 4. Decision Rule Engine
        # Case A: High Confidence -> Automerge
        if best_match and score >= 85:
            customer_id = best_match["id"]
            
            # Enrich fields if needed
            self._enrich_customer(customer_id, best_match, normalized_record)
            
            # Insert Provenance
            prov_query = text("""
                INSERT INTO customer_provenance (unified_customer_id, source_system, source_record_id, raw_data)
                VALUES (:unified_id, :source_system, :source_record_id, CAST(:raw_data AS jsonb))
            """)
            self.session.execute(prov_query, {
                "unified_id": customer_id,
                "source_system": source_system,
                "source_record_id": source_record_id,
                "raw_data": raw_data_json
            })
            
            self.merged_count += 1
            logger.debug(f"Automerged {source_system}:{source_record_id} to unified customer {customer_id} (Score: {score}%)")
            return "merged", customer_id
            
        # Case B: Medium Confidence -> Flag for Manual Review
        elif best_match and score >= 60:
            potential_id = best_match["id"]
            reason_str = "; ".join(reasons)
            
            flag_query = text("""
                INSERT INTO flagged_records (run_id, source_system, source_record_id, raw_data, potential_match_id, confidence_score, reason)
                VALUES (:run_id, :source_system, :source_record_id, CAST(:raw_data AS jsonb), :potential_id, :score, :reason)
            """)
            self.session.execute(flag_query, {
                "run_id": run_id,
                "source_system": source_system,
                "source_record_id": source_record_id,
                "raw_data": raw_data_json,
                "potential_id": potential_id,
                "score": float(score),
                "reason": reason_str[:255] # Truncate if too long
            })
            
            self.flagged_count += 1
            logger.debug(f"Flagged {source_system}:{source_record_id} for review. Potential match: {potential_id} (Score: {score}%)")
            return "flagged", None
            
        # Case C: Low Confidence -> Create New Unified Customer
        else:
            create_query = text("""
                INSERT INTO unified_customers (full_name, email, phone, address)
                VALUES (:full_name, :email, :phone, :address)
                RETURNING id
            """)
            result = self.session.execute(create_query, {
                "full_name": normalized_record["name"],
                "email": normalized_record["email"] or None,
                "phone": normalized_record["phone"] or None,
                "address": normalized_record["address"] or None
            })
            new_id = str(result.scalar())
            
            # Insert Provenance
            prov_query = text("""
                INSERT INTO customer_provenance (unified_customer_id, source_system, source_record_id, raw_data)
                VALUES (:unified_id, :source_system, :source_record_id, CAST(:raw_data AS jsonb))
            """)
            self.session.execute(prov_query, {
                "unified_id": new_id,
                "source_system": source_system,
                "source_record_id": source_record_id,
                "raw_data": raw_data_json
            })
            
            self.created_count += 1
            logger.debug(f"Created new unified customer {new_id} from {source_system}:{source_record_id}")
            return "created", new_id
