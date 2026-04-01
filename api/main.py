"""
AlphaFMC FastAPI — optional REST API layer.

Run:
    uvicorn api.main:app --reload
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.store import (
    get_all_records, get_portco_records, get_latest_records,
    upsert_record, init_db
)
from pipeline.extractor import extract_pdf

app = FastAPI(
    title="AlphaFMC Portfolio API",
    description="Private markets portfolio data pipeline REST API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok", "service": "alphafmc-api"}


# ── Portfolio endpoints ───────────────────────────────────────────────────────

@app.get("/portfolio/latest", tags=["Portfolio"])
def portfolio_latest():
    """Return the latest quarter financial record for each portco."""
    records = get_latest_records()
    if not records:
        raise HTTPException(status_code=404, detail="No data found")
    return records


@app.get("/portfolio/all", tags=["Portfolio"])
def portfolio_all(portco_id: Optional[str] = Query(None)):
    """Return all financial records, optionally filtered by portco_id."""
    if portco_id:
        records = get_portco_records(portco_id)
    else:
        records = get_all_records()
    return records


@app.get("/portfolio/{portco_id}", tags=["Portfolio"])
def portco_detail(portco_id: str):
    """Return all records for a specific portfolio company."""
    records = get_portco_records(portco_id.upper())
    if not records:
        raise HTTPException(status_code=404, detail=f"Portco '{portco_id}' not found")
    return records


# ── Extraction endpoint ───────────────────────────────────────────────────────

@app.post("/extract", tags=["Extraction"])
async def extract_document(file: UploadFile = File(...)):
    """
    Upload a PDF and run the extraction pipeline.
    Returns the extracted and normalised financial record.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        record = extract_pdf(tmp_path)
        record["source_pdf"] = file.filename
        upsert_record(record)
        return {
            "status": "success",
            "record": record,
            "confidence": record.get("extraction_confidence", 1.0),
            "low_confidence_flag": record.get("extraction_confidence", 1.0) < 0.8,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── Report endpoint ───────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    period: str = "Q4 2024"
    use_ai: bool = False


@app.post("/reports/generate", tags=["Reports"])
def generate_report(req: ReportRequest):
    """Trigger LP report generation for a given period."""
    from reports.generator import build_lp_report
    try:
        out_path = build_lp_report(period=req.period, use_ai=req.use_ai)
        return {"status": "success", "output_path": str(out_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
