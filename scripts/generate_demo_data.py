"""
AlphaFMC — Demo Data Generator
Generates 5 fictional portcos with 8 quarters of synthetic financials
and produces realistic-looking PDF financial reports for each.
"""

import os
import sys
import json
import random
import math
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas

# ── Brand colours ──────────────────────────────────────────────────────────────
NAVY  = colors.HexColor("#0A1628")
GOLD  = colors.HexColor("#C9A84C")
LIGHT = colors.HexColor("#F5F6FA")
GREY  = colors.HexColor("#8A94A6")
WHITE = colors.white

# ── Portco definitions ─────────────────────────────────────────────────────────
PORTCOS = [
    {
        "portco_id":   "NXH",
        "portco_name": "Nexora Health",
        "sector":      "Healthcare",
        "geography":   "UK",
        "stage":       "Growth",
        "currency":    "GBP",
        "symbol":      "£",
        # Base financials (£000s) for Q1 2023
        "base_revenue":     12_500,
        "gross_margin":     0.62,
        "ebitda_margin":    0.24,
        "base_headcount":   185,
        "base_total_debt":  18_000,
        "base_cash":        4_200,
        "revenue_growth_q": 0.042,   # quarterly growth rate
        "headcount_growth": 0.025,
    },
    {
        "portco_id":   "CLG",
        "portco_name": "Caliber Logistics",
        "sector":      "Industrials",
        "geography":   "Germany",
        "stage":       "Buyout",
        "currency":    "EUR",
        "symbol":      "€",
        "base_revenue":     28_000,
        "gross_margin":     0.38,
        "ebitda_margin":    0.17,
        "base_headcount":   420,
        "base_total_debt":  52_000,
        "base_cash":        6_800,
        "revenue_growth_q": 0.028,
        "headcount_growth": 0.010,
    },
    {
        "portco_id":   "PRD",
        "portco_name": "Prism Digital",
        "sector":      "TMT",
        "geography":   "UK",
        "stage":       "Growth",
        "currency":    "GBP",
        "symbol":      "£",
        "base_revenue":     8_200,
        "gross_margin":     0.74,
        "ebitda_margin":    0.19,
        "base_headcount":   130,
        "base_total_debt":  9_500,
        "base_cash":        3_100,
        "revenue_growth_q": 0.055,
        "headcount_growth": 0.035,
    },
    {
        "portco_id":   "VRE",
        "portco_name": "Verdant Energy",
        "sector":      "Renewables",
        "geography":   "Spain",
        "stage":       "Infrastructure",
        "currency":    "EUR",
        "symbol":      "€",
        "base_revenue":     19_400,
        "gross_margin":     0.55,
        "ebitda_margin":    0.42,
        "base_headcount":   210,
        "base_total_debt":  88_000,
        "base_cash":        12_500,
        "revenue_growth_q": 0.018,
        "headcount_growth": 0.008,
    },
    {
        "portco_id":   "HLC",
        "portco_name": "Halo Consumer",
        "sector":      "Consumer",
        "geography":   "France",
        "stage":       "Buyout",
        "currency":    "EUR",
        "symbol":      "€",
        "base_revenue":     34_600,
        "gross_margin":     0.44,
        "ebitda_margin":    0.15,
        "base_headcount":   580,
        "base_total_debt":  64_000,
        "base_cash":        8_900,
        "revenue_growth_q": 0.022,
        "headcount_growth": 0.012,
    },
]

QUARTERS = [
    ("Q1", 2023), ("Q2", 2023), ("Q3", 2023), ("Q4", 2023),
    ("Q1", 2024), ("Q2", 2024), ("Q3", 2024), ("Q4", 2024),
]


def _noise(base: float, pct: float = 0.04) -> float:
    """Add small random noise."""
    return base * (1 + random.uniform(-pct, pct))


