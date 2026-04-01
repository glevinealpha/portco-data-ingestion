"""
AlphaFMC Portfolio Dashboard — Streamlit app.

Run:
    streamlit run dashboard/app.py
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.store import get_all_records, get_portco_records, get_latest_records, init_db, bulk_load_from_json
from pipeline.extractor import extract_pdf
from pipeline.store import upsert_record

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AlphaFMC Portfolio Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

NAVY  = "#28343D"
TEAL  = "#00AECB"
GREEN = "#66BC29"
AMBER = "#F38B00"
RED   = "#CF0A2C"
LIGHT = "#F3F5F7"
DARK_TEAL = "#006579"

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@300;400;600;700;800&family=Lora:wght@400;600&display=swap');

    /* Global font */
    html, body, [class*="css"], .stApp {{
        font-family: 'Nunito Sans', sans-serif;
        letter-spacing: -0.01em;
    }}

    /* Main background */
    .stApp {{ background-color: #F3F5F7; }}

    /* Sidebar — red background, force all text white */
    section[data-testid="stSidebar"] {{
        background-color: #8B0000;
    }}
    section[data-testid="stSidebar"] *,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stRadio > label,
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p {{
        color: #FFFFFF !important;
        font-family: 'Nunito Sans', sans-serif !important;
    }}
    /* Radio button selected state */
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] {{
        background-color: rgba(0,174,203,0.15) !important;
        border-radius: 4px;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] div:first-child {{
        border-color: {TEAL} !important;
    }}

    /* Header banner */
    .alphafmc-header {{
        background: {NAVY};
        padding: 22px 28px;
        border-radius: 0;
        margin-bottom: 24px;
        border-bottom: 3px solid {TEAL};
    }}
    .alphafmc-header h1 {{
        color: white;
        margin: 0;
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        font-family: 'Nunito Sans', sans-serif;
    }}
    .alphafmc-header p {{
        color: {TEAL};
        margin: 4px 0 0 0;
        font-size: 0.85rem;
        font-weight: 400;
    }}

    /* KPI cards — dark style matching site */
    .kpi-card {{
        background: {NAVY};
        border: 2px solid {TEAL};
        border-radius: 4px;
        padding: 18px 20px;
        text-align: center;
        box-shadow: 0px 4px 8px rgba(0,0,0,0.15);
        transition: background 0.15s ease;
    }}
    .kpi-card:hover {{
        background: {TEAL};
    }}
    .kpi-label {{
        font-size: 0.7rem;
        color: {TEAL};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
        font-weight: 700;
    }}
    .kpi-card:hover .kpi-label {{
        color: white;
    }}
    .kpi-value {{
        font-size: 1.4rem;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: -0.025em;
    }}
    .kpi-sub {{
        font-size: 0.7rem;
        color: #8698AF;
        margin-top: 3px;
    }}
    .kpi-card:hover .kpi-sub {{
        color: rgba(255,255,255,0.7);
    }}

    /* RAG badges */
    .rag-green {{ background: #E8F7ED; color: #417630; border-radius: 4px;
                  padding: 3px 10px; font-size: 0.78rem; font-weight: 700; }}
    .rag-amber {{ background: #FFF4E5; color: #CC4800; border-radius: 4px;
                  padding: 3px 10px; font-size: 0.78rem; font-weight: 700; }}
    .rag-red   {{ background: #FDECEA; color: #CF0A2C; border-radius: 4px;
                  padding: 3px 10px; font-size: 0.78rem; font-weight: 700; }}

    /* Section headers */
    .section-header {{
        color: {NAVY};
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        border-bottom: 3px solid {TEAL};
        padding-bottom: 6px;
        margin: 20px 0 14px 0;
        font-family: 'Nunito Sans', sans-serif;
    }}

    /* Tables */
    .dataframe {{ font-size: 0.85rem !important; }}

    /* Streamlit button override */
    .stButton > button {{
        background-color: {TEAL};
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: 700;
        font-family: 'Nunito Sans', sans-serif;
        transition: background 0.15s ease;
    }}
    .stButton > button:hover {{
        background-color: {NAVY};
        color: white;
    }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ensure_data() -> bool:
    """Make sure DB has data; auto-load from JSON if not."""
    init_db()
    records = get_latest_records()
    if not records:
        json_path = PROJECT_ROOT / "data" / "financials.json"
        if json_path.exists():
            n = bulk_load_from_json(json_path)
            st.toast(f"Loaded {n} records from financials.json", icon="✅")
            return True
        return False
    return True


def rag_status(row: dict) -> str:
    nd = row.get("net_debt_ebitda", 0) or 0
    em_vs_b = row.get("vs_budget_ebitda_pct", 0) or 0
    if nd > 5 or em_vs_b < -10:
        return "RED"
    if nd > 4 or em_vs_b < -5:
        return "AMBER"
    return "GREEN"


def rag_html(status: str) -> str:
    icons = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}
    classes = {"GREEN": "rag-green", "AMBER": "rag-amber", "RED": "rag-red"}
    return f'<span class="{classes[status]}">{icons[status]} {status}</span>'


def fmt_num(v, sym="", k=True) -> str:
    if v is None:
        return "—"
    suffix = "k" if k else ""
    return f"{sym}{v:,.0f}{suffix}"


def fmt_pct(v, decimals=1) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def currency_sym(currency: str) -> str:
    return "£" if currency == "GBP" else "€"


# ── Chart helpers ─────────────────────────────────────────────────────────────

def trend_chart(df: pd.DataFrame, y_col: str, title: str,
                color: str = NAVY, sym: str = "£") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["period"], y=df[y_col],
        mode="lines+markers",
        line=dict(color=color, width=2.5),
        marker=dict(size=7, color=color),
        hovertemplate=f"<b>%{{x}}</b><br>{title}: {sym}%{{y:,.0f}}k<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color=NAVY, size=13), x=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#F0F2F7", tickfont=dict(size=10)),
        height=240,
        margin=dict(l=10, r=10, t=36, b=10),
    )
    return fig


def margin_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["period"], y=df["ebitda_margin"],
        marker_color=TEAL, name="EBITDA Margin %",
        hovertemplate="<b>%{x}</b><br>EBITDA Margin: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="EBITDA Margin (%)", font=dict(color=NAVY, size=13), x=0),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#F0F2F7",
                   tickformat=".1f", ticksuffix="%", tickfont=dict(size=10)),
        height=240, margin=dict(l=10, r=10, t=36, b=10), showlegend=False,
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────

def sidebar():
    st.sidebar.markdown("""
    <div style="padding:18px 0 10px 0; text-align:center;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 64" width="160" height="52">
          <!-- Icon mark: stacked bar chart -->
          <rect x="8"  y="28" width="12" height="24" rx="2" fill="#00AECB"/>
          <rect x="24" y="18" width="12" height="34" rx="2" fill="#00AECB" opacity="0.8"/>
          <rect x="40" y="8"  width="12" height="44" rx="2" fill="#00AECB" opacity="0.6"/>
          <!-- Diagonal accent line -->
          <line x1="10" y1="26" x2="50" y2="6" stroke="#C9A84C" stroke-width="2" stroke-linecap="round"/>
          <!-- Wordmark -->
          <text x="62" y="32" font-family="'Nunito Sans', Arial, sans-serif"
                font-size="18" font-weight="800" fill="#FFFFFF" letter-spacing="-0.5">Alpha</text>
          <text x="62" y="50" font-family="'Nunito Sans', Arial, sans-serif"
                font-size="18" font-weight="800" fill="#00AECB" letter-spacing="-0.5">FMC</text>
        </svg>
        <div style="font-size:0.65rem; color:#8698AF; margin-top:4px; letter-spacing:0.1em; text-transform:uppercase;">
            Portfolio Intelligence
        </div>
    </div>
    <hr style="border-color:#3a4e59; margin:8px 0 16px 0;">
    """, unsafe_allow_html=True)

    page = st.sidebar.radio(
        "Navigation",
        ["Portfolio Overview", "Portco Drilldown", "Upload Simulator", "Variance Flags", "LP Report"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown(f"""
    <hr style="border-color:#3a4e59; margin:16px 0 8px 0;">
    <div style="font-size:0.7rem; color:#4a6080; text-align:center;">
        As at {datetime.now().strftime('%d %b %Y')}
    </div>
    """, unsafe_allow_html=True)

    return page


# ── Page 1: Portfolio Overview ─────────────────────────────────────────────────

def page_portfolio_overview():
    st.markdown("""
    <div class="alphafmc-header">
        <div>
            <h1>Portfolio Overview</h1>
            <p>Latest quarter KPIs across all portfolio companies</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    latest = get_latest_records()
    if not latest:
        st.warning("No data found. Run `python scripts/generate_demo_data.py` first.")
        return

    df = pd.DataFrame(latest)

    # ── Top-level KPIs ─────────────────────────────────────────────────────────
    total_rev = df["revenue"].sum()
    total_ebitda = df["ebitda"].sum()
    avg_margin = df["ebitda_margin"].mean()
    total_hc = df["headcount"].sum()
    n_red = sum(1 for r in latest if rag_status(r) == "RED")

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, val in [
        (c1, "Total Portfolio Revenue", f"£/€{total_rev/1000:,.1f}M"),
        (c2, "Total EBITDA", f"£/€{total_ebitda/1000:,.1f}M"),
        (c3, "Avg EBITDA Margin", f"{avg_margin:.1f}%"),
        (c4, "Total Headcount", f"{total_hc:,}"),
        (c5, "Companies at Risk", f"{n_red} / {len(latest)}"),
    ]:
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{val}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">Portfolio Companies — Latest Quarter</div>',
                unsafe_allow_html=True)

    # ── Portfolio table ────────────────────────────────────────────────────────
    table_rows = []
    for r in latest:
        sym = currency_sym(r.get("currency", "GBP"))
        status = rag_status(r)
        table_rows.append({
            "Company":         r["portco_name"],
            "Period":          r["period"],
            "Revenue":         fmt_num(r["revenue"], sym),
            "EBITDA":          fmt_num(r["ebitda"], sym),
            "EBITDA Margin":   fmt_pct(r["ebitda_margin"]),
            "Net Debt/EBITDA": f"{r.get('net_debt_ebitda', 0):.2f}x",
            "Rev vs Budget":   fmt_pct(r.get("vs_budget_revenue_pct", 0)),
            "EBITDA vs Budget":fmt_pct(r.get("vs_budget_ebitda_pct", 0)),
            "Headcount":       f"{r.get('headcount', 0):,}",
            "Status":          status,
        })

    tdf = pd.DataFrame(table_rows)

    def colour_status(val):
        colors_map = {"GREEN": "background-color:#E8F7ED; color:#417630; font-weight:700",
                      "AMBER": "background-color:#FFF4E5; color:#CC4800; font-weight:700",
                      "RED":   "background-color:#FADBD8; color:#C0392B; font-weight:600"}
        return colors_map.get(val, "")

    def colour_variance(val):
        try:
            v = float(str(val).replace("%", "").replace("+", ""))
            if v < -10:
                return "background-color:#FDECEA; color:#CF0A2C; font-weight:700"
            if v < 0:
                return "background-color:#FFF4E5; color:#CC4800; font-weight:700"
            return "background-color:#E8F7ED; color:#417630; font-weight:700"
        except Exception:
            return ""

    styled = (
        tdf.style
        .applymap(colour_status, subset=["Status"])
        .applymap(colour_variance, subset=["Rev vs Budget", "EBITDA vs Budget"])
        .set_properties(**{"font-size": "0.85rem"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True, height=220)

    # ── EBITDA margin bar chart ────────────────────────────────────────────────
    st.markdown('<div class="section-header">EBITDA Margin by Company</div>',
                unsafe_allow_html=True)
    fig = px.bar(
        tdf, x="Company", y=[float(v.replace("%", "")) for v in tdf["EBITDA Margin"]],
        color=[float(v.replace("%", "")) for v in tdf["EBITDA Margin"]],
        color_continuous_scale=[[0, RED], [0.4, AMBER], [0.7, GREEN]],
        labels={"y": "EBITDA Margin (%)", "color": "Margin"},
        height=300,
    )
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        coloraxis_showscale=False,
        xaxis_title=None,
        yaxis=dict(ticksuffix="%", gridcolor="#F0F2F7"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Page 2: Portco Drilldown ───────────────────────────────────────────────────

def page_portco_drilldown():
    st.markdown("""
    <div class="alphafmc-header">
        <div>
            <h1>Portco Drilldown</h1>
            <p>8-quarter KPI trend analysis</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    all_records = get_all_records()
    if not all_records:
        st.warning("No data. Run the data generator first.")
        return

    portcos = sorted(set(r["portco_name"] for r in all_records))
    selected = st.selectbox("Select Portfolio Company", portcos)

    portco_rec = [r for r in all_records if r["portco_name"] == selected]
    portco_id  = portco_rec[0]["portco_id"] if portco_rec else None
    records    = get_portco_records(portco_id) if portco_id else []

    if not records:
        st.warning("No records found.")
        return

    df = pd.DataFrame(records)
    sym = currency_sym(df["currency"].iloc[0])
    latest = records[-1]
    status = rag_status(latest)

    # KPI banner for latest quarter
    st.markdown(f'<div class="section-header">{selected} — {latest["period"]} (Latest)</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (c1, "Revenue",        fmt_num(latest["revenue"], sym),         f"{sym}000s"),
        (c2, "EBITDA",         fmt_num(latest["ebitda"], sym),          f"{sym}000s"),
        (c3, "EBITDA Margin",  fmt_pct(latest["ebitda_margin"]),        ""),
        (c4, "Net Debt/EBITDA",f'{latest.get("net_debt_ebitda", 0):.2f}x', ""),
        (c5, "Headcount",      f'{latest.get("headcount", 0):,}',       "FTEs"),
        (c6, "RAG Status",     status,                                  ""),
    ]
    for col, lbl, val, sub in kpis:
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{lbl}</div>
            <div class="kpi-value" style="font-size:1.2rem">{val}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">8-Quarter Trend</div>',
                unsafe_allow_html=True)

    # ── Trend charts ──────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(
            trend_chart(df, "revenue", "Revenue", NAVY, sym),
            use_container_width=True
        )
        st.plotly_chart(
            trend_chart(df, "net_debt", "Net Debt", RED, sym),
            use_container_width=True
        )
    with col_right:
        st.plotly_chart(
            trend_chart(df, "ebitda", "EBITDA", TEAL, sym),
            use_container_width=True
        )
        st.plotly_chart(
            margin_chart(df),
            use_container_width=True
        )

    # ── Net Debt / EBITDA over time ────────────────────────────────────────────
    st.markdown('<div class="section-header">Net Debt / EBITDA (leverage trend)</div>',
                unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["period"], y=df["net_debt_ebitda"],
        mode="lines+markers",
        line=dict(color=NAVY, width=2.5),
        marker=dict(size=7, color=NAVY),
        hovertemplate="<b>%{x}</b><br>ND/EBITDA: %{y:.2f}x<extra></extra>",
    ))
    # Reference lines
    for level, col, label in [(4.0, AMBER, "4x threshold"), (5.0, RED, "5x threshold")]:
        fig.add_hline(y=level, line_dash="dash", line_color=col,
                      annotation_text=label, annotation_position="bottom right")
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#F0F2F7", ticksuffix="x"),
        height=250, margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Historical data table ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">Historical Financials ({})'.format(
        f"{sym}000s") + '</div>', unsafe_allow_html=True)
    display_cols = ["period", "revenue", "gross_profit", "ebitda", "ebit",
                    "net_income", "net_debt", "headcount",
                    "ebitda_margin", "net_debt_ebitda",
                    "vs_budget_revenue_pct", "vs_budget_ebitda_pct"]
    disp_df = df[display_cols].copy()
    disp_df.columns = ["Period", "Revenue", "Gross Profit", "EBITDA", "EBIT",
                        "Net Income", "Net Debt", "Headcount",
                        "EBITDA Margin %", "ND/EBITDA",
                        "Rev vs Budget %", "EBITDA vs Budget %"]
    st.dataframe(disp_df.set_index("Period"), use_container_width=True)


# ── Page 3: Upload Simulator ───────────────────────────────────────────────────

def page_upload_simulator():
    st.markdown("""
    <div class="alphafmc-header">
        <div>
            <h1>Upload Simulator</h1>
            <p>Drag and drop a demo PDF to trigger the extraction pipeline</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Upload a Quarterly Financial Report</div>',
                unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Drop a portco quarterly PDF here",
        type=["pdf"],
        help="Upload any PDF from data/demo_pdfs/ to test the extraction pipeline",
    )

    if uploaded:
        st.info(f"File received: **{uploaded.name}** ({uploaded.size:,} bytes)")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        with st.spinner("Running extraction pipeline..."):
            try:
                record = extract_pdf(tmp_path, filename_hint=uploaded.name)
                record["source_pdf"] = uploaded.name
                upsert_record(record)
                st.success("Extraction complete — record saved to database.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                return

        conf = record.get("extraction_confidence", 1.0)
        if conf < 0.8:
            st.warning(f"Low confidence extraction: {conf:.2f}. Please review results.")

        # Show results
        st.markdown('<div class="section-header">Extracted KPIs</div>',
                    unsafe_allow_html=True)
        sym = currency_sym(record.get("currency", "GBP"))

        c1, c2, c3 = st.columns(3)
        kpi_groups = [
            [("Company",         record.get("portco_name", "—")),
             ("Period",          record.get("period", "—")),
             ("Currency",        record.get("currency", "—"))],
            [("Revenue",         fmt_num(record.get("revenue"), sym)),
             ("EBITDA",          fmt_num(record.get("ebitda"), sym)),
             ("EBITDA Margin",   fmt_pct(record.get("ebitda_margin")))],
            [("Net Debt",        fmt_num(record.get("net_debt"), sym)),
             ("ND/EBITDA",       f'{record.get("net_debt_ebitda", 0):.2f}x'),
             ("Confidence",      f'{conf:.0%}')],
        ]
        for col, group in zip([c1, c2, c3], kpi_groups):
            for label, val in group:
                col.markdown(f"""
                <div class="kpi-card" style="margin-bottom:10px">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value" style="font-size:1.1rem">{val}</div>
                </div>
                """, unsafe_allow_html=True)

        # Full record as expandable JSON
        with st.expander("Full extraction record (JSON)"):
            st.json({k: v for k, v in record.items()
                     if k not in ("raw_extraction", "_low_confidence_flag")})

        st.markdown(f"""
        <br>
        <div style="background:{LIGHT}; border-left: 3px solid {TEAL};
                    padding:10px 16px; border-radius:4px; font-size:0.85rem; color:#555;">
            <b>RAG Status:</b> {rag_html(rag_status(record))}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <b>Extracted at:</b> {record.get("extracted_at", "—")}
        </div>
        """, unsafe_allow_html=True)


# ── Page 4: Variance Flags ─────────────────────────────────────────────────────

def page_variance_flags():
    st.markdown("""
    <div class="alphafmc-header">
        <div>
            <h1>Variance Flags</h1>
            <p>Portfolio companies with actuals materially below budget</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    latest = get_latest_records()
    if not latest:
        st.warning("No data. Run the data generator first.")
        return

    all_records = get_all_records()

    # Threshold selector
    threshold = st.slider("Variance threshold (%)", -25, 0, -10,
                          help="Flag portcos where actuals are below budget by more than this")

    flagged = [r for r in latest
               if (r.get("vs_budget_revenue_pct", 0) or 0) < threshold
               or (r.get("vs_budget_ebitda_pct", 0) or 0) < threshold]

    if not flagged:
        st.success(f"No portcos are more than {abs(threshold)}% below budget on revenue or EBITDA.")
    else:
        st.markdown(f'<div class="section-header">{len(flagged)} Company/Companies Flagged</div>',
                    unsafe_allow_html=True)

    for r in latest:
        sym = currency_sym(r.get("currency", "GBP"))
        rev_miss  = r.get("vs_budget_revenue_pct", 0) or 0
        ebit_miss = r.get("vs_budget_ebitda_pct", 0) or 0
        is_flagged = rev_miss < threshold or ebit_miss < threshold
        status = rag_status(r)

        border_col = RED if is_flagged else "#E8EBF2"
        with st.container():
            st.markdown(f"""
            <div style="background:white; border: 1.5px solid {border_col};
                        border-radius:8px; padding:16px 20px; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-weight:700; font-size:1rem; color:{NAVY};">
                            {r['portco_name']}
                        </span>
                        <span style="font-size:0.8rem; color:#8A94A6; margin-left:10px;">
                            {r['period']}
                        </span>
                    </div>
                    <div>{rag_html(status)}</div>
                </div>
                <div style="display:flex; gap:24px; margin-top:12px;">
                    <div>
                        <div style="font-size:0.72rem; color:#8A94A6; text-transform:uppercase;">
                            Revenue vs Budget
                        </div>
                        <div style="font-weight:600; font-size:1rem;
                                    color:{'#CF0A2C' if rev_miss < threshold else '#417630'};">
                            {fmt_pct(rev_miss)}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.72rem; color:#8A94A6; text-transform:uppercase;">
                            EBITDA vs Budget
                        </div>
                        <div style="font-weight:600; font-size:1rem;
                                    color:{'#C0392B' if ebit_miss < threshold else '#27AE60'};">
                            {fmt_pct(ebit_miss)}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.72rem; color:#8A94A6; text-transform:uppercase;">
                            ND/EBITDA
                        </div>
                        <div style="font-weight:600; font-size:1rem; color:{NAVY};">
                            {r.get('net_debt_ebitda', 0):.2f}x
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.72rem; color:#8A94A6; text-transform:uppercase;">
                            EBITDA Margin
                        </div>
                        <div style="font-weight:600; font-size:1rem; color:{NAVY};">
                            {r.get('ebitda_margin', 0):.1f}%
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Variance scatter ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Revenue vs EBITDA Budget Variance (Latest Quarter)</div>',
                unsafe_allow_html=True)
    df = pd.DataFrame([{
        "Company":        r["portco_name"],
        "Rev vs Budget":  r.get("vs_budget_revenue_pct", 0) or 0,
        "EBITDA vs Budget": r.get("vs_budget_ebitda_pct", 0) or 0,
        "EBITDA":         r.get("ebitda", 0) or 0,
        "Status":         rag_status(r),
    } for r in latest])

    color_map = {"GREEN": GREEN, "AMBER": AMBER, "RED": RED}
    fig = px.scatter(
        df,
        x="Rev vs Budget", y="EBITDA vs Budget",
        text="Company",
        size="EBITDA",
        color="Status",
        color_discrete_map=color_map,
        labels={"Rev vs Budget": "Revenue vs Budget (%)",
                "EBITDA vs Budget": "EBITDA vs Budget (%)"},
        height=380,
    )
    fig.add_vline(x=threshold, line_dash="dash", line_color=RED,
                  annotation_text=f"Threshold {threshold}%")
    fig.add_hline(y=threshold, line_dash="dash", line_color=RED)
    fig.update_traces(textposition="top center")
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)


# ── Page 5: LP Report ─────────────────────────────────────────────────────────

def page_lp_report():
    st.markdown("""
    <div class="alphafmc-header">
        <div>
            <h1>LP Report</h1>
            <p>Generate a quarterly Limited Partner report with AI commentary</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    all_records = get_all_records()
    if not all_records:
        st.warning("No data. Run the data generator first.")
        return

    available_periods = sorted(
        set(r["period"] for r in all_records),
        key=lambda p: (int(p.split()[1]), p.split()[0])
    )

    st.markdown('<div class="section-header">Report Settings</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        period = st.selectbox("Reporting Period", available_periods,
                              index=len(available_periods) - 1)
    with col2:
        use_ai = st.toggle("AI Commentary", value=True,
                           help="Use AlphaGPT to generate narrative commentary")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Generate LP Report", use_container_width=False):
        with st.spinner(f"Generating {period} LP Report {'with AI commentary' if use_ai else '(template)'}..."):
            try:
                from reports.generator import build_lp_report
                out_path = build_lp_report(period=period, use_ai=use_ai)
                with open(out_path, "rb") as f:
                    docx_bytes = f.read()
                st.success(f"Report generated successfully.")
                st.download_button(
                    label="Download LP Report (.docx)",
                    data=docx_bytes,
                    file_name=out_path.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=False,
                )
            except Exception as e:
                st.error(f"Report generation failed: {e}")
                return

    # Preview: show the portcos that will be included
    st.markdown('<div class="section-header">Report Coverage</div>', unsafe_allow_html=True)
    period_records = [r for r in all_records if r["period"] == period]
    if period_records:
        rows = []
        for r in period_records:
            sym = currency_sym(r.get("currency", "GBP"))
            status = rag_status(r)
            rows.append({
                "Company":      r["portco_name"],
                "Sector":       r.get("sector", ""),
                "Revenue":      fmt_num(r["revenue"], sym),
                "EBITDA":       fmt_num(r["ebitda"], sym),
                "Margin":       fmt_pct(r.get("ebitda_margin", 0)),
                "ND/EBITDA":    f'{r.get("net_debt_ebitda", 0):.2f}x',
                "Status":       status,
            })
        tdf = pd.DataFrame(rows)

        def _colour_status(val):
            m = {"GREEN": "background-color:#E8F7ED;color:#417630;font-weight:700",
                 "AMBER": "background-color:#FFF4E5;color:#CC4800;font-weight:700",
                 "RED":   "background-color:#FDECEA;color:#CF0A2C;font-weight:700"}
            return m.get(val, "")

        st.dataframe(
            tdf.style.applymap(_colour_status, subset=["Status"]),
            use_container_width=True, hide_index=True
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ok = ensure_data()
    page = sidebar()

    if not ok and page != "Upload Simulator":
        st.warning(
            "No data in database. Run `python scripts/generate_demo_data.py` "
            "then `python pipeline/store.py` to load data."
        )
        return

    pages = {
        "Portfolio Overview": page_portfolio_overview,
        "Portco Drilldown":   page_portco_drilldown,
        "Upload Simulator":   page_upload_simulator,
        "Variance Flags":     page_variance_flags,
        "LP Report":          page_lp_report,
    }
    pages[page]()


if __name__ == "__main__":
    main()
