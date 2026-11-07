"""
app.py - AI Lead Business Discovery System Dashboard

A professional Streamlit-based sales intelligence dashboard for discovering,
evaluating, and scoring business service leads from public procurement requirements.

Sections:
1. Executive Dashboard (KPIs, category charts, intent/priority distribution)
2. Data Ingestion (built-in sample CSV & custom CSV upload with validation)
3. AI Evaluation Pipeline (batch processing with progress tracking, rate-limiting, and error handling)
4. Lead Explorer (search, category/priority/intent filters, verification cards with verbatim evidence)
5. Data Export & CRM Sync (CSV & OpenPyXL Excel downloads, export tracking)
"""

import os
import io
import time
from datetime import datetime
import streamlit as st
import pandas as pd

# Internal modules
import database
import data_processor
import ai_analyzer
import lead_scoring

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Lead Business Discovery System",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database schema and auto-seed demo leads if database is empty
database.init_db()
if not hasattr(database, "seed_demo_leads_if_empty"):
    import importlib
    importlib.reload(database)

if hasattr(database, "seed_demo_leads_if_empty"):
    database.seed_demo_leads_if_empty()

# ---------------------------------------------------------
# Session State: Theme & AI Processing Status
# ---------------------------------------------------------
if "app_theme" not in st.session_state:
    st.session_state["app_theme"] = "light"

if "ai_status" not in st.session_state:
    st.session_state["ai_status"] = "idle"

if "ai_status_msg" not in st.session_state:
    st.session_state["ai_status_msg"] = "AI Ready"

current_theme = st.session_state["app_theme"]

# ---------------------------------------------------------
# Custom Styling - Dynamic Enterprise Theme Engine
# ---------------------------------------------------------
if current_theme == "dark":
    theme_vars = """
    :root {
        --canvas-bg: #0f172a;
        --card-bg: #1e293b;
        --card-border: #334155;
        --text-heading: #f8fafc;
        --text-main: #e2e8f0;
        --text-muted: #94a3b8;
        --accent-blue: #60a5fa;
        --accent-hover: #93c5fd;
        --accent-light: #1e3a5f;
        --radio-bg: #1e293b;
        --radio-border: #475569;
        --quote-bg: #1e293b;
        --quote-border: #60a5fa;
        --evidence-bg: #064e3b;
        --evidence-border: #34d399;
        --evidence-text: #a7f3d0;
        --reason-bg: #1e293b;
        --reason-border: #334155;
        --notice-bg: #1e293b;
        --notice-border: #334155;
        --notice-text: #93c5fd;
        --btn-sec-bg: #1e293b;
        --btn-sec-border: #475569;
        --btn-sec-text: #f1f5f9;
        --status-pill-bg: #1e293b;
        --status-pill-border: #334155;
    }
    """
else:
    theme_vars = """
    :root {
        --canvas-bg: #f8fafc;
        --card-bg: #ffffff;
        --card-border: #e2e8f0;
        --text-heading: #0f172a;
        --text-main: #1e293b;
        --text-muted: #64748b;
        --accent-blue: #2563eb;
        --accent-hover: #1d4ed8;
        --accent-light: #eff6ff;
        --radio-bg: #f8fafc;
        --radio-border: #cbd5e1;
        --quote-bg: #f8fafc;
        --quote-border: #2563eb;
        --evidence-bg: #f0fdf4;
        --evidence-border: #10b981;
        --evidence-text: #065f46;
        --reason-bg: #f8fafc;
        --reason-border: #e2e8f0;
        --notice-bg: #f0f7ff;
        --notice-border: #c7dffd;
        --notice-text: #1e3a8a;
        --btn-sec-bg: #ffffff;
        --btn-sec-border: #cbd5e1;
        --btn-sec-text: #1e293b;
        --status-pill-bg: #ffffff;
        --status-pill-border: #cbd5e1;
    }
    """

