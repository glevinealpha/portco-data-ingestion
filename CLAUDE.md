# AlphaFMC — Portfolio Data Pipeline Demo

## Project Overview
This is a self-contained demo application for AlphaFMC's private markets division.
It simulates a portfolio company (portco) financial data ingestion pipeline, from
PDF upload through to LP report drafting and a live portfolio dashboard.

All data is synthetic/demo. No real portco data is used.

---

## Tech Stack
- **Backend**: Python (FastAPI)
- **PDF Parsing**: pdfplumber + Claude API (claude-sonnet-4-20250514) for extraction
- **Data Store**: SQLite (single file, no setup required)
- **Dashboard**: Streamlit
- **Report Generation**: Claude API → populates a Word (.docx) template via python-docx
- **Demo Data**: Faker + custom financial data generator (scripts/generate_demo_data.py)

---

## Project Structure
```
alphafmc-demo/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── data/
│   ├── db/                     # SQLite database
│   └── demo_pdfs/              # Synthetic portco PDF financials
├── scripts/
│   └── generate_demo_data.py   # Generates demo portcos + PDF financials
├── pipeline/
│   ├── ingestor.py             # Watches for new PDFs, triggers extraction
│   ├── extractor.py            # Claude-powered PDF → structured KPIs
│   ├── normaliser.py           # Maps extracted data to standard schema
│   └── store.py                # Database read/write layer
├── reports/
│   ├── template.docx           # LP report Word template
│   └── generator.py            # Populates template with portco data
├── dashboard/
│   └── app.py                  # Streamlit dashboard
└── api/
    └── main.py                 # FastAPI endpoints (optional)
```

---

## Demo Data Spec
Generate **5 fictional portfolio companies** across different sectors:

| Company | Sector | Geography | Stage |
|---|---|---|---|
| Nexora Health | Healthcare | UK | Growth |
| Caliber Logistics | Industrials | Germany | Buyout |
| Prism Digital | TMT | UK | Growth |
| Verdant Energy | Renewables | Spain | Infrastructure |
| Halo Consumer | Consumer | France | Buyout |

Each portco should have:
- 8 quarters of historical financials (Q1 2023 – Q4 2024)
- P&L: Revenue, Gross Profit, EBITDA, EBIT, Net Income
- Balance Sheet: Cash, Total Debt, Net Debt, Total Assets
- KPIs: Headcount, Revenue Growth YoY, EBITDA Margin, Net Debt / EBITDA
- Current quarter vs budget variance
- Generate as realistic-looking PDF financial reports (one PDF per portco per quarter)

---

## Extraction Schema
Each PDF should be parsed into this normalised structure:

```python
{
  "portco_id": str,
  "portco_name": str,
  "period": str,           # e.g. "Q3 2024"
  "currency": str,         # GBP / EUR
  "revenue": float,
  "gross_profit": float,
  "ebitda": float,
  "ebit": float,
  "net_income": float,
  "cash": float,
  "total_debt": float,
  "net_debt": float,
  "headcount": int,
  "revenue_growth_yoy": float,
  "ebitda_margin": float,
  "net_debt_ebitda": float,
  "vs_budget_revenue_pct": float,
  "vs_budget_ebitda_pct": float,
  "extraction_confidence": float,  # 0–1, flagged if < 0.8
  "extracted_at": str              # ISO timestamp
}
```

---

## Dashboard Requirements
The Streamlit dashboard should include:

1. **Portfolio Overview** — summary table of all portcos, latest quarter KPIs, RAG status
2. **Portco Drilldown** — select a portco, see KPI trend charts (revenue, EBITDA, net debt) over 8 quarters
3. **Upload Simulator** — drag-and-drop a demo PDF, trigger the extraction pipeline, show results
4. **Variance Flags** — highlight portcos where actuals are >10% below budget

RAG status logic:
- 🟢 Green: EBITDA margin on target, net debt / EBITDA < 4x
- 🟡 Amber: EBITDA margin 5–10% below budget OR net debt / EBITDA 4–5x
- 🔴 Red: EBITDA margin >10% below budget OR net debt / EBITDA > 5x

---

## LP Report Requirements
Generate a quarterly LP report (Word doc) that includes:
- Cover page with AlphaFMC branding and period
- Executive summary (Claude-generated narrative, ~150 words)
- One page per portco: KPI table + Claude-generated commentary (~100 words) highlighting performance vs prior quarter and budget
- Portfolio-level summary table

---

## Build Order
1. `scripts/generate_demo_data.py` — generate portcos, financials, PDFs
2. `pipeline/` — extractor and store
3. `dashboard/app.py` — Streamlit UI
4. `reports/generator.py` — LP report generation
5. `README.md` — setup and run instructions

---

## Style Notes
- Use AlphaFMC brand colours where possible: **Navy #0A1628**, **Gold #C9A84C**
- Keep the dashboard clean and institutional — this is for LP/IC audiences
- All currency in GBP for UK portcos, EUR for European portcos
- Numbers in thousands (£000s / €000s) unless stated

---

## First Task for Claude Code
> "Read CLAUDE.md and build this project end to end, starting with
> `scripts/generate_demo_data.py`. Generate all 5 portcos with 8 quarters
> of synthetic financials and produce realistic-looking PDF financial
> reports for each. Then proceed through the build order in CLAUDE.md."
