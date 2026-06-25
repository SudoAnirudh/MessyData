from fastapi import FastAPI

app = FastAPI(
    title="Unified CRM API",
    description="Consolidated CRM records, ingestion runs, and review endpoints."
)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "unified-api"}

@app.get("/")
def read_root():
    return {"message": "Welcome to MessyData Unified API. Ingestion engine is initialized."}
