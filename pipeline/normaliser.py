"""
Normaliser — maps raw Claude extraction output to the standard schema.
"""

from datetime import datetime
from typing import Any


REQUIRED_FIELDS = [
    "portco_id", "portco_name", "period", "currency",
    "revenue", "gross_profit", "ebitda", "ebit", "net_income",
    "cash", "total_debt", "net_debt",
    "headcount", "revenue_growth_yoy", "ebitda_margin",
    "net_debt_ebitda", "vs_budget_revenue_pct", "vs_budget_ebitda_pct",
]


def normalise(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Takes raw extracted dict (from Claude or direct parse) and
    returns a clean record conforming to the extraction schema.
    Missing numeric fields default to 0.0. Confidence is passed through.
    """
    out: dict[str, Any] = {}

    for field in REQUIRED_FIELDS:
        val = raw.get(field)
        STRING_FIELDS = ("portco_id", "portco_name", "period", "currency")
        if val is None:
            if field in STRING_FIELDS:
                out[field] = ""
            elif field == "headcount":
                out[field] = 0
            else:
                out[field] = 0.0
        elif field == "headcount":
            out[field] = int(float(val))
        elif field in ("portco_id", "portco_name", "period", "currency"):
            out[field] = str(val).strip()
        else:
            out[field] = float(val)

    # Derive portco_id from name if AI omitted it
    if not out.get("portco_id"):
        _name_to_id = {
            "Nexora Health": "NXH", "Caliber Logistics": "CLG",
            "Prism Digital": "PRD", "Verdant Energy": "VRE",
            "Halo Consumer": "HLC",
        }
        out["portco_id"] = _name_to_id.get(out.get("portco_name", ""), "UNK")

    # Derived / enrichment fields
    out["extraction_confidence"] = float(raw.get("extraction_confidence", 1.0))
    out["extracted_at"] = raw.get("extracted_at") or datetime.utcnow().isoformat()

    # Optional passthrough
    for opt in ("quarter", "year", "sector", "geography", "stage", "symbol",
                "total_assets", "source_pdf", "raw_extraction"):
        if opt in raw:
            out[opt] = raw[opt]

    # Validate confidence threshold
    if out["extraction_confidence"] < 0.8:
        out["_low_confidence_flag"] = True

    return out