def generate_financials(portco: dict) -> list[dict]:
    """Generate 8 quarters of financials for a portco."""
    random.seed(portco["portco_id"])  # reproducible

    records = []
    rev       = portco["base_revenue"]
    headcount = portco["base_headcount"]
    total_debt = portco["base_total_debt"]
    cash       = portco["base_cash"]

    for i, (q, yr) in enumerate(QUARTERS):
        # Revenue growth with some seasonality
        seasonal = 1.0
        if q == "Q4":
            seasonal = 1.06  # year-end boost
        elif q == "Q1":
            seasonal = 0.96  # Q1 dip

        rev = rev * (1 + portco["revenue_growth_q"]) * seasonal
        rev = _noise(rev, 0.025)

        gp       = rev * _noise(portco["gross_margin"], 0.02)
        ebitda   = rev * _noise(portco["ebitda_margin"], 0.03)
        ebit     = ebitda * _noise(0.82, 0.02)
        net_inc  = ebit  * _noise(0.70, 0.03)

        # Balance sheet
        cash       = _noise(cash * 1.005, 0.05)
        total_debt = total_debt * _noise(0.998, 0.01)  # slow paydown
        net_debt   = total_debt - cash
        total_assets = total_debt * 1.65 + cash

        headcount = int(headcount * (1 + portco["headcount_growth"]) * _noise(1.0, 0.01))

        # YoY growth (only computable from Q1 2024 onwards, else approximate)
        rev_growth_yoy = portco["revenue_growth_q"] * 4 * _noise(1.0, 0.15)

        ebitda_margin  = ebitda / rev
        nd_ebitda      = net_debt / (ebitda * 4)  # annualised

        # Budget variance: actuals slightly miss/beat budget
        budget_miss = random.uniform(-0.12, 0.08)
        vs_budget_rev    = budget_miss * _noise(1.0, 0.3)
        vs_budget_ebitda = (budget_miss - 0.02) * _noise(1.0, 0.4)

        records.append({
            "portco_id":           portco["portco_id"],
            "portco_name":         portco["portco_name"],
            "sector":              portco["sector"],
            "geography":           portco["geography"],
            "stage":               portco["stage"],
            "period":              f"{q} {yr}",
            "quarter":             q,
            "year":                yr,
            "currency":            portco["currency"],
            "symbol":              portco["symbol"],
            "revenue":             round(rev, 1),
            "gross_profit":        round(gp, 1),
            "ebitda":              round(ebitda, 1),
            "ebit":                round(ebit, 1),
            "net_income":          round(net_inc, 1),
            "cash":                round(cash, 1),
            "total_debt":          round(total_debt, 1),
            "net_debt":            round(net_debt, 1),
            "total_assets":        round(total_assets, 1),
            "headcount":           headcount,
            "revenue_growth_yoy":  round(rev_growth_yoy * 100, 1),
            "ebitda_margin":       round(ebitda_margin * 100, 1),
            "net_debt_ebitda":     round(nd_ebitda, 2),
            "vs_budget_revenue_pct":  round(vs_budget_rev * 100, 1),
            "vs_budget_ebitda_pct":   round(vs_budget_ebitda * 100, 1),
        })

    return records


# ── PDF generation ─────────────────────────────────────────────────────────────

def _fmt(val: float, symbol: str = "", decimals: int = 0) -> str:
    if decimals == 0:
        return f"{symbol}{val:,.0f}"
    return f"{symbol}{val:,.{decimals}f}"


def _pct(val: float, decimals: int = 1) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.{decimals}f}%"


def _rag_color(rec: dict) -> colors.Color:
    nd = rec["net_debt_ebitda"]
    em_vs_budget = rec["vs_budget_ebitda_pct"]
    if nd > 5 or em_vs_budget < -10:
        return colors.HexColor("#C0392B")
    if nd > 4 or em_vs_budget < -5:
        return colors.HexColor("#E67E22")
    return colors.HexColor("#27AE60")


