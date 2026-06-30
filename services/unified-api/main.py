import os
import logging
from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Import ETL runner and normalizers
from pipeline.runner import run_etl
from pipeline.normalizer import normalize_name, normalize_email, normalize_phone, normalize_address

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unified_api")

# Database setup
DATABASE_URL = os.getenv(
    "UNIFIED_DATABASE_URL",
    "postgresql://postgres:postgres@unified-db:5432/unified_crm"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(
    title="Unified CRM API",
    description="Consolidated CRM records, ingestion runs, and review endpoints.",
    version="1.0.0"
)

# --- Pydantic Schemas ---

class PipelineRunResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    records_extracted: int
    records_processed: int
    records_merged: int
    records_flagged: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class FlaggedRecordResponse(BaseModel):
    id: int
    run_id: int
    source_system: str
    source_record_id: str
    raw_data: Dict[str, Any]
    potential_match_id: Optional[UUID] = None
    confidence_score: float
    reason: Optional[str] = None
    resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ResolveRequest(BaseModel):
    action: str = Field(..., description="Must be either 'merge' or 'create'")
    target_customer_id: Optional[UUID] = Field(None, description="Overrides potential_match_id if action is 'merge'")

class UnifiedCustomerResponse(BaseModel):
    id: UUID
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProvenanceResponse(BaseModel):
    id: int
    source_system: str
    source_record_id: str
    raw_data: Dict[str, Any]
    matched_at: datetime

    class Config:
        from_attributes = True

class UnifiedCustomerDetailResponse(UnifiedCustomerResponse):
    provenance: List[ProvenanceResponse] = []

# --- Health Check ---

@app.get("/health")
def health():
    return {"status": "healthy", "service": "unified-api"}

@app.get("/")
def read_root():
    return {"message": "Welcome to MessyData Unified API. Ingestion engine is initialized."}

# --- Pipeline Runs Endpoints ---

@app.get("/api/v1/pipeline/runs", response_model=List[PipelineRunResponse])
def list_pipeline_runs(db: Session = Depends(get_db)):
    """Retrieves execution history of all ETL pipeline runs."""
    query = text("""
        SELECT id, started_at, completed_at, status, records_extracted, records_processed, records_merged, records_flagged, error_message 
        FROM pipeline_runs 
        ORDER BY id DESC
    """)
    result = db.execute(query)
    runs = []
    for row in result:
        runs.append({
            "id": row.id,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "status": row.status,
            "records_extracted": row.records_extracted,
            "records_processed": row.records_processed,
            "records_merged": row.records_merged,
            "records_flagged": row.records_flagged,
            "error_message": row.error_message
        })
    return runs

def bg_run_pipeline():
    """Wrapper task to run ETL pipeline safely in background thread."""
    try:
        run_etl()
    except Exception as e:
        logger.error(f"Background ETL run failed: {e}")

@app.post("/api/v1/pipeline/run", status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline_run(background_tasks: BackgroundTasks):
    """Triggers the ETL pipeline asynchronously as a background task."""
    background_tasks.add_task(bg_run_pipeline)
    return {"message": "ETL pipeline execution triggered successfully.", "status": "running"}

# --- Flagged Records Endpoints ---

@app.get("/api/v1/flagged", response_model=List[FlaggedRecordResponse])
def list_flagged_records(resolved: Optional[bool] = None, db: Session = Depends(get_db)):
    """Lists flagged duplicate records needing manual resolution."""
    if resolved is not None:
        query = text("""
            SELECT id, run_id, source_system, source_record_id, raw_data, potential_match_id, confidence_score, reason, resolved, created_at
            FROM flagged_records
            WHERE resolved = :resolved
            ORDER BY id DESC
        """)
        result = db.execute(query, {"resolved": resolved})
    else:
        query = text("""
            SELECT id, run_id, source_system, source_record_id, raw_data, potential_match_id, confidence_score, reason, resolved, created_at
            FROM flagged_records
            ORDER BY id DESC
        """)
        result = db.execute(query)

    records = []
    for row in result:
        records.append({
            "id": row.id,
            "run_id": row.run_id,
            "source_system": row.source_system,
            "source_record_id": row.source_record_id,
            "raw_data": row.raw_data,
            "potential_match_id": row.potential_match_id,
            "confidence_score": row.confidence_score,
            "reason": row.reason,
            "resolved": row.resolved,
            "created_at": row.created_at
        })
    return records

@app.post("/api/v1/flagged/{record_id}/resolve")
def resolve_flagged_record(record_id: int, request: ResolveRequest, db: Session = Depends(get_db)):
    """
    Manually resolves a flagged duplicate record by either merging it with an
    existing unified customer profile or creating a new unified record.
    """
    # 1. Fetch Flagged Record
    fetch_query = text("""
        SELECT id, source_system, source_record_id, raw_data, potential_match_id, resolved
        FROM flagged_records
        WHERE id = :id
    """)
    flagged = db.execute(fetch_query, {"id": record_id}).fetchone()
    
    if not flagged:
        raise HTTPException(status_code=404, detail="Flagged record not found")
        
    if flagged.resolved:
        raise HTTPException(status_code=400, detail="Record has already been resolved")
        
    source_system = flagged.source_system
    source_record_id = flagged.source_record_id
    raw_data = flagged.raw_data

    # Extract name, email, phone, address for standardizing
    raw_name = raw_data.get("name") or raw_data.get("cust_nm") or ""
    if not raw_name and "first_name" in raw_data:
        raw_name = f"{raw_data.get('first_name', '')} {raw_data.get('last_name', '')}"
    raw_email = raw_data.get("email") or raw_data.get("email_addr") or ""
    raw_phone = raw_data.get("phone") or raw_data.get("phone_no") or ""
    raw_address = raw_data.get("address") or raw_data.get("addr_line1") or ""
    if source_system == "legacy_db" and raw_data.get("city_name"):
        raw_address = f"{raw_address}, {raw_data['city_name']} {raw_data.get('postal_code', '')}"

    normalized_record = {
        "name": normalize_name(raw_name),
        "email": normalize_email(raw_email),
        "phone": normalize_phone(raw_phone),
        "address": normalize_address(raw_address)
    }

    try:
        target_uuid = None
        
        # Action A: Merge with existing Golden Record
        if request.action == "merge":
            target_uuid = request.target_customer_id or flagged.potential_match_id
            if not target_uuid:
                raise HTTPException(
                    status_code=400, 
                    detail="Merge action requires potential_match_id or target_customer_id"
                )
                
            # Verify target unified customer exists
            cust_check = text("SELECT id, email, phone, address FROM unified_customers WHERE id = :id")
            cust = db.execute(cust_check, {"id": target_uuid}).fetchone()
            if not cust:
                raise HTTPException(status_code=400, detail="Target unified customer profile does not exist")
                
            # Perform optional enrichment
            enrichments = {}
            if not cust.email and normalized_record["email"]:
                enrichments["email"] = normalized_record["email"]
            if not cust.phone and normalized_record["phone"]:
                enrichments["phone"] = normalized_record["phone"]
            if not cust.address and normalized_record["address"]:
                enrichments["address"] = normalized_record["address"]
                
            if enrichments:
                set_clause = ", ".join(f"{col} = :{col}" for col in enrichments.keys())
                enrich_query = text(f"""
                    UPDATE unified_customers
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """)
                enrichments["id"] = target_uuid
                db.execute(enrich_query, enrichments)
                
            # Insert Lineage Provenance Link
            prov_query = text("""
                INSERT INTO customer_provenance (unified_customer_id, source_system, source_record_id, raw_data)
                VALUES (:unified_id, :source_system, :source_record_id, CAST(:raw_data AS jsonb))
            """)
            db.execute(prov_query, {
                "unified_id": target_uuid,
                "source_system": source_system,
                "source_record_id": source_record_id,
                "raw_data": json_dumps_raw(raw_data)
            })
            
        # Action B: Create New Golden Record
        elif request.action == "create":
            create_query = text("""
                INSERT INTO unified_customers (full_name, email, phone, address)
                VALUES (:full_name, :email, :phone, :address)
                RETURNING id
            """)
            result = db.execute(create_query, {
                "full_name": normalized_record["name"],
                "email": normalized_record["email"] or None,
                "phone": normalized_record["phone"] or None,
                "address": normalized_record["address"] or None
            })
            target_uuid = result.scalar()
            
            # Insert Provenance
            prov_query = text("""
                INSERT INTO customer_provenance (unified_customer_id, source_system, source_record_id, raw_data)
                VALUES (:unified_id, :source_system, :source_record_id, CAST(:raw_data AS jsonb))
            """)
            db.execute(prov_query, {
                "unified_id": target_uuid,
                "source_system": source_system,
                "source_record_id": source_record_id,
                "raw_data": json_dumps_raw(raw_data)
            })
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Action must be 'merge' or 'create'.")

        # Mark conflict as resolved
        resolve_query = text("""
            UPDATE flagged_records
            SET resolved = TRUE
            WHERE id = :id
        """)
        db.execute(resolve_query, {"id": record_id})
        
        db.commit()
        logger.info(f"Manually resolved flagged record {record_id} via action '{request.action}' -> Unified ID: {target_uuid}")
        return {"status": "success", "action": request.action, "resolved_id": target_uuid}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to resolve flagged record {record_id}: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Database resolution execution failed: {e}")

def json_dumps_raw(data: Any) -> str:
    import json
    return json.dumps(data)

# --- Unified Customers Endpoints ---

@app.get("/api/v1/customers", response_model=List[UnifiedCustomerResponse])
def list_unified_customers(
    q: Optional[str] = None, 
    limit: int = 100, 
    offset: int = 0, 
    db: Session = Depends(get_db)
):
    """Lists consolidated golden customer profiles. Supports fuzzy query searching on name, email, or phone."""
    if q:
        search_pattern = f"%{q}%"
        query = text("""
            SELECT id, full_name, email, phone, address, created_at, updated_at
            FROM unified_customers
            WHERE full_name ILIKE :q
               OR email ILIKE :q
               OR phone ILIKE :q
            ORDER BY full_name ASC
            LIMIT :limit OFFSET :offset
        """)
        result = db.execute(query, {"q": search_pattern, "limit": limit, "offset": offset})
    else:
        query = text("""
            SELECT id, full_name, email, phone, address, created_at, updated_at
            FROM unified_customers
            ORDER BY full_name ASC
            LIMIT :limit OFFSET :offset
        """)
        result = db.execute(query, {"limit": limit, "offset": offset})

    customers = []
    for row in result:
        customers.append({
            "id": row.id,
            "full_name": row.full_name,
            "email": row.email,
            "phone": row.phone,
            "address": row.address,
            "created_at": row.created_at,
            "updated_at": row.updated_at
        })
    return customers

@app.get("/api/v1/customers/{customer_id}", response_model=UnifiedCustomerDetailResponse)
def get_unified_customer_details(customer_id: UUID, db: Session = Depends(get_db)):
    """Retrieves full profile details for a unified customer, including its source lineage (provenance)."""
    # 1. Fetch Golden Profile
    profile_query = text("""
        SELECT id, full_name, email, phone, address, created_at, updated_at
        FROM unified_customers
        WHERE id = :id
    """)
    profile = db.execute(profile_query, {"id": customer_id}).fetchone()
    if not profile:
        raise HTTPException(status_code=404, detail="Unified customer profile not found")

    # 2. Fetch Provenance (Lineage Source Links)
    prov_query = text("""
        SELECT id, source_system, source_record_id, raw_data, matched_at
        FROM customer_provenance
        WHERE unified_customer_id = :id
        ORDER BY matched_at ASC
    """)
    result_prov = db.execute(prov_query, {"id": customer_id})
    provenance_list = []
    for row in result_prov:
        provenance_list.append({
            "id": row.id,
            "source_system": row.source_system,
            "source_record_id": row.source_record_id,
            "raw_data": row.raw_data,
            "matched_at": row.matched_at
        })

    return {
        "id": profile.id,
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "address": profile.address,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "provenance": provenance_list
    }
