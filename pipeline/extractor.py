"""
Claude-powered PDF → structured KPI extractor.

Usage:
    from pipeline.extractor import extract_pdf
    record = extract_pdf("data/demo_pdfs/NXH_2024_Q3.pdf")
"""

import json
from datetime import datetime
from pathlib import Path

import pdfplumber

from pipeline.normaliser import normalise
from pipeline import ai_client

EXTRACTION_PROMPT = """You are a financial data extraction assistant for a private equity firm.

Extract all financial KPIs from the provided quarterly financial report PDF text and return them as a JSON object.

Return ONLY a valid JSON object with these exact fields (all numeric values in thousands):
{
  "portco_id": "<3-letter code>",
  "portco_name": "<company name>",
  "period": "<e.g. Q3 2024>",
  "currency": "<GBP or EUR>",
  "revenue": <number>,
  "gross_profit": <number>,
  "ebitda": <number>,
  "ebit": <number>,
  "net_income": <number>,
  "cash": <number>,
  "total_debt": <number>,
  "net_debt": <number>,
  "total_assets": <number>,
  "headcount": <integer>,
  "revenue_growth_yoy": <percentage as float, e.g. 12.5 for 12.5%>,
  "ebitda_margin": <percentage as float>,
  "net_debt_ebitda": <ratio as float, e.g. 3.2>,
  "vs_budget_revenue_pct": <variance as float, e.g. -5.2 for 5.2% below budget>,
  "vs_budget_ebitda_pct": <variance as float>,
  "extraction_confidence": <float between 0 and 1>
}

If a field cannot be found or computed, use null. Set extraction_confidence based on how clearly the data was present in the document (1.0 = all fields clearly present, 0.5 = many fields missing or ambiguous).

PDF TEXT:
{pdf_text}
"""


def _extract_text(pdf_path: Path) -> str:
    """Extract raw text from PDF using pdfplumber."""
    text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


