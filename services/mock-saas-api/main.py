import os
import json
import random
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Mock SaaS API",
    description="Simulated Third-Party CRM REST API with rate-limiting, pagination, and random failures."
)

# Rate limiting settings: 5 requests per second
RATE_LIMIT_WINDOW = 1.0  # 1 second
RATE_LIMIT_MAX = 5
request_history = {}  # ip -> list of timestamps

# Load seed data
SEED_FILE = os.path.join(os.path.dirname(__file__), "seed_contacts.json")
try:
    with open(SEED_FILE, "r") as f:
        contacts = json.load(f)
except Exception as e:
    contacts = []
    print(f"Error loading seed file: {e}")

@app.middleware("http")
async def rate_limit_and_failures(request: Request, call_next):
    # Skip middleware for health checks
    if request.url.path == "/health":
        return await call_next(request)
        
    # 1. Simulate 5% Random Failures (HTTP 500 / 503)
    if random.random() < 0.05:
        failure_code = random.choice([500, 503])
        return JSONResponse(
            status_code=failure_code,
            content={"detail": f"Simulated Server Error ({failure_code}) - Client Integration Failure Test"}
        )
        
    # 2. Simulate Rate Limiting (HTTP 429)
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Initialize history list
    if client_ip not in request_history:
        request_history[client_ip] = []
        
    # Filter timestamps to keep only those within current window
    request_history[client_ip] = [t for t in request_history[client_ip] if now - t < RATE_LIMIT_WINDOW]
    
    # Check rate limit
    if len(request_history[client_ip]) >= RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too Many Requests - Simulated SaaS Rate Limit Breached"},
            headers={"Retry-After": "1"}
        )
        
    request_history[client_ip].append(now)
    
    # 3. Process the request
    return await call_next(request)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "contacts_loaded": len(contacts),
        "timestamp": time.time()
    }

@app.get("/api/v1/contacts")
def get_contacts(limit: int = 50, offset: int = 0):
    total = len(contacts)
    paged_contacts = contacts[offset : offset + limit]
    
    next_offset = offset + limit
    next_page = f"/api/v1/contacts?limit={limit}&offset={next_offset}" if next_offset < total else None
    
    return {
        "contacts": paged_contacts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_page": next_page
    }
