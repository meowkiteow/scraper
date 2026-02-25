"""
Prospector routes — Google Maps business scraping with background jobs.
"""

import csv
import io
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from db import get_db, User, Lead, get_plan_limits
from auth import get_current_user

router = APIRouter()

# In-memory job storage (for production, use Redis or DB)
_jobs = {}

# Directories
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(_BACKEND_DIR, "scraped_data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "prospector_history.json")
SCRAPER_RUNNER = os.path.join(_BACKEND_DIR, "scraper_runner.py")


def _load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


class SearchRequest(BaseModel):
    query: str
    location: str
    limit: int = 20
    extract_emails: bool = True
    extract_phone: bool = True
    extract_website: bool = True
    extract_reviews: bool = True


class ImportRequest(BaseModel):
    results: list[dict]


@router.post("/search")
def start_search(req: SearchRequest, user: User = Depends(get_current_user)):
    # Collect previously-scraped business names for this query+location
    history = _load_history()
    skip_names = set()
    q_lower = req.query.strip().lower()
    loc_lower = req.location.strip().lower()
    for entry in history:
        if (entry.get("user_id") == user.id
                and entry.get("query", "").strip().lower() == q_lower
                and entry.get("location", "").strip().lower() == loc_lower):
            for r in entry.get("results", []):
                name = r.get("name", "").strip()
                if name:
                    skip_names.add(name)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "user_id": user.id,
        "status": "running",
        "query": req.query,
        "location": req.location,
        "limit": req.limit,
        "results": [],
        "started_at": datetime.utcnow().isoformat(),
        "progress": "Starting scraper...",
        "stop_requested": False,
        "options": {
            "extract_emails": req.extract_emails,
            "extract_phone": req.extract_phone,
            "extract_website": req.extract_website,
            "extract_reviews": req.extract_reviews,
        },
    }

    thread = threading.Thread(
        target=_run_scrape,
        args=(job_id, req.query, req.location, min(req.limit, 100),
              req.extract_emails, req.extract_phone, req.extract_website,
              req.extract_reviews, list(skip_names)),
        daemon=True
    )
    thread.start()

    skipped_info = f" (skipping {len(skip_names)} already scraped)" if skip_names else ""
    return {"job_id": job_id, "status": "running", "skipping": len(skip_names)}


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str, user: User = Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job or job["user_id"] != user.id:
        raise HTTPException(404, "Job not found")
    job["stop_requested"] = True
    job["status"] = "stopping"
    job["progress"] = "Stop requested, finishing current business..."
    # Create stop flag file for the subprocess
    stop_path = os.path.join(DATA_DIR, f"stop_{job_id}.flag")
    try:
        with open(stop_path, "w") as f:
            f.write("stop")
    except Exception:
        pass
    return {"status": "stopping", "results_so_far": len(job["results"])}


@router.get("/jobs/{job_id}/results")
def get_job_results(job_id: str, user: User = Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job or job["user_id"] != user.id:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job["id"],
        "status": job["status"],
        "progress": job.get("progress", ""),
        "results": job["results"],
        "total": len(job["results"]),
        "query": job["query"],
        "location": job["location"],
    }


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user: User = Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job or job["user_id"] != user.id:
        raise HTTPException(404, "Job not found")
    del _jobs[job_id]
    return {"deleted": True}


@router.get("/jobs")
def list_jobs(user: User = Depends(get_current_user)):
    user_jobs = [
        {"id": j["id"], "status": j["status"], "query": j["query"],
         "location": j["location"], "total": len(j["results"]),
         "started_at": j["started_at"], "options": j.get("options", {})}
        for j in _jobs.values() if j["user_id"] == user.id
    ]
    return {"jobs": sorted(user_jobs, key=lambda x: x["started_at"], reverse=True)[:50]}


# ── History ──────────────────────────────────────────────────

@router.get("/history")
def get_history(user: User = Depends(get_current_user)):
    history = _load_history()
    user_history = [h for h in history if h.get("user_id") == user.id]
    total_leads = sum(h.get("total", 0) for h in user_history)
    return {
        "searches": user_history[-50:][::-1],
        "total_searches": len(user_history),
        "total_leads": total_leads,
    }


@router.delete("/history")
def clear_history(user: User = Depends(get_current_user)):
    history = _load_history()
    history = [h for h in history if h.get("user_id") != user.id]
    _save_history(history)
    return {"cleared": True}


@router.get("/history/{search_id}/csv")
def download_history_csv(search_id: str, user: User = Depends(get_current_user)):
    history = _load_history()
    entry = next((h for h in history if h.get("id") == search_id and h.get("user_id") == user.id), None)
    if not entry:
        raise HTTPException(404, "Search not found")

    results = entry.get("results", [])
    if not results:
        raise HTTPException(404, "No results")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)
    content = output.getvalue().encode("utf-8-sig")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment;filename=leads_{entry['query']}_{entry['location']}.csv"}
    )


# ── Import ───────────────────────────────────────────────────