def extract_pdf(pdf_path: str | Path, api_key: str | None = None,
                filename_hint: str | None = None) -> dict:
    """
    Extract structured KPIs from a PDF using the configured AI provider.

    filename_hint: original filename when pdf_path is a temp file (e.g. from upload).
    Falls back to regex/heuristic extraction if AI call fails.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_text = _extract_text(pdf_path)
    hint_path = Path(filename_hint) if filename_hint else pdf_path

    # Try AI provider (Anthropic or AlphaGPT, per config.properties)
    try:
        raw = _ai_extract(pdf_text)
        raw["source_pdf"] = str(hint_path)
        raw["extracted_at"] = datetime.utcnow().isoformat()
        return normalise(raw)
    except Exception as e:
        print(f"[extractor] AI extraction error ({ai_client.active_provider()}): {e}. Falling back to heuristic.")

    # Fallback: heuristic extraction from PDF text content + filename hint
    raw = _heuristic_extract(pdf_text, hint_path)
    raw["source_pdf"] = str(hint_path)
    raw["extracted_at"] = datetime.utcnow().isoformat()
    return normalise(raw)


def _ai_extract(pdf_text: str) -> dict:
    """Call the configured AI provider to extract structured KPIs."""
    import re as _re
    prompt = EXTRACTION_PROMPT.replace("{pdf_text}", pdf_text[:8000])
    content = ai_client.complete(prompt, max_tokens=1024)

    # Strip markdown code fences if present
    if "```" in content:
        m = _re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
        if m:
            content = m.group(1)

    # Extract first JSON object if surrounded by prose
    m = _re.search(r"\{[\s\S]+\}", content)
    if m:
        content = m.group(0)

    return json.loads(content)


def _heuristic_extract(text: str, pdf_path: Path) -> dict:
    """
    Heuristic extraction by parsing the structured text from our PDF generator.
    Reliable for our own generated PDFs.
    """
    import re

    def _find_num(pattern: str, text: str, default=0.0) -> float:
        m = re.search(pattern, text)
        if not m:
            return default
        val_str = m.group(1).replace(",", "")
        try:
            return float(val_str)
        except ValueError:
            return default

    def _find_pct(pattern: str, text: str) -> float:
        m = re.search(pattern, text)
        if not m:
            return 0.0
        val_str = m.group(1).replace("+", "")
        try:
            return float(val_str)
        except ValueError:
            return 0.0

    # Known portco names and their IDs (for text-based matching)
    portco_names = {
        "NXH": "Nexora Health", "CLG": "Caliber Logistics",
        "PRD": "Prism Digital",  "VRE": "Verdant Energy",
        "HLC": "Halo Consumer",
    }
    name_to_id = {v: k for k, v in portco_names.items()}

    # 1. Try to extract portco name and period from PDF text content
    portco_name = None
    for name in portco_names.values():
        if name in text:
            portco_name = name
            break
    portco_id = name_to_id.get(portco_name, "UNK") if portco_name else "UNK"

    period_m = re.search(r"(Q[1-4]\s+20\d{2})", text)
    if period_m:
        period  = period_m.group(1).replace(" ", " ")
        quarter = period.split()[0]
        year    = int(period.split()[1])
    else:
        # 2. Fall back to structured filename: PORTCO_YEAR_Q.pdf
        stem  = pdf_path.stem
        parts = stem.split("_")
        if len(parts) >= 3 and parts[0] in portco_names:
            portco_id   = parts[0]
            portco_name = portco_names[portco_id]
            year        = int(parts[1]) if parts[1].isdigit() else 0
            quarter     = parts[2]
        else:
            year    = 0
            quarter = "Q?"
        period = f"{quarter} {year}"

    # Determine currency from text
    currency = "GBP" if "£" in text or "GBP" in text else "EUR"

    sym_re = r"[£€]"
    num_re = r"([\d,]+(?:\.\d+)?)"

    # Extract financial figures
    revenue      = _find_num(rf"Revenue\s+[£€]{num_re}", text)
    gross_profit = _find_num(rf"Gross Profit\s+[£€]{num_re}", text)
    ebitda       = _find_num(rf"EBITDA\s+[£€]{num_re}", text)
    ebit         = _find_num(rf"EBIT\s+[£€]{num_re}", text)
    net_income   = _find_num(rf"Net Income\s+[£€]{num_re}", text)
    cash         = _find_num(rf"Cash & Equivalents\s+[£€]{num_re}", text)
    total_debt   = _find_num(rf"Total Debt\s+[£€]{num_re}", text)
    net_debt     = _find_num(rf"Net Debt\s+[£€]{num_re}", text)
    total_assets = _find_num(rf"Total Assets\s+[£€]{num_re}", text)

    # Headcount
    hc_m = re.search(r"Headcount\s+([\d,]+)", text)
    headcount = int(hc_m.group(1).replace(",", "")) if hc_m else 0

    # KPI percentages
    rev_growth = _find_pct(r"Rev Growth YoY\s+([+-]?[\d.]+)%", text)
    ebitda_margin = _find_pct(r"EBITDA Margin\s+([+-]?[\d.]+)%", text)
    nd_ebitda_m = re.search(r"Net Debt / EBITDA\s+([\d.]+)x", text)
    nd_ebitda = float(nd_ebitda_m.group(1)) if nd_ebitda_m else 0.0

    # Budget variances
    vs_budget_rev = _find_pct(r"Revenue\s+[£€][\d,]+\s+([+-]?[\d.]+)%", text)
    vs_budget_ebitda = _find_pct(r"EBITDA\s+[£€][\d,]+\s+([+-]?[\d.]+)%", text)

    portco_name = portco_name or portco_names.get(portco_id, portco_id)

    confidence = 0.95 if revenue > 0 else 0.5

    return {
        "portco_id":   portco_id,
        "portco_name": portco_name,
        "period":      period,
        "quarter":     quarter,
        "year":        year,
        "currency":    currency,
        "revenue":     revenue,
        "gross_profit":    gross_profit,
        "ebitda":          ebitda,
        "ebit":            ebit,
        "net_income":      net_income,
        "cash":            cash,
        "total_debt":      total_debt,
        "net_debt":        net_debt,
        "total_assets":    total_assets,
        "headcount":       headcount,
        "revenue_growth_yoy":    rev_growth,
        "ebitda_margin":         ebitda_margin,
        "net_debt_ebitda":       nd_ebitda,
        "vs_budget_revenue_pct": vs_budget_rev,
        "vs_budget_ebitda_pct":  vs_budget_ebitda,
        "extraction_confidence": confidence,
    }


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "data/demo_pdfs/NXH_2024_Q4.pdf"
    result = extract_pdf(pdf)
    print(json.dumps(result, indent=2))
