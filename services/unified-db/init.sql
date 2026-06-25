-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Ingestion Pipeline Runs Table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL, -- 'running', 'success', 'failed'
    records_extracted INT DEFAULT 0,
    records_processed INT DEFAULT 0,
    records_merged INT DEFAULT 0,
    records_flagged INT DEFAULT 0,
    error_message TEXT
);

-- 2. Unified Customer Records Table (Golden Records)
CREATE TABLE IF NOT EXISTS unified_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    address VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for lookup speed
CREATE INDEX IF NOT EXISTS idx_unified_customers_email ON unified_customers(email);
CREATE INDEX IF NOT EXISTS idx_unified_customers_phone ON unified_customers(phone);

-- 3. Data Provenance & Lineage Table
CREATE TABLE IF NOT EXISTS customer_provenance (
    id SERIAL PRIMARY KEY,
    unified_customer_id UUID NOT NULL REFERENCES unified_customers(id) ON DELETE CASCADE,
    source_system VARCHAR(50) NOT NULL, -- 'legacy_db', 'saas_api', 'csv'
    source_record_id VARCHAR(100) NOT NULL, -- Primary Key of record in source system
    raw_data JSONB NOT NULL, -- Full JSON dump of the raw source record
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Ensure we don't ingest the same source record twice into the unified layer
    CONSTRAINT unique_source_record UNIQUE (source_system, source_record_id)
);

-- Indexing for lineage lookups
CREATE INDEX IF NOT EXISTS idx_customer_provenance_source ON customer_provenance(source_system, source_record_id);

-- 4. Flagged Duplicates for Manual Conflict Resolution
CREATE TABLE IF NOT EXISTS flagged_records (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    source_system VARCHAR(50) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    potential_match_id UUID REFERENCES unified_customers(id) ON DELETE SET NULL,
    confidence_score FLOAT,
    reason VARCHAR(255),
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for review workflow
CREATE INDEX IF NOT EXISTS idx_flagged_records_resolved ON flagged_records(resolved);