@router.post("/import")
def import_results(req: ImportRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Import prospector results as leads."""
    limits = get_plan_limits(user.plan)
    current = db.query(Lead).filter(Lead.user_id == user.id).count()

    added = 0
    skipped = 0

    for result in req.results:
        if current + added >= limits["leads"]:
            break

        emails_str = result.get("Emails", result.get("email", ""))
        emails = []
        if emails_str and emails_str not in ("None found", "N/A", ""):
            emails = [e.strip() for e in emails_str.split(",") if "@" in e]

        if not emails:
            skipped += 1
            continue

        for email in emails:
            email = email.strip().lower()
            existing = db.query(Lead).filter(Lead.user_id == user.id, Lead.email == email).first()
            if existing:
                skipped += 1
                continue

            lead = Lead(
                user_id=user.id,
                email=email,
                first_name="",
                last_name="",
                company=result.get("Name", result.get("name", "")),
                phone=result.get("Phone", result.get("phone", "")),
                website=result.get("Website", result.get("website", "")),
                source="prospector",
                tags=["maps_scrape"],
            )
            db.add(lead)
            added += 1

    db.commit()
    return {"added": added, "skipped": skipped}


# ── CSV Export for current results ──

@router.post("/export-csv")
def export_csv(req: ImportRequest, user: User = Depends(get_current_user)):
    results = req.results
    if not results:
        raise HTTPException(400, "No results to export")

    output = io.StringIO()
    fields = ["name", "phone", "website", "email", "rating", "reviews"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)
    content = output.getvalue().encode("utf-8-sig")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment;filename=leads_export.csv"}
    )


# ── Background scraper (subprocess-based) ────────────────────


def _read_json_safe(path):
    """Read a JSON file, returning None if it doesn't exist or is corrupted."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cleanup_job_files(job_id):
    """Remove temporary files for a job."""
    for prefix in ("config_", "output_", "status_", "stop_"):
        ext = ".json" if prefix != "stop_" else ".flag"
        path = os.path.join(DATA_DIR, f"{prefix}{job_id}{ext}")
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def _run_scrape(job_id, query, location, limit, extract_emails, extract_phone, extract_website, extract_reviews, skip_names=None):
    """
    Run the scraper as a subprocess with its own Python process and event loop.
    This avoids the NotImplementedError that occurs when Playwright's async API
    is used inside a background thread on Windows.
    """
    output_path = os.path.join(DATA_DIR, f"output_{job_id}.json")
    status_path = os.path.join(DATA_DIR, f"status_{job_id}.json")
    config_path = os.path.join(DATA_DIR, f"config_{job_id}.json")
    stop_path = os.path.join(DATA_DIR, f"stop_{job_id}.flag")

    try:
        # Write config for the subprocess
        config = {
            "keyword": query,
            "location": location,
            "limit": limit,
            "extract_emails": extract_emails,
            "extract_phone": extract_phone,
            "extract_website": extract_website,
            "extract_reviews": extract_reviews,
            "output_path": output_path,
            "status_path": status_path,
            "stop_path": stop_path,
            "skip_names": skip_names or [],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        # Launch the scraper subprocess
        proc = subprocess.Popen(
            [sys.executable, SCRAPER_RUNNER, config_path],
            cwd=_BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Poll for results until subprocess finishes
        while proc.poll() is None:
            time.sleep(1.5)

            # Check if stop was requested via the API
            if job_id in _jobs and _jobs[job_id].get("stop_requested"):
                # Create stop flag
                try:
                    with open(stop_path, "w") as f:
                        f.write("stop")
                except Exception:
                    pass

            # Read latest results
            results_data = _read_json_safe(output_path)
            if results_data and isinstance(results_data, list):
                _jobs[job_id]["results"] = results_data

            # Read latest status
            status_data = _read_json_safe(status_path)
            if status_data and isinstance(status_data, dict):
                _jobs[job_id]["progress"] = status_data.get("progress", "")

        # Process exited — read final data
        _, stderr_out = proc.communicate(timeout=5)

        results_data = _read_json_safe(output_path)
        if results_data and isinstance(results_data, list):
            _jobs[job_id]["results"] = results_data

        status_data = _read_json_safe(status_path)

        if proc.returncode != 0 and not _jobs[job_id]["results"]:
            err = stderr_out.decode("utf-8", errors="replace").strip()
            # Get last meaningful line from stderr
            err_lines = [l for l in err.split("\n") if l.strip()]
            short_err = err_lines[-1] if err_lines else "Scraper process failed"
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["progress"] = f"Error: {short_err}"
        else:
            total = len(_jobs[job_id]["results"])
            was_stopped = _jobs[job_id].get("stop_requested", False)
            _jobs[job_id]["status"] = "completed"

            if status_data and isinstance(status_data, dict):
                _jobs[job_id]["progress"] = status_data.get("progress", f"Done! Found {total} businesses.")
            else:
                _jobs[job_id]["progress"] = f"{'Stopped' if was_stopped else 'Done'}! Found {total} businesses."

            # Save to history
            history = _load_history()
            history.append({
                "id": job_id,
                "user_id": _jobs[job_id]["user_id"],
                "query": query,
                "location": location,
                "total": total,
                "timestamp": datetime.utcnow().isoformat(),
                "results": _jobs[job_id]["results"],
            })
            _save_history(history)

    except Exception as e:
        import traceback
        traceback.print_exc()
        if job_id in _jobs:
            total = len(_jobs[job_id]["results"])
            if total > 0:
                _jobs[job_id]["status"] = "completed"
                _jobs[job_id]["progress"] = f"Stopped with {total} results."
                history = _load_history()
                history.append({
                    "id": job_id,
                    "user_id": _jobs[job_id]["user_id"],
                    "query": query,
                    "location": location,
                    "total": total,
                    "timestamp": datetime.utcnow().isoformat(),
                    "results": _jobs[job_id]["results"],
                })
                _save_history(history)
            else:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["progress"] = f"Error: {str(e) or repr(e)}"
    finally:
        _cleanup_job_files(job_id)
