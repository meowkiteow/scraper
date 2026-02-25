"""
FastAPI Backend — Cold Email SaaS
Main entrypoint. Run with: uvicorn main:app --reload --port 8000
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from db import init_db
from campaign_worker import start_worker as start_campaign_worker, is_worker_running
from warmup_worker import start_warmup, is_warmup_running

# Import route modules
from routes import auth, accounts, campaigns, steps, leads, inbox, analytics, billing, prospector


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    # Startup
    init_db()
    print("✅ Database initialized")

    start_campaign_worker()
    print("🚀 Campaign sending worker started")

    start_warmup()
    print("🔥 Warmup worker started")

    yield

    # Shutdown
    from campaign_worker import stop_worker
    from warmup_worker import stop_warmup as stop_warmup_worker
    stop_worker()
    stop_warmup_worker()
    print("Workers stopped.")


app = FastAPI(
    title="Cold Email SaaS API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routes
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(steps.router, prefix="/api/campaigns", tags=["steps"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(inbox.router, prefix="/api/inbox", tags=["inbox"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(prospector.router, prefix="/api/prospector", tags=["prospector"])


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "campaign_worker": is_worker_running(),
        "warmup_worker": is_warmup_running(),
    }
