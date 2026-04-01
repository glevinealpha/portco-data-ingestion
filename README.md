# AlphaFMC — Portfolio Data Pipeline Demo

A self-contained demo for AlphaFMC's private markets division. Simulates a full portco
financial data ingestion pipeline: PDF generation → Claude extraction → SQLite store →
Streamlit dashboard → LP report generation.

All data is **synthetic/demo only**. No real portco data is used.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate demo data (portcos + PDFs)

```bash
python scripts/generate_demo_data.py
```

Generates 40 PDFs (5 portcos × 8 quarters) in `data/demo_pdfs/` and writes
`data/financials.json` and `data/portcos.json`.

### 3. Load data into SQLite

```bash
python pipeline/store.py
```

### 4. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Opens at http://localhost:8501

### 5. Generate an LP report

```bash
# Template mode (no API key required)
python reports/generator.py --period "Q4 2024" --no-ai

# AI mode (requires ANTHROPIC_API_KEY)
python reports/generator.py --period "Q4 2024"
```

Output: `reports/output/AlphaFMC_LP_Report_Q4_2024.docx`

### 6. (Optional) Run the REST API

```bash
uvicorn api.main:app --reload
```

API docs at http://localhost:8000/docs

---

## Project Structure

```
portco_data_ingestion/
├── CLAUDE.md                   # Project spec
├── README.md
├── requirements.txt
├── data/
│   ├── db/alphafmc.db          # SQLite database (auto-created)
│   ├── demo_pdfs/              # Generated quarterly PDF reports
│   ├── financials.json         # Financial data manifest
│   └── portcos.json            # Portco metadata
├── scripts/
│   └── generate_demo_data.py   # Portco + PDF generator
├── pipeline/
│   ├── store.py                # SQLite read/write layer
│   ├── extractor.py            # Claude-powered PDF → KPI extraction
│   ├── normaliser.py           # Schema normalisation
│   └── ingestor.py             # PDF watcher / batch processor
├── dashboard/
│   └── app.py                  # Streamlit dashboard
├── reports/
│   ├── generator.py            # LP report Word doc generator
│   └── output/                 # Generated .docx files
└── api/
    └── main.py                 # FastAPI REST endpoints
```

---

## Portfolio Companies

| ID  | Company           | Sector       | Geography | Stage          | Currency |
|-----|-------------------|--------------|-----------|----------------|----------|
| NXH | Nexora Health     | Healthcare   | UK        | Growth         | GBP      |
| CLG | Caliber Logistics | Industrials  | Germany   | Buyout         | EUR      |
| PRD | Prism Digital     | TMT          | UK        | Growth         | GBP      |
| VRE | Verdant Energy    | Renewables   | Spain     | Infrastructure | EUR      |
| HLC | Halo Consumer     | Consumer     | France    | Buyout         | EUR      |

---

## Dashboard Features

| Tab | Description |
|-----|-------------|
| Portfolio Overview | Summary table with latest KPIs and RAG status for all portcos |
| Portco Drilldown | 8-quarter trend charts (Revenue, EBITDA, Net Debt, Margin) |
| Upload Simulator | Drag-and-drop PDF → real-time extraction pipeline |
| Variance Flags | Highlights portcos with actuals materially below budget |

### RAG Status Logic

- **Green**: EBITDA margin on target, Net Debt / EBITDA < 4x
- **Amber**: EBITDA margin 5–10% below budget OR Net Debt / EBITDA 4–5x
- **Red**: EBITDA margin > 10% below budget OR Net Debt / EBITDA > 5x

---

## PDF Extraction Pipeline

The extraction pipeline (`pipeline/extractor.py`) uses:

1. **pdfplumber** to extract raw text from the PDF
2. **Claude API** (`claude-sonnet-4-20250514`) to parse text into structured KPIs
3. **Heuristic fallback** if no API key is set — regex-based parsing of our structured PDFs
4. **Normaliser** to validate and coerce values to the canonical schema

Set `ANTHROPIC_API_KEY` in your environment to enable Claude-powered extraction.

### Batch processing existing PDFs

```bash
python -m pipeline.ingestor --backfill
```

### Watch mode (live ingestion)

```bash
python -m pipeline.ingestor
```

Drop a PDF into `data/demo_pdfs/` and it will be extracted and stored automatically.

---

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/portfolio/latest` | Latest quarter per portco |
| GET | `/portfolio/all` | All records (optional `?portco_id=NXH`) |
| GET | `/portfolio/{portco_id}` | All records for one portco |
| POST | `/extract` | Upload PDF, returns extracted KPIs |
| POST | `/reports/generate` | Trigger LP report generation |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key (enables AI extraction + report narration) |

---

## Brand Colours

- **Navy** `#0A1628`
- **Gold** `#C9A84C`