st.markdown(
    f"""
    <style>
    {theme_vars}

    /* Main canvas styling */
    .stApp {{
        background-color: var(--canvas-bg) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
        color: var(--text-main) !important;
    }}

    /* Main workspace text hierarchy */
    [data-testid="stMainBlockContainer"] p,
    [data-testid="stMainBlockContainer"] span,
    [data-testid="stMainBlockContainer"] label,
    [data-testid="stMainBlockContainer"] div[data-testid="stMarkdownContainer"] p {{
        color: var(--text-main);
    }}

    [data-testid="stMainBlockContainer"] h1,
    [data-testid="stMainBlockContainer"] h2,
    [data-testid="stMainBlockContainer"] h3,
    [data-testid="stMainBlockContainer"] h4,
    [data-testid="stMainBlockContainer"] h5 {{
        color: var(--text-heading) !important;
    }}

    [data-testid="stMainBlockContainer"] .stCaption,
    [data-testid="stMainBlockContainer"] caption {{
        color: var(--text-muted) !important;
    }}

    /* Sidebar deep navy enterprise theme */
    [data-testid="stSidebar"] {{
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }}
    [data-testid="stSidebar"] * {{
        color: #f1f5f9;
    }}
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {{
        color: #94a3b8 !important;
    }}
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5 {{
        color: #ffffff !important;
        font-weight: 600;
        letter-spacing: -0.01em;
    }}
    [data-testid="stSidebar"] [data-testid="stTextInput"] input,
    [data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #ffffff !important;
        border-radius: 6px;
    }}

    /* Sidebar telemetry card */
    .sidebar-telemetry {{
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px 14px;
        margin: 10px 0;
    }}
    .sidebar-telemetry-row {{
        display: flex;
        justify-content: space-between;
        padding: 5px 0;
        font-size: 0.85rem;
        border-bottom: 1px solid #273549;
    }}
    .sidebar-telemetry-row:last-child {{
        border-bottom: none;
    }}
    .telemetry-label {{
        color: #94a3b8;
    }}
    .telemetry-value {{
        color: #f8fafc;
        font-weight: 600;
    }}

    /* KPI Metric Cards */
    [data-testid="stMetric"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 10px !important;
        padding: 16px 20px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        color: var(--text-muted) !important;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: var(--text-heading) !important;
    }}

    /* Enterprise notice banner */
    .enterprise-notice {{
        background-color: var(--notice-bg);
        border: 1px solid var(--notice-border);
        border-left: 4px solid var(--accent-blue);
        color: var(--notice-text);
        padding: 12px 18px;
        border-radius: 6px;
        font-size: 0.88rem;
        margin-bottom: 22px;
        line-height: 1.5;
    }}
    .notice-pill {{
        background-color: var(--accent-blue);
        color: #ffffff;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 8px;
        vertical-align: middle;
    }}

    /* Header Controls Container - Compact Unified Right Group */
    div.st-key-hdr_controls {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: flex-end !important;
        align-items: center !important;
        gap: 10px !important;
        width: 100% !important;
        height: 100% !important;
        min-height: 34px !important;
    }}
    div.st-key-hdr_controls > div,
    div.st-key-hdr_controls > div[data-testid="stElementContainer"] {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: auto !important;
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        margin: 0 !important;
        padding: 0 !important;
        flex: 0 0 auto !important;
        align-self: center !important;
    }}
    div.st-key-hdr_controls div[data-testid="stMarkdown"],
    div.st-key-hdr_controls div[data-testid="stMarkdownContainer"] {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
    }}
    div.st-key-hdr_controls div[data-testid="stMarkdownContainer"] p {{
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
    }}

    /* Top-Right Header Elements - Compact Unified Controls */
    .ai-status-pill {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        height: 34px;
        min-height: 34px;
        max-height: 34px;
        box-sizing: border-box;
        background-color: var(--status-pill-bg);
        border: 1px solid var(--status-pill-border);
        border-radius: 8px;
        padding: 0 10px;
        font-size: 0.76rem;
        font-weight: 600;
        color: var(--text-main);
        white-space: nowrap;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
        transition: all 0.15s ease-in-out;
        margin: 0;
        line-height: 1;
        align-self: center;
    }}
    .ai-status-pill:hover {{
        border-color: var(--accent-blue);
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
    }}
    .status-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }}
    .ai-status-idle .status-dot {{
        background-color: #10b981;
    }}
    .ai-status-processing .status-dot {{
        background-color: #f59e0b;
        box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.25);
        animation: pulse 1.5s infinite;
    }}
    .ai-status-completed .status-dot {{
        background-color: #10b981;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
    }}
    @keyframes pulse {{
        0% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.5; transform: scale(1.2); }}
        100% {{ opacity: 1; transform: scale(1); }}
    }}
    .status-text {{
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}

    /* Compact Theme Toggle Button */
    div.st-key-hdr_theme_toggle,
    div.st-key-hdr_theme_toggle div[data-testid="stButton"],
    div.st-key-hdr_theme_toggle span.stTooltipHoverTarget {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        margin: 0 !important;
        padding: 0 !important;
        width: auto !important;
    }}
    div.st-key-hdr_theme_toggle button {{
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        box-sizing: border-box !important;
        padding: 0 10px !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: 1px solid var(--card-border) !important;
        background-color: var(--btn-sec-bg) !important;
        color: var(--btn-sec-text) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 4px !important;
        white-space: nowrap !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.15s ease-in-out !important;
        margin: 0 !important;
        width: auto !important;
        line-height: 1 !important;
        align-self: center !important;
    }}
    div.st-key-hdr_theme_toggle button:hover {{
        border-color: var(--accent-blue) !important;
        color: var(--accent-blue) !important;
        background-color: var(--accent-light) !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06) !important;
    }}

    /* Compact GitHub Repository Button */
    .gh-header-btn {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 34px;
        height: 34px;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        box-sizing: border-box;
        border-radius: 8px;
        border: 1px solid var(--card-border);
        background-color: var(--card-bg);
        color: var(--text-main);
        text-decoration: none;
        transition: all 0.15s ease-in-out;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
        margin: 0;
        padding: 0;
        align-self: center;
    }}
    .gh-header-btn:hover {{
        background-color: var(--accent-light);
        border-color: var(--accent-blue);
        color: var(--accent-blue);
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
    }}
    .gh-header-btn svg {{
        display: block;
        width: 17px;
        height: 17px;
    }}

    /* --------------------------------------------------------- */
    /* 1. Navigation Tabs                                        */
    /* --------------------------------------------------------- */
    [data-testid="stTabs"] {{
        background-color: transparent !important;
        border-bottom: 2px solid var(--card-border) !important;
        margin-top: 10px !important;
        margin-bottom: 22px !important;
        gap: 6px !important;
    }}
    [data-testid="stTabs"] button[role="tab"] {{
        background-color: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        padding: 10px 18px !important;
        border-radius: 6px 6px 0 0 !important;
        transition: all 0.15s ease-in-out !important;
        margin-bottom: -2px !important;
    }}
    [data-testid="stTabs"] button[role="tab"] p,
    [data-testid="stTabs"] button[role="tab"] span,
    [data-testid="stTabs"] button[role="tab"] div,
    [data-testid="stTabs"] button[role="tab"] div[data-testid="stMarkdownContainer"] p {{
        color: var(--text-main) !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
    }}
    [data-testid="stTabs"] button[role="tab"]:hover {{
        background-color: var(--accent-light) !important;
    }}
    [data-testid="stTabs"] button[role="tab"]:hover p,
    [data-testid="stTabs"] button[role="tab"]:hover span,
    [data-testid="stTabs"] button[role="tab"]:hover div {{
        color: var(--accent-hover) !important;
    }}
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
        background-color: var(--accent-light) !important;
        border-bottom: 2px solid var(--accent-blue) !important;
    }}
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] p,
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] span,
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] div,
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] div[data-testid="stMarkdownContainer"] p {{
        color: var(--accent-blue) !important;
        font-weight: 700 !important;
    }}

    /* --------------------------------------------------------- */
    /* 2. Radio Options (Export Scope & Data Ingestion)          */
    /* --------------------------------------------------------- */
    [data-testid="stRadio"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        padding: 14px 18px !important;
        margin: 8px 0 16px 0 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    }}
    [data-testid="stRadio"] > label,
    [data-testid="stRadio"] > label p,
    [data-testid="stRadio"] > label span,
    [data-testid="stRadio"] > label div[data-testid="stMarkdownContainer"] p {{
        color: var(--text-heading) !important;
        font-weight: 600 !important;
        font-size: 0.90rem !important;
        margin-bottom: 10px !important;
    }}
    [data-testid="stRadio"] [role="radiogroup"] {{
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 12px !important;
        align-items: center !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"] {{
        background-color: var(--radio-bg) !important;
        border: 1px solid var(--radio-border) !important;
        border-radius: 6px !important;
        padding: 8px 16px !important;
        cursor: pointer !important;
        transition: all 0.15s ease-in-out !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 8px !important;
        margin: 0 !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"]:hover {{
        border-color: var(--accent-blue) !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"] input[type="radio"] + div {{
        border: 2px solid var(--text-muted) !important;
        background-color: var(--card-bg) !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"] p,
    [data-testid="stRadio"] label[data-baseweb="radio"] span,
    [data-testid="stRadio"] label[data-baseweb="radio"] div,
    [data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {{
        color: var(--text-main) !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        margin: 0 !important;
        padding: 0 !important;
        display: inline-block !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
        background-color: var(--accent-light) !important;
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 1px var(--accent-blue) !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p,
    [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) span,
    [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) div,
    [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p {{
        color: var(--accent-blue) !important;
        font-weight: 600 !important;
    }}
    [data-testid="stRadio"] label[data-baseweb="radio"] input[type="radio"]:checked + div {{
        border: 2px solid var(--accent-blue) !important;
        background-color: var(--accent-blue) !important;
    }}

    /* --------------------------------------------------------- */
    /* 3. Data Tables (Glide Data Grid Container)               */
    /* --------------------------------------------------------- */
    [data-testid="stDataFrame"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        padding: 0 !important;
        margin: 12px 0 18px 0 !important;
    }}

    /* Native Table element styling */
    [data-testid="stTable"] table,
    table {{
        width: 100% !important;
        background-color: var(--card-bg) !important;
        color: var(--text-main) !important;
        border-collapse: collapse !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        font-size: 0.88rem !important;
        margin: 12px 0 !important;
    }}
    th {{
        background-color: var(--card-border) !important;
        color: var(--text-heading) !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.04em !important;
        padding: 10px 14px !important;
        border-bottom: 2px solid var(--card-border) !important;
    }}
    td {{
        background-color: var(--card-bg) !important;
        color: var(--text-main) !important;
        padding: 10px 14px !important;
        border-bottom: 1px solid var(--card-border) !important;
    }}

    /* --------------------------------------------------------- */
    /* 4. Form Controls & Expanders                              */
    /* --------------------------------------------------------- */
    [data-testid="stMainBlockContainer"] [data-testid="stTextInput"] input {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        color: var(--text-heading) !important;
        border-radius: 6px !important;
    }}
    [data-testid="stMainBlockContainer"] [data-testid="stTextInput"] label,
    [data-testid="stMainBlockContainer"] [data-testid="stTextInput"] label p {{
        color: var(--text-main) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }}
    [data-testid="stMainBlockContainer"] [data-testid="stSelectbox"] label,
    [data-testid="stMainBlockContainer"] [data-testid="stSelectbox"] label p {{
        color: var(--text-main) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }}
    [data-testid="stMainBlockContainer"] [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        color: var(--text-heading) !important;
        border-radius: 6px !important;
    }}
    [data-testid="stMainBlockContainer"] [data-testid="stSelectbox"] div[data-baseweb="select"] * {{
        color: var(--text-heading) !important;
    }}
    [data-testid="stMainBlockContainer"] [data-testid="stSlider"] label,
    [data-testid="stMainBlockContainer"] [data-testid="stSlider"] label p {{
        color: var(--text-main) !important;
        font-weight: 600 !important;
    }}

    /* Expanders (Lead cards) */
    [data-testid="stExpander"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: 8px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    }}
    [data-testid="stExpander"] summary {{
        color: var(--text-heading) !important;
        font-weight: 600 !important;
        padding: 12px 18px !important;
    }}
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span {{
        color: var(--text-heading) !important;
        font-weight: 600 !important;
    }}

    /* Quotation & Evidence callouts */
    .quote-card {{
        background-color: var(--quote-bg);
        border-left: 3px solid var(--quote-border);
        border-radius: 4px;
        padding: 12px 16px;
        font-size: 0.92rem;
        color: var(--text-main);
        margin: 6px 0 14px 0;
        line-height: 1.55;
    }}
    .evidence-card {{
        background-color: var(--evidence-bg);
        border-left: 3px solid var(--evidence-border);
        border-radius: 4px;
        padding: 10px 16px;
        font-size: 0.90rem;
        color: var(--evidence-text);
        margin: 6px 0 14px 0;
        font-style: italic;
        line-height: 1.45;
    }}
    .reason-card {{
        background-color: var(--reason-bg);
        border: 1px solid var(--reason-border);
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 0.88rem;
        color: var(--text-main);
        margin-top: 6px;
        line-height: 1.45;
    }}

    /* Action button styling */
    button[kind="primary"] {{
        background-color: #2563eb !important;
        border-color: #2563eb !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
    }}
    button[kind="primary"]:hover {{
        background-color: #1d4ed8 !important;
        border-color: #1d4ed8 !important;
    }}
    button[kind="secondary"] {{
        background-color: var(--btn-sec-bg) !important;
        border: 1px solid var(--btn-sec-border) !important;
        color: var(--btn-sec-text) !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
    }}
    button[kind="secondary"]:hover {{
        border-color: var(--accent-blue) !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Sidebar Configuration & System Health
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 6px 0 16px 0; border-bottom: 1px solid #1e293b; margin-bottom: 18px;">
            <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; letter-spacing: -0.01em;">
                Lead Intelligence
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px;">
                Sales Discovery Pipeline
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### API Configuration")

    detected_key = ai_analyzer.get_api_key()
    user_api_key = st.text_input(
        "Gemini API Key (Optional Override):",
        type="password",
        value="",
        placeholder="Paste key to override environment",
        help="Reads from .env or Streamlit Secrets by default. You can also paste an override key here for this session.",
    )
    effective_api_key = user_api_key.strip() if user_api_key.strip() else detected_key

    if effective_api_key:
        masked_key = effective_api_key[:4] + "..." + effective_api_key[-4:] if len(effective_api_key) > 8 else "***"
        st.success(f"API Key Active: `{masked_key}`")
    else:
        st.warning("No Gemini API key detected. Configure `.env` or input a key above.")

    configured_model = ai_analyzer.get_configured_model()
    model_options = [
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "custom",
    ]
    default_model_idx = model_options.index(configured_model) if configured_model in model_options else 0
    model_option = st.selectbox(
        "Gemini Model Architecture:",
        options=model_options,
        index=default_model_idx,
        help="Select the Gemini model. gemini-3.8-flash is preferred; if it experiences high demand or quota limits, gemini-3.5-flash is an active alternative.",
    )
    if model_option == "custom":
        custom_model = st.text_input("Custom model identifier:", value=configured_model)
        active_model = custom_model.strip()
    else:
        active_model = model_option

    st.markdown("---")
    st.markdown("##### System Telemetry")
    db_metrics = database.get_dashboard_metrics()

    st.markdown(
        f"""
        <div class="sidebar-telemetry">
            <div class="sidebar-telemetry-row">
                <span class="telemetry-label">Total Leads</span>
                <span class="telemetry-value">{db_metrics['total_records']}</span>
            </div>
            <div class="sidebar-telemetry-row">
                <span class="telemetry-label">Evaluated</span>
                <span class="telemetry-value">{db_metrics['processed_records']}</span>
            </div>
            <div class="sidebar-telemetry-row">
                <span class="telemetry-label">Pending</span>
                <span class="telemetry-value">{db_metrics['unprocessed_records']}</span>
            </div>
            <div class="sidebar-telemetry-row">
                <span class="telemetry-label">Failed</span>
                <span class="telemetry-value">{db_metrics['failed_records']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Reset Local Database", help="Deletes stored leads and reinitializes empty schema."):
        database.reset_database()
        st.success("Database schema reset successfully.")
        st.rerun()

    st.markdown("---")
    st.caption(
        "Cloud Persistence Note: Streamlit Community Cloud runs inside ephemeral containers. "
        "Runtime SQLite modifications do not persist across container reboots."
    )

# ---------------------------------------------------------
# Dynamic Top-Right Header Status & Toolbar
# ---------------------------------------------------------
# Determine queue status for idle state
unprocessed_queue = database.get_unprocessed_leads()
pending_queue_count = len(unprocessed_queue)

if st.session_state.get("ai_status") != "processing":
    if st.session_state.get("ai_status") == "completed":
        pass  # retain completed summary message until next action
    elif pending_queue_count > 0:
        st.session_state["ai_status"] = "idle"
        st.session_state["ai_status_msg"] = f"AI Ready ({pending_queue_count} pending)"
    else:
        st.session_state["ai_status"] = "idle"
        st.session_state["ai_status_msg"] = "AI Ready (Queue clear)"

col_title, col_actions = st.columns([5.5, 4.5], vertical_alignment="center")

with col_title:
    st.markdown(
        """
        <div style="margin-bottom: 0.25rem;">
            <h1 style="font-size: 1.85rem; font-weight: 700; color: var(--text-heading); margin: 0; letter-spacing: -0.02em;">
                AI Lead Business Discovery System
            </h1>
            <p style="font-size: 0.90rem; color: var(--text-muted); margin: 3px 0 0 0;">
                Lead Intelligence, Intent Classification & Procurement Scoring Engine
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_actions:
    with st.container(
        key="hdr_controls",
        horizontal=True,
        wrap=False,
        horizontal_alignment="right",
        vertical_alignment="center",
        gap=10,
    ):
        ai_st = st.session_state.get("ai_status", "idle")
        ai_msg = st.session_state.get("ai_status_msg", "AI Ready")
        if ai_st == "processing":
            pill_class = "ai-status-processing"
        elif ai_st == "completed":
            pill_class = "ai-status-completed"
        else:
            pill_class = "ai-status-idle"

        st.markdown(
            f"""
            <div class="ai-status-pill {pill_class}">
                <span class="status-dot"></span>
                <span class="status-text" title="{ai_msg}">{ai_msg}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        toggle_label = "🌙 Dark" if current_theme == "light" else "☀️ Light"
        toggle_tooltip = "Switch to Dark Mode" if current_theme == "light" else "Switch to Light Mode"
        if st.button(toggle_label, key="hdr_theme_toggle", help=toggle_tooltip):
            st.session_state["app_theme"] = "dark" if current_theme == "light" else "light"
            st.rerun()

        st.markdown(
            """
            <a href="https://github.com/Sagar-satapathy/AI-Lead-Business-Discovery-System" target="_blank" rel="noopener noreferrer" title="View Source on GitHub" class="gh-header-btn">
                <svg width="17" height="17" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            </a>
            """,
            unsafe_allow_html=True,
        )

# Notice Banner
st.markdown(
    """
    <div class="enterprise-notice">
        <span class="notice-pill">Internal System</span>
        This sales intelligence platform analyzes publicly available business procurement requirements
        to identify commercial service opportunities. All demonstration records are designated fictional examples.
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Main Tabs Navigation
# ---------------------------------------------------------
tab_dash, tab_ingest, tab_ai, tab_leads, tab_export = st.tabs([
    "Executive Dashboard",
    "Data Ingestion",
    "AI Evaluation Pipeline",
    "Lead Explorer",
    "Data Export & CRM Sync",
])

# =========================================================
# TAB 1: EXECUTIVE DASHBOARD
# =========================================================
with tab_dash:
    st.subheader("Sales Intelligence Overview")
    metrics = database.get_dashboard_metrics()

    # Top KPI Metrics Cards
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric(
            label="Total Processed",
            value=metrics["processed_records"],
            delta=f"{metrics['unprocessed_records']} pending evaluation",
        )
    with kpi2:
        fit_rate = round(metrics["relevant_opportunities"] / max(metrics["processed_records"], 1) * 100)
        st.metric(
            label="Qualified Leads",
            value=metrics["relevant_opportunities"],
            delta=f"{fit_rate}% fit rate",
        )
    with kpi3:
        st.metric(label="High Priority", value=metrics["high_priority_leads"], delta="Score 80–100")
    with kpi4:
        st.metric(label="Medium Priority", value=metrics["medium_priority_leads"], delta="Score 50–79")
    with kpi5:
        st.metric(label="Active Buying Intent", value=metrics["active_intent_leads"], delta="Procurement ready")

    st.markdown("---")

    if metrics["processed_records"] == 0:
        st.info(
            "No lead records have been evaluated yet. "
            "Navigate to 'Data Ingestion' to load business requirements, then proceed to 'AI Evaluation Pipeline' to execute classification."
        )
    else:
        col_chart1, col_chart2 = st.columns(2)

        chart_primary = "#2563eb" if current_theme == "light" else "#60a5fa"
        with col_chart1:
            st.markdown("##### Opportunities by Service Category")
            cat_data = metrics["category_counts"]
            if cat_data:
                cat_df = pd.DataFrame(list(cat_data.items()), columns=["Category", "Count"])
                st.bar_chart(cat_df.set_index("Category"), color=chart_primary)
            else:
                st.write("No category distribution data available.")

        with col_chart2:
            st.markdown("##### Priority & Buying Intent Distribution")
            tab_prio, tab_intent = st.tabs(["Priority Distribution", "Buying Intent"])
            with tab_prio:
                prio_data = metrics["priority_counts"]
                if prio_data:
                    prio_df = pd.DataFrame(list(prio_data.items()), columns=["Priority", "Count"])
                    st.bar_chart(prio_df.set_index("Priority"), color="#10b981")
            with tab_intent:
                intent_data = metrics["intent_counts"]
                if intent_data:
                    intent_df = pd.DataFrame(list(intent_data.items()), columns=["Intent", "Count"])
                    st.bar_chart(intent_df.set_index("Intent"), color="#f59e0b")

# =========================================================
# TAB 2: DATA INGESTION
# =========================================================
with tab_ingest:
    st.subheader("Data Ingestion & Schema Validation")
    st.markdown(
        "Load the standard demonstration dataset (24 realistic records) or upload an external CSV file. "
        "The system validates mandatory columns, filters empty requirement statements, and prevents duplicates."
    )

    data_source = st.radio(
        "Select Data Source:",
        ["Standard Demonstration Dataset (24 Business Records)", "Upload Custom Requirements CSV"],
        horizontal=True,
    )

    target_df = None
    validation_status = False
    validation_message = ""
    stats_dict = {}

    if data_source == "Standard Demonstration Dataset (24 Business Records)":
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_leads.csv")
        if os.path.exists(sample_path):
            validation_status, target_df, validation_message, stats_dict = data_processor.load_and_validate_csv(sample_path)
            st.success("Loaded built-in demo dataset: `data/sample_leads.csv`.")
        else:
            st.error("Error: `data/sample_leads.csv` not found in workspace.")
    else:
        uploaded_file = st.file_uploader(
            "Upload Business Requirements CSV:",
            type=["csv"],
            help="CSV must contain: business_name, requirement, source_name, source_url, location, date_found",
        )
        if uploaded_file is not None:
            validation_status, target_df, validation_message, stats_dict = data_processor.load_and_validate_csv(uploaded_file)
            if not validation_status:
                st.error(f"Validation Error:\n{validation_message}")
            else:
                st.success("Uploaded CSV passed schema validation successfully.")

    if validation_status and target_df is not None:
        st.markdown("#### Ingestion Validation Audit")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Raw Records", stats_dict.get("raw_count", 0))
        c2.metric("Valid Records", stats_dict.get("valid_count", 0))
        c3.metric("Invalid Dropped", stats_dict.get("empty_dropped", 0))
        c4.metric("Duplicates Filtered", stats_dict.get("duplicates_dropped", 0))

        st.markdown("#### Dataset Preview (First 5 Records)")
        st.dataframe(target_df.head(5), use_container_width=True)

        if st.button("Import Validated Records into Database", type="primary"):
            inserted, skipped = database.insert_leads_from_df(target_df)
            st.success(
                f"Ingestion complete: {inserted} new record(s) inserted. {skipped} duplicate record(s) skipped."
            )
            time.sleep(1)
            st.rerun()

# =========================================================
# TAB 3: AI EVALUATION PIPELINE
# =========================================================
with tab_ai:
    st.subheader("Gemini Classification & Deterministic Scoring Engine")
    st.markdown(
        "Execute AI opportunity classification using the official `google-genai` SDK and calculate deterministic 0–100 lead scores. "
        "Controlled batch execution is enforced to respect API rate limits and free-tier quotas. "
        "Failed API calls are never replaced with fabricated results."
    )

    unprocessed_leads = database.get_unprocessed_leads()
    pending_count = len(unprocessed_leads)

    st.write(f"**Pending Evaluation Queue:** `{pending_count} record(s)`")

    if pending_count == 0:
        st.success("Queue clear: All lead records in the database have been evaluated. Review results in 'Lead Explorer'.")
    else:
        st.markdown("#### Execution Parameters")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            batch_choice = st.selectbox(
                "Batch Allocation:",
                options=["Sample Batch: 3 Records", "Standard Batch: 5 Records", f"Complete Queue: {pending_count} Records"],
                index=0,
            )
        with col_b2:
            pacing_delay = st.slider(
                "Request Pacing Delay (Seconds between calls):",
                min_value=0.5,
                max_value=3.0,
                value=1.2,
                step=0.1,
                help="Adds a pacing pause between Gemini API calls to safeguard API quota and rate limits.",
            )

        # Determine numeric limit
        if "3" in batch_choice:
            batch_limit = 3
        elif "5" in batch_choice:
            batch_limit = 5
        else:
            batch_limit = pending_count

        if st.button(f"Execute Evaluation for Next {min(batch_limit, pending_count)} Record(s)", type="primary"):
            if not effective_api_key:
                st.error("Cannot start evaluation: Gemini API key is missing. Please configure GEMINI_API_KEY in `.env` or sidebar.")
            else:
                leads_to_process = database.get_unprocessed_leads(limit=batch_limit)
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_expander = st.expander("Live Execution Audit Log", expanded=True)

                total_in_batch = len(leads_to_process)
                success_count = 0
                fail_count = 0

                st.session_state["ai_status"] = "processing"
                st.session_state["ai_status_msg"] = f"Evaluating 0/{total_in_batch}..."

                for idx, lead in enumerate(leads_to_process):
                    b_name = lead["business_name"]
                    req_text = lead["requirement"]
                    lead_id = lead["id"]

                    status_msg = f"Evaluating {idx + 1}/{total_in_batch}: {b_name}"
                    status_text.markdown(f"**{status_msg}**...")
                    st.session_state["ai_status_msg"] = f"Evaluating {idx + 1}/{total_in_batch}: {b_name[:18]}"

                    # Call Gemini
                    success, analysis, error_msg = ai_analyzer.analyze_lead_with_gemini(
                        business_name=b_name,
                        requirement=req_text,
                        api_key=effective_api_key,
                        model_name=active_model,
                    )

                    if success and analysis:
                        # Compute deterministic lead score
                        scoring_result = lead_scoring.calculate_lead_score(req_text, analysis)

                        # Update SQLite database
                        database.update_lead_analysis(lead_id, analysis, scoring_result)
                        success_count += 1

                        with log_expander:
                            st.write(
                                f"[SUCCESS] **{b_name}** | Category: `{analysis.get('category')}` | "
                                f"Intent: `{analysis.get('buying_intent')}` | "
                                f"Score: **{scoring_result['total_score']}/100** ({scoring_result['priority']})"
                            )
                    else:
                        fail_count += 1
                        database.mark_lead_failed(lead_id, error_msg)
                        with log_expander:
                            st.error(f"[FAILED] **{b_name}**: {error_msg}")

                    # Update progress
                    progress_bar.progress((idx + 1) / total_in_batch)

                    # Pacing delay to avoid rate limit spikes
                    if idx < total_in_batch - 1:
                        time.sleep(pacing_delay)

                st.session_state["ai_status"] = "completed"
                st.session_state["ai_status_msg"] = f"Batch Complete ({success_count} success, {fail_count} failed)"
                status_text.success(f"Batch completed: {success_count} succeeded, {fail_count} failed.")
                time.sleep(1.5)
                st.rerun()

# =========================================================
# TAB 4: LEAD EXPLORER & OPPORTUNITY VERIFICATION
# =========================================================
with tab_leads:
    st.subheader("Lead Intelligence Explorer & Requirement Verification")
    st.markdown(
        "Inspect evaluated business opportunities, review explainable score breakdowns, and audit verbatim requirement evidence."
    )

    all_leads_df = database.get_all_leads(order_by="score_desc")

    if all_leads_df.empty:
        st.info("No lead records found in database. Ingest leads in 'Data Ingestion' first.")
    else:
        # Summary Metric Bar
        s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)
        with s_col1:
            st.metric("Processed Leads", len(all_leads_df[all_leads_df["status"] == "processed"]))
        with s_col2:
            st.metric("High Priority", len(all_leads_df[(all_leads_df["status"] == "processed") & (all_leads_df["priority"] == "High")]))
        with s_col3:
            st.metric("Medium Priority", len(all_leads_df[(all_leads_df["status"] == "processed") & (all_leads_df["priority"] == "Medium")]))
        with s_col4:
            st.metric("Pending Evaluation", len(all_leads_df[all_leads_df["status"] == "unprocessed"]))
        with s_col5:
            st.metric("Failed Calls", len(all_leads_df[all_leads_df["status"] == "failed"]))

        st.markdown("---")

        # Search & Filter controls
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([2, 1.2, 1.2, 1, 1])
        with f_col1:
            search_query = st.text_input("Search by business, keyword, or location:", value="")
        with f_col2:
            status_options = ["Processed Only", "All Statuses", "Pending Only", "Failed Only"]
            selected_status = st.selectbox("Filter Status:", status_options, index=0)
        with f_col3:
            categories_list = ["All"] + ai_analyzer.ALLOWED_CATEGORIES
            selected_cat = st.selectbox("Filter Category:", categories_list, index=0)
        with f_col4:
            selected_priority = st.selectbox("Filter Priority:", ["All", "High", "Medium", "Low"], index=0)
        with f_col5:
            selected_intent = st.selectbox("Filter Intent:", ["All", "Active", "Potential", "Unclear"], index=0)

        # Apply filtering
        filtered_df = all_leads_df.copy()

        if selected_status == "Processed Only":
            filtered_df = filtered_df[filtered_df["status"] == "processed"]
        elif selected_status == "Pending Only":
            filtered_df = filtered_df[filtered_df["status"] == "unprocessed"]
        elif selected_status == "Failed Only":
            filtered_df = filtered_df[filtered_df["status"] == "failed"]

        if search_query.strip():
            sq = search_query.strip().lower()
            filtered_df = filtered_df[
                filtered_df["business_name"].str.lower().str.contains(sq, na=False)
                | filtered_df["requirement"].str.lower().str.contains(sq, na=False)
                | filtered_df["location"].str.lower().str.contains(sq, na=False)
                | filtered_df["summary"].str.lower().str.contains(sq, na=False)
            ]

        if selected_cat != "All":
            filtered_df = filtered_df[filtered_df["category"] == selected_cat]

        if selected_priority != "All":
            filtered_df = filtered_df[filtered_df["priority"] == selected_priority]

        if selected_intent != "All":
            filtered_df = filtered_df[filtered_df["buying_intent"] == selected_intent]

        st.caption(f"Displaying **{len(filtered_df)}** of **{len(all_leads_df)}** records (Filter: **{selected_status}**)")

        if filtered_df.empty:
            st.info("No lead records match the selected search and filter criteria.")
        else:
            # Display Detailed Lead Cards
            for _, lead in filtered_df.iterrows():
                status = lead.get("status", "unprocessed")
                priority = lead.get("priority", "Low")
                score = lead.get("lead_score", 0)
                category = lead.get("category", "Uncategorized")
                b_name = lead.get("business_name", "Unknown Business")

                if status == "processed":
                    header_title = f"{b_name} | Score: {score}/100 | {priority} Priority | {category}"
                elif status == "failed":
                    header_title = f"{b_name} | Evaluation Failed | {category}"
                else:
                    header_title = f"{b_name} | Pending AI Evaluation"

                # Automatically expand all successfully processed leads
                is_expanded = (status == "processed")
                with st.expander(header_title, expanded=is_expanded):
                    c_left, c_right = st.columns([3, 2])

                    with c_left:
                        st.markdown("##### Client Requirement Statement")
                        st.markdown(f'<div class="quote-card">"{lead["requirement"]}"</div>', unsafe_allow_html=True)

                        st.markdown("##### Executive Summary")
                        if lead.get("summary"):
                            st.write(lead["summary"])
                        elif status == "failed":
                            st.caption("Evaluation could not be completed.")
                        else:
                            st.caption("Evaluation pending.")

                        st.markdown("##### Verbatim Requirement Evidence")
                        if lead.get("evidence"):
                            st.markdown(f'<div class="evidence-card">"{lead["evidence"]}"</div>', unsafe_allow_html=True)
                        elif status == "failed":
                            st.caption("No evidence extracted.")
                        else:
                            st.caption("No evidence extracted.")

                    with c_right:
                        st.markdown("##### Classification Details")
                        st.write(f"• **Category:** `{lead.get('category', 'N/A')}`")
                        st.write(f"• **Relevance:** `{lead.get('relevance', 'Pending')}`")
                        st.write(f"• **Buying Intent:** `{lead.get('buying_intent', 'N/A')}`")
                        st.write(f"• **Location:** {lead.get('location', 'N/A')}")
                        st.write(f"• **Date Identified:** {lead.get('date_found', 'N/A')}")

                        st.markdown("##### Source Metadata")
                        st.write(f"• **Origin Platform:** {lead.get('source_name', 'N/A')}")
                        src_url = lead.get("source_url", "")
                        if src_url:
                            st.write(f"• **Source URL:** [{src_url}]({src_url})")

                        st.markdown("##### Scoring Justification")
                        if lead.get("score_explanation"):
                            st.markdown(f'<div class="reason-card">{lead["score_explanation"]}</div>', unsafe_allow_html=True)
                        elif status == "failed":
                            st.error(f"Analysis failed: {lead.get('error_message', 'Unknown error')}")
                        else:
                            st.caption("Pending AI evaluation.")

# =========================================================
# TAB 5: DATA EXPORT & CRM SYNC
# =========================================================
with tab_export:
    st.subheader("Data Export & CRM Synchronization")
    st.markdown(
        "Export evaluated lead records as standardized CSV or formatted Excel (`.xlsx`) workbooks for CRM ingestion and executive reporting."
    )

    export_scope = st.radio(
        "Select Export Dataset Scope:",
        [
            "All Leads in Database",
            "Relevant Leads Only",
            "High Priority Leads Only",
            "Not Yet Exported Leads",
        ],
        horizontal=True,
    )

    base_df = database.get_all_leads(order_by="id_asc")

    if base_df.empty:
        st.warning("Database contains no lead records to export.")
    else:
        if export_scope == "Not Yet Exported Leads":
            is_exp_col = base_df["is_exported"] if "is_exported" in base_df.columns else 0
            export_df = base_df[(base_df["status"] == "processed") & (is_exp_col == 0)].copy()
        elif "Relevant" in export_scope:
            export_df = base_df[base_df["relevance"] == "Relevant"].copy()
        elif "High Priority" in export_scope:
            export_df = base_df[base_df["priority"] == "High"].copy()
        else:
            export_df = base_df.copy()

        # Enforce ascending database ID order across all export scopes
        export_df = export_df.sort_values(by="id", ascending=True).reset_index(drop=True)

        st.write(f"Export dataset contains **{len(export_df)}** record(s).")

        if export_df.empty:
            if export_scope == "Not Yet Exported Leads":
                st.info("All evaluated leads have already been marked as exported. No unexported records pending.")
            else:
                st.warning("Database contains no records matching the selected export scope.")
        else:
            # Data preview
            export_preview_cols = [
                "business_name", "category", "buying_intent", "lead_score", "priority", "location", "source_name"
            ]
            available_cols = [c for c in export_preview_cols if c in export_df.columns]
            st.dataframe(export_df[available_cols].head(5), use_container_width=True)

            # Export generation buttons
            exp_col1, exp_col2 = st.columns(2)

            # 1. CSV Download
            csv_buffer = export_df.to_csv(index=False).encode("utf-8")
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
            with exp_col1:
                st.download_button(
                    label="Download CSV Spreadsheet",
                    data=csv_buffer,
                    file_name=f"lead_discovery_export_{timestamp_str}.csv",
                    mime="text/csv",
                    type="primary",
                )

            # 2. Excel Download using OpenPyXL
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name="Leads")
            excel_bytes = excel_buffer.getvalue()

            with exp_col2:
                st.download_button(
                    label="Download Excel Workbook (.xlsx)",
                    data=excel_bytes,
                    file_name=f"lead_discovery_export_{timestamp_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # Export confirmation action
            unexported_ids = [
                int(lid) for lid in export_df[export_df.get("is_exported", 0) == 0]["id"].tolist()
            ] if "is_exported" in export_df.columns else []

            if unexported_ids:
                st.markdown("---")
                st.markdown("##### Export Status Confirmation")
                st.caption(
                    "After downloading your CSV or Excel workbook, confirm below to mark these records in the database. "
                    "Only the records included in this download will be updated, excluding them from future unexported queries."
                )
                if st.button(
                    f"Mark These {len(unexported_ids)} Records as Exported",
                    type="secondary",
                    help="Updates database records so they are excluded from future 'Not Yet Exported Leads' exports.",
                ):
                    marked_count = database.mark_leads_as_exported(unexported_ids)
                    st.success(f"Export status updated: {marked_count} lead(s) successfully marked as exported.")
                    time.sleep(1.2)
                    st.rerun()
