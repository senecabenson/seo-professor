"""
Local dev server for SEO Professor.

Exposes the same API surface as the Vercel + Trigger.dev production setup:
  POST /api/audit          → start audit job, returns { run_id }
  GET  /api/status/:run_id → poll job status + output
  GET  /                   → serve app.html

Run with:
  uvicorn src.web:app --reload --port 8080
  # or via entry point:
  seo-web
"""

import asyncio
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from src.audit import (
    run_audit,
    validate_url,
    extract_domain,
    store_results,
)
from src.ai_analyzer import format_for_analysis, analyze_with_claude
from src.report_generator import generate_report

# ─── App ────────────────────────────────────────────────
app = FastAPI(title="SEO Professor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

# ─── Job store ──────────────────────────────────────────
@dataclass
class Job:
    run_id: str
    url: str
    # Trigger.dev-compatible status strings so the frontend works unchanged
    status: str = "QUEUED"       # QUEUED → EXECUTING → COMPLETED | FAILED
    output: dict | None = None
    error: dict | None = None

JOBS: dict[str, Job] = {}


# ─── Routes ─────────────────────────────────────────────
@app.get("/")
def serve_frontend():
    return FileResponse(TEMPLATES_DIR / "app.html", media_type="text/html")


@app.post("/api/audit")
def start_audit(body: dict):
    raw_url = body.get("url", "").strip()
    if not raw_url:
        return JSONResponse({"error": "url is required"}, status_code=400)

    try:
        url = validate_url(raw_url)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    max_pages  = int(body.get("max_pages", 50))
    single_page = bool(body.get("single_page", False))

    run_id = str(uuid.uuid4())
    job = Job(run_id=run_id, url=url)
    JOBS[run_id] = job

    t = threading.Thread(
        target=_run_job,
        args=(job, max_pages, single_page),
        daemon=True,
    )
    t.start()

    return {"run_id": run_id}


@app.get("/api/report/{run_id}")
def download_report(run_id: str):
    job = JOBS.get(run_id)
    if not job or job.status != "COMPLETED":
        return JSONResponse({"error": "report not ready"}, status_code=404)
    pdf_path = job.output.get("pdf_url", "")
    if not Path(pdf_path).exists():
        return JSONResponse({"error": "PDF file not found"}, status_code=404)
    domain = job.output.get("domain", "report")
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"{domain}-audit.pdf")


@app.get("/api/status/{run_id}")
def get_status(run_id: str):
    job = JOBS.get(run_id)
    if not job:
        return JSONResponse({"error": "run not found"}, status_code=404)
    return {
        "status": job.status,
        "output": job.output,
        "error":  job.error,
    }


# ─── Background job ─────────────────────────────────────
def _run_job(job: Job, max_pages: int, single_page: bool):
    try:
        job.status = "EXECUTING"
        domain = extract_domain(job.url)

        # Phase 1: crawl + audit
        audit_result = asyncio.run(
            run_audit(job.url, single_page=single_page, max_pages=max_pages)
        )
        aggregated = audit_result["aggregated"]
        pages      = audit_result["pages"]

        # Phase 2: AI analysis
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")

        analysis = format_for_analysis(aggregated, domain)
        ai_analysis = analyze_with_claude(analysis["prompt"], api_key)

        # Phase 3: generate PDF
        out_dir = Path(".tmp/reports") / job.run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(out_dir / f"{domain}-audit.pdf")
        generate_report(aggregated, ai_analysis, pdf_path)

        # Phase 4: store in Supabase (best-effort — skip if no DB creds)
        pdf_url = pdf_path  # local fallback; overwritten if Supabase succeeds
        try:
            pdf_url = store_results(domain, aggregated, pages, ai_analysis, pdf_path)
        except Exception as db_err:
            print(f"[web] Supabase skipped: {db_err}")

        job.output = {
            "domain":      domain,
            "date":        datetime.now().strftime("%B %d, %Y"),
            "pdf_url":     pdf_url,
            "aggregated":  aggregated,
            "ai_analysis": ai_analysis,
        }
        job.status = "COMPLETED"

    except Exception as e:
        job.status = "FAILED"
        job.error  = {"message": str(e)}
        print(f"[web] Job {job.run_id} failed: {e}")


# ─── Entry point ─────────────────────────────────────────
def start():
    import uvicorn
    uvicorn.run("src.web:app", host="127.0.0.1", port=8080, reload=True)