class NumberedCanvas(canvas.Canvas):
    """Canvas that adds page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_footer(self, page_count):
        self.saveState()
        self.setFillColor(GREY)
        self.setFont("Helvetica", 7)
        page_num = self._saved_page_states.index(
            {k: v for k, v in self.__dict__.items() if k in self._saved_page_states[0]}
        ) if self._saved_page_states else 1
        self.restoreState()


def build_pdf(rec: dict, out_path: Path) -> None:
    """Build a single quarterly financial report PDF."""
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=15*mm,
        bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()
    # Custom styles
    h1 = ParagraphStyle("H1", parent=styles["Normal"],
                         fontName="Helvetica-Bold", fontSize=20,
                         textColor=WHITE, leading=26)
    h2 = ParagraphStyle("H2", parent=styles["Normal"],
                         fontName="Helvetica-Bold", fontSize=13,
                         textColor=NAVY, leading=18, spaceAfter=4)
    h3 = ParagraphStyle("H3", parent=styles["Normal"],
                         fontName="Helvetica-Bold", fontSize=10,
                         textColor=NAVY, leading=14, spaceAfter=2)
    body = ParagraphStyle("Body", parent=styles["Normal"],
                          fontName="Helvetica", fontSize=9,
                          textColor=colors.HexColor("#2C3E50"), leading=13)
    small = ParagraphStyle("Small", parent=styles["Normal"],
                            fontName="Helvetica", fontSize=7.5,
                            textColor=GREY, leading=11)
    label = ParagraphStyle("Label", parent=styles["Normal"],
                            fontName="Helvetica-Bold", fontSize=8,
                            textColor=GREY, leading=11)
    num_r = ParagraphStyle("NumR", parent=styles["Normal"],
                            fontName="Helvetica", fontSize=9,
                            textColor=colors.HexColor("#2C3E50"),
                            alignment=TA_RIGHT, leading=13)

    sym  = rec["symbol"]
    curr = rec["currency"]
    rag  = _rag_color(rec)

    story = []

    # ── Cover banner ───────────────────────────────────────────────────────────
    # Header table: company name + period
    header_data = [[
        Paragraph(f"<b>{rec['portco_name']}</b>", h1),
        Paragraph(f"<b>{rec['period']}</b>\nQuarterly Financial Report",
                  ParagraphStyle("PR", parent=h1, fontSize=11, leading=15,
                                 alignment=TA_RIGHT)),
    ]]
    header_tbl = Table(header_data, colWidths=[100*mm, 74*mm])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (0, -1), 14),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_tbl)

    # Sub-header: sector / geography / stage
    meta_data = [[
        Paragraph(f"Sector: <b>{rec['sector']}</b>", small),
        Paragraph(f"Geography: <b>{rec['geography']}</b>", small),
        Paragraph(f"Stage: <b>{rec['stage']}</b>", small),
        Paragraph(f"Currency: <b>{curr} ({sym}000s)</b>", small),
        Paragraph(f"Report Date: <b>{datetime.now().strftime('%d %b %Y')}</b>", small),
    ]]
    meta_tbl = Table(meta_data, colWidths=[35*mm, 35*mm, 30*mm, 40*mm, 34*mm])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8*mm))

    # ── KPI Scorecard ──────────────────────────────────────────────────────────
    story.append(Paragraph("Performance Highlights", h2))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=6))

    kpi_items = [
        ("Revenue", _fmt(rec["revenue"], sym), curr + "000s"),
        ("Gross Profit", _fmt(rec["gross_profit"], sym), curr + "000s"),
        ("EBITDA", _fmt(rec["ebitda"], sym), curr + "000s"),
        ("EBITDA Margin", f"{rec['ebitda_margin']:.1f}%", ""),
        ("Net Income", _fmt(rec["net_income"], sym), curr + "000s"),
        ("Headcount", f"{rec['headcount']:,}", "FTEs"),
    ]

    kpi_data = []
    row = []
    for idx, (lbl, val, unit) in enumerate(kpi_items):
        cell = Table(
            [[Paragraph(lbl, label)],
             [Paragraph(val, ParagraphStyle("KV", parent=styles["Normal"],
                                            fontName="Helvetica-Bold", fontSize=16,
                                            textColor=NAVY, leading=20))],
             [Paragraph(unit, small)]],
            colWidths=[27*mm]
        )
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDE1EB")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ]))
        row.append(cell)
        if len(row) == 3:
            kpi_data.append(row)
            row = []
    if row:
        while len(row) < 3:
            row.append(Paragraph("", body))
        kpi_data.append(row)

    kpi_tbl = Table(kpi_data, colWidths=[59*mm, 59*mm, 59*mm], hAlign="LEFT")
    kpi_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 8*mm))

    # ── P&L Table ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Income Statement", h2))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=6))

    pl_rows = [
        ["", f"{rec['period']} Actual", "vs Budget", ""],
        ["Revenue",       _fmt(rec["revenue"], sym),       _pct(rec["vs_budget_revenue_pct"]),  ""],
        ["Gross Profit",  _fmt(rec["gross_profit"], sym),  "",  ""],
        ["EBITDA",        _fmt(rec["ebitda"], sym),        _pct(rec["vs_budget_ebitda_pct"]), ""],
        ["EBIT",          _fmt(rec["ebit"], sym),          "",  ""],
        ["Net Income",    _fmt(rec["net_income"], sym),    "",  ""],
        ["EBITDA Margin", f"{rec['ebitda_margin']:.1f}%",  "",  ""],
        ["Rev Growth YoY",f"{rec['revenue_growth_yoy']:.1f}%", "",  ""],
    ]

    def _variance_color(val_str: str):
        if not val_str or val_str == "":
            return colors.white
        try:
            v = float(val_str.replace("%", "").replace("+", ""))
            if v < -10:
                return colors.HexColor("#FADBD8")
            if v < 0:
                return colors.HexColor("#FEF9E7")
            return colors.HexColor("#EAFAF1")
        except Exception:
            return colors.white

    pl_col_widths = [65*mm, 45*mm, 35*mm, 29*mm]
    pl_tbl = Table(pl_rows, colWidths=pl_col_widths)
    pl_style = [
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        # Data rows
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (0, -1), 8),
        ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#DDE1EB")),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT]),
        # Bold revenue & ebitda rows
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTNAME",      (0, 3), (-1, 3), "Helvetica-Bold"),
    ]
    for r_idx in range(1, len(pl_rows)):
        v = pl_rows[r_idx][2]
        vc = _variance_color(v)
        pl_style.append(("BACKGROUND", (2, r_idx), (2, r_idx), vc))

    pl_tbl.setStyle(TableStyle(pl_style))
    story.append(pl_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    story.append(Paragraph("Balance Sheet", h2))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=6))

    bs_rows = [
        ["", f"{rec['period']} Actual", "", ""],
        ["Cash & Equivalents", _fmt(rec["cash"], sym),         "", ""],
        ["Total Debt",         _fmt(rec["total_debt"], sym),   "", ""],
        ["Net Debt",           _fmt(rec["net_debt"], sym),     "", ""],
        ["Total Assets",       _fmt(rec["total_assets"], sym), "", ""],
        ["Net Debt / EBITDA",  f"{rec['net_debt_ebitda']:.2f}x", "", ""],
    ]

    bs_tbl = Table(bs_rows, colWidths=pl_col_widths)
    bs_style = [
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (0, -1), 8),
        ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#DDE1EB")),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT]),
        ("FONTNAME",      (0, 4), (-1, 4), "Helvetica-Bold"),
        ("FONTNAME",      (0, 5), (-1, 5), "Helvetica-Bold"),
    ]
    # Colour ND/EBITDA row by RAG
    nd = rec["net_debt_ebitda"]
    if nd > 5:
        bs_style.append(("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#FADBD8")))
    elif nd > 4:
        bs_style.append(("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#FEF9E7")))
    else:
        bs_style.append(("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#EAFAF1")))

    bs_tbl.setStyle(TableStyle(bs_style))
    story.append(bs_tbl)
    story.append(Spacer(1, 8*mm))

    # ── RAG Status ────────────────────────────────────────────────────────────
    story.append(Paragraph("Status Summary", h2))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=6))

    rag_label = "GREEN" if rag == colors.HexColor("#27AE60") else \
                "AMBER" if rag == colors.HexColor("#E67E22") else "RED"
    rag_emoji = {"GREEN": "●", "AMBER": "●", "RED": "●"}[rag_label]

    rag_data = [[
        Paragraph(f"<b>RAG Status:</b>", body),
        Paragraph(f"<b>{rag_emoji} {rag_label}</b>",
                  ParagraphStyle("RAG", parent=styles["Normal"],
                                 fontName="Helvetica-Bold", fontSize=10,
                                 textColor=rag, leading=14)),
        Paragraph(f"Net Debt / EBITDA: <b>{rec['net_debt_ebitda']:.2f}x</b>", body),
        Paragraph(f"EBITDA vs Budget: <b>{_pct(rec['vs_budget_ebitda_pct'])}</b>", body),
    ]]
    rag_tbl = Table(rag_data, colWidths=[35*mm, 28*mm, 60*mm, 51*mm])
    rag_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX",        (0, 0), (-1, -1), 1, GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(rag_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Footer disclaimer ──────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY, spaceBefore=4, spaceAfter=4))
    story.append(Paragraph(
        "This report contains synthetic/demo data generated for illustrative purposes only. "
        "AlphaFMC — Confidential. Not for distribution.",
        ParagraphStyle("Disc", parent=styles["Normal"],
                       fontName="Helvetica-Oblique", fontSize=7,
                       textColor=GREY, leading=10, alignment=TA_CENTER)
    ))

    doc.build(story)


# ── Main entry point ───────────────────────────────────────────────────────────

def main():
    pdf_dir = PROJECT_ROOT / "data" / "demo_pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    all_records = []
    pdf_count = 0

    print("AlphaFMC Demo Data Generator")
    print("=" * 50)

    for portco in PORTCOS:
        print(f"\nGenerating: {portco['portco_name']} ({portco['portco_id']})")
        records = generate_financials(portco)
        all_records.extend(records)

        for rec in records:
            filename = f"{rec['portco_id']}_{rec['year']}_{rec['quarter']}.pdf"
            out_path = pdf_dir / filename
            build_pdf(rec, out_path)
            print(f"  OK  {filename}")
            pdf_count += 1

    # Save JSON manifest (used by pipeline and dashboard)
    manifest_path = PROJECT_ROOT / "data" / "financials.json"
    with open(manifest_path, "w") as f:
        json.dump(all_records, f, indent=2)
    print(f"\nSaved financial manifest -> data/financials.json")

    # Save portco metadata
    portco_meta = [
        {k: v for k, v in p.items()
         if k not in ("base_revenue", "gross_margin", "ebitda_margin",
                      "base_headcount", "base_total_debt", "base_cash",
                      "revenue_growth_q", "headcount_growth")}
        for p in PORTCOS
    ]
    meta_path = PROJECT_ROOT / "data" / "portcos.json"
    with open(meta_path, "w") as f:
        json.dump(portco_meta, f, indent=2)
    print(f"Saved portco metadata -> data/portcos.json")

    print(f"\n{'='*50}")
    print(f"Done. Generated {pdf_count} PDFs across {len(PORTCOS)} portcos.")
    print(f"Output directory: {pdf_dir}")


if __name__ == "__main__":
    main()
