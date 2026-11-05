"""
app.py - AI Lead Business Discovery System Dashboard

A Streamlit-based sales intelligence dashboard for discovering and scoring
business service leads from public requirements.

Sections:
1. Executive Dashboard (KPIs, category charts, intent/priority distribution)
2. Input Data Collection (built-in sample CSV & custom CSV upload with validation)
3. AI Analysis Studio (batch processing with progress tracking, rate-limiting, and error handling)
4. Lead Management (search, category/priority/intent filters, verification cards with verbatim evidence)
5. Export Data (CSV & OpenPyXL Excel downloads)
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
# Custom Styling
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1f77b4;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .badge-high {
        background-color: #28a745;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-medium {
        background-color: #fd7e14;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-low {
        background-color: #6c757d;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .disclaimer-banner {
        background-color: #e8f4fd;
        border: 1px solid #b6e0fe;
        color: #0c5460;
        padding: 10px 16px;
        border-radius: 6px;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Sidebar Configuration & System Health
# ---------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/business-network.png", width=64)
    st.title("Lead Discovery")
    st.caption("Internal Sales Intelligence Pipeline")

    st.markdown("---")
    st.subheader("🔑 API Configuration")

    detected_key = ai_analyzer.get_api_key()
    user_api_key = st.text_input(
        "Gemini API Key (Optional Override):",
        type="password",
        value="",
        placeholder="Paste key to override .env / secrets",
        help="Reads from .env or Streamlit Secrets by default. You can also paste an override key here for this session.",
    )
    effective_api_key = user_api_key.strip() if user_api_key.strip() else detected_key

    if effective_api_key:
        masked_key = effective_api_key[:4] + "..." + effective_api_key[-4:] if len(effective_api_key) > 8 else "***"
        st.success(f"API Key Detected: `{masked_key}`")
    else:
        st.warning("⚠️ No Gemini API Key detected.\nPlease configure `.env` or paste your key above.")

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
        "Gemini Model:",
        options=model_options,
        index=default_model_idx,
        help="Select the Gemini model. gemini-3.8-flash is preferred; if it experiences high demand or quota limits, gemini-3.5-flash is an active alternative.",
    )
    if model_option == "custom":
        custom_model = st.text_input("Enter custom model name:", value=configured_model)
        active_model = custom_model.strip()
    else:
        active_model = model_option

    st.markdown("---")
    st.subheader("⚙️ System Status")
    db_metrics = database.get_dashboard_metrics()
    st.write(f"📁 **Total Leads in DB:** {db_metrics['total_records']}")
    st.write(f"✅ **Processed Leads:** {db_metrics['processed_records']}")
    st.write(f"⏳ **Pending Leads:** {db_metrics['unprocessed_records']}")
    if db_metrics['failed_records'] > 0:
        st.write(f"❌ **Failed Leads:** {db_metrics['failed_records']}")

    if st.button("🗑️ Reset Local Database", help="Deletes all stored leads and re-creates empty schema."):
        database.reset_database()
        st.success("Database reset successfully.")
        st.rerun()

    st.markdown("---")
    st.caption(
        "**Cloud Persistence Note:**\n"
        "Streamlit Community Cloud runs in ephemeral containers. Runtime SQLite changes do not persist across app reboots."
    )

# ---------------------------------------------------------
# Top Header Banner
# ---------------------------------------------------------
st.title("💼 AI Lead Business Discovery System")
st.markdown(
    """
    <div class="disclaimer-banner">
        <strong>Notice:</strong> This is an <em>internal sales intelligence tool</em> built to analyze publicly available business requirements 
        and identify sales opportunities for digital services. It is <strong>NOT</strong> a public marketplace or website-building platform. 
        All demo records are clearly marked fictional examples.
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Main Tabs Navigation
# ---------------------------------------------------------
tab_dash, tab_ingest, tab_ai, tab_leads, tab_export = st.tabs([
    "📊 Executive Dashboard",
    "📥 Input Data Collection",
    "⚡ AI Analysis Studio",
    "📋 Lead Management",
    "📤 Export Data",
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
        st.metric(label="Total Processed", value=metrics["processed_records"], delta=f"{metrics['unprocessed_records']} pending")
    with kpi2:
        st.metric(label="Relevant Leads", value=metrics["relevant_opportunities"], delta=f"{round(metrics['relevant_opportunities'] / max(metrics['processed_records'], 1) * 100)}% fit")
    with kpi3:
        st.metric(label="High Priority", value=metrics["high_priority_leads"], delta="Score 80-100")
    with kpi4:
        st.metric(label="Medium Priority", value=metrics["medium_priority_leads"], delta="Score 50-79")
    with kpi5:
        st.metric(label="Active Buying Intent", value=metrics["active_intent_leads"], delta="Ready to hire")

    st.markdown("---")

    if metrics["processed_records"] == 0:
        st.info(
            "💡 **No leads have been analyzed yet.**\n\n"
            "1. Navigate to **'Input Data Collection'** to load sample leads or upload a CSV.\n"
            "2. Head to **'AI Analysis Studio'** to run Gemini classification and lead scoring."
        )
    else:
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("##### 📌 Opportunities by Service Category")
            cat_data = metrics["category_counts"]
            if cat_data:
                cat_df = pd.DataFrame(list(cat_data.items()), columns=["Category", "Count"])
                st.bar_chart(cat_df.set_index("Category"), color="#1f77b4")
            else:
                st.write("No category data available.")

        with col_chart2:
            st.markdown("##### 🎯 Priority & Intent Breakdown")
            tab_prio, tab_intent = st.tabs(["Priority Distribution", "Buying Intent"])
            with tab_prio:
                prio_data = metrics["priority_counts"]
                if prio_data:
                    prio_df = pd.DataFrame(list(prio_data.items()), columns=["Priority", "Count"])
                    st.bar_chart(prio_df.set_index("Priority"), color="#2ca02c")
            with tab_intent:
                intent_data = metrics["intent_counts"]
                if intent_data:
                    intent_df = pd.DataFrame(list(intent_data.items()), columns=["Intent", "Count"])
                    st.bar_chart(intent_df.set_index("Intent"), color="#ff7f0e")

# =========================================================
# TAB 2: INPUT DATA COLLECTION
# =========================================================
with tab_ingest:
    st.subheader("Data Ingestion & Schema Validation")
    st.markdown(
        "Choose to load the standard fictional demo dataset (24 realistic records) or upload your own CSV file. "
        "The system rigorously validates mandatory columns, filters empty requirements, and prevents duplicates."
    )

    data_source = st.radio(
        "Select Data Source:",
        ["Load Built-in Sample Dataset (24 Demo Records)", "Upload Custom CSV File"],
        horizontal=True,
    )

    target_df = None
    validation_status = False
    validation_message = ""
    stats_dict = {}

    if data_source == "Load Built-in Sample Dataset (24 Demo Records)":
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
                st.error(f"❌ Validation Failed:\n{validation_message}")
            else:
                st.success("✅ Uploaded CSV passed schema validation!")

    if validation_status and target_df is not None:
        st.markdown("#### Validation Statistics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Raw Rows", stats_dict.get("raw_count", 0))
        c2.metric("Valid Rows", stats_dict.get("valid_count", 0))
        c3.metric("Empty/Invalid Dropped", stats_dict.get("empty_dropped", 0))
        c4.metric("Duplicates Dropped", stats_dict.get("duplicates_dropped", 0))

        st.markdown("#### Data Preview (First 5 Rows)")
        st.dataframe(target_df.head(5), use_container_width=True)

        if st.button("📥 Import Validated Leads into Database", type="primary"):
            inserted, skipped = database.insert_leads_from_df(target_df)
            st.success(
                f"🎉 Ingestion complete! **{inserted}** new lead(s) inserted into the database. "
                f"**{skipped}** duplicate record(s) skipped."
            )
            time.sleep(1)
            st.rerun()

# =========================================================
# TAB 3: AI ANALYSIS STUDIO
# =========================================================
with tab_ai:
    st.subheader("Gemini AI Analysis & Deterministic Scoring Studio")
    st.markdown(
        "Execute AI classification using the official `google-genai` SDK and calculate deterministic 0–100 lead scores. "
        "Controlled batching is enforced to respect API rate limits and free-tier quotas. "
        "**Failed API calls are never replaced with fabricated results.**"
    )

    unprocessed_leads = database.get_unprocessed_leads()
    pending_count = len(unprocessed_leads)

    st.write(f"📊 **Unprocessed / Pending Leads:** `{pending_count}`")

    if pending_count == 0:
        st.success("🎉 All leads in the database have been analyzed! Head over to 'Lead Management' to review results.")
    else:
        st.markdown("#### Execution Settings")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            batch_choice = st.selectbox(
                "Batch Size:",
                options=["Test 3 Leads (Quick Sanity Check)", "Analyze 5 Leads", f"Analyze All ({pending_count} Leads)"],
                index=0,
            )
        with col_b2:
            pacing_delay = st.slider(
                "Rate-Limit Delay (Seconds between requests):",
                min_value=0.5,
                max_value=3.0,
                value=1.2,
                step=0.1,
                help="Adds a safe pause between Gemini API calls to safeguard free-tier quota.",
            )

        # Determine numeric limit
        if "3" in batch_choice:
            batch_limit = 3
        elif "5" in batch_choice:
            batch_limit = 5
        else:
            batch_limit = pending_count

        if st.button(f"🚀 Start Analysis for Next {min(batch_limit, pending_count)} Lead(s)", type="primary"):
            if not effective_api_key:
                st.error("❌ Cannot start analysis: Gemini API key is missing. Please configure GEMINI_API_KEY in `.env` or the sidebar.")
            else:
                leads_to_process = database.get_unprocessed_leads(limit=batch_limit)
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_expander = st.expander("Live Analysis Log", expanded=True)

                total_in_batch = len(leads_to_process)
                success_count = 0
                fail_count = 0

                for idx, lead in enumerate(leads_to_process):
                    b_name = lead["business_name"]
                    req_text = lead["requirement"]
                    lead_id = lead["id"]

                    status_text.markdown(f"**Analyzing {idx + 1}/{total_in_batch}:** `{b_name}`...")

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
                                f"✅ **{b_name}** | Category: `{analysis.get('category')}` | "
                                f"Intent: `{analysis.get('buying_intent')}` | "
                                f"Score: **{scoring_result['total_score']}/100** ({scoring_result['priority']})"
                            )
                    else:
                        fail_count += 1
                        database.mark_lead_failed(lead_id, error_msg)
                        with log_expander:
                            st.error(f"❌ **{b_name}** failed: {error_msg}")

                    # Update progress
                    progress_bar.progress((idx + 1) / total_in_batch)

                    # Pacing delay to avoid rate limit spikes
                    if idx < total_in_batch - 1:
                        time.sleep(pacing_delay)

                status_text.success(f"Batch completed! ✅ {success_count} succeeded, ❌ {fail_count} failed.")
                time.sleep(1.5)
                st.rerun()

# =========================================================
# TAB 4: LEAD MANAGEMENT & VERIFICATION
# =========================================================
with tab_leads:
    st.subheader("Lead Explorer & Opportunity Verification")
    st.markdown(
        "Inspect categorized business leads, review explainable score breakdowns, and verify the original source text."
    )

    all_leads_df = database.get_all_leads()

    if all_leads_df.empty:
        st.info("No leads found in database. Ingest leads in 'Input Data Collection' first.")
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
            st.metric("Pending Analysis", len(all_leads_df[all_leads_df["status"] == "unprocessed"]))
        with s_col5:
            st.metric("Failed Calls", len(all_leads_df[all_leads_df["status"] == "failed"]))

        st.markdown("---")

        # Search & Filter controls
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([2, 1.2, 1.2, 1, 1])
        with f_col1:
            search_query = st.text_input("🔍 Search by business, keyword, or location:", value="")
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

        st.caption(f"Showing **{len(filtered_df)}** of **{len(all_leads_df)}** leads (Filter: **{selected_status}**)")

        if filtered_df.empty:
            st.info("No leads match the current search and filter criteria.")
        else:
            # Display Detailed Lead Cards
            for _, lead in filtered_df.iterrows():
                status = lead.get("status", "unprocessed")
                priority = lead.get("priority", "Low")
                score = lead.get("lead_score", 0)
                category = lead.get("category", "Uncategorized")
                b_name = lead.get("business_name", "Unknown Business")

                if status == "processed":
                    status_icon = "✅"
                    header_title = f"{status_icon} {b_name} — Score: {score}/100 [{priority} Priority] | {category}"
                elif status == "failed":
                    status_icon = "❌"
                    header_title = f"{status_icon} {b_name} — [Analysis Failed - Click to inspect error] | {category}"
                else:
                    status_icon = "⏳"
                    header_title = f"{status_icon} {b_name} — [Pending AI Analysis] | Uncategorized"

                # Automatically expand all successfully processed leads (High and Medium priority)
                is_expanded = (status == "processed")
                with st.expander(header_title, expanded=is_expanded):
                    c_left, c_right = st.columns([3, 2])

                    with c_left:
                        st.markdown("##### 📝 Original Business Requirement")
                        st.info(f"\"{lead['requirement']}\"")

                        st.markdown("##### 🤖 AI Analysis Summary")
                        if lead.get("summary"):
                            st.write(lead["summary"])
                        elif status == "failed":
                            st.caption("Analysis could not be completed.")
                        else:
                            st.caption("Not analyzed yet or pending.")

                        st.markdown("##### 🔍 Verbatim Evidence (From Original Text)")
                        if lead.get("evidence"):
                            st.success(f"\"{lead['evidence']}\"")
                        elif status == "failed":
                            st.caption("No evidence available.")
                        else:
                            st.caption("No evidence extracted.")

                    with c_right:
                        st.markdown("##### 📌 Opportunity Breakdown")
                        st.write(f"• **Category:** `{lead.get('category', 'N/A')}`")
                        st.write(f"• **Relevance:** `{lead.get('relevance', 'Pending')}`")
                        st.write(f"• **Buying Intent:** `{lead.get('buying_intent', 'N/A')}`")
                        st.write(f"• **Location:** {lead.get('location', 'N/A')}")
                        st.write(f"• **Date Found:** {lead.get('date_found', 'N/A')}")

                        st.markdown("##### 🌐 Source Verification")
                        st.write(f"• **Source Platform:** {lead.get('source_name', 'N/A')}")
                        src_url = lead.get("source_url", "")
                        if src_url:
                            st.write(f"• **Source URL:** [{src_url}]({src_url})")

                        st.markdown("##### 📊 Explainable Score Reason")
                        if lead.get("score_explanation"):
                            st.markdown(f"> {lead['score_explanation']}")
                        elif status == "failed":
                            st.error(f"Analysis failed: {lead.get('error_message', 'Unknown error')}")
                        else:
                            st.caption("Pending AI analysis.")

# =========================================================
# TAB 5: EXPORT DATA
# =========================================================
with tab_export:
    st.subheader("Export Analyzed Leads")
    st.markdown(
        "Download processed leads as clean CSV or styled Excel (`.xlsx`) files for reporting and CRM integration."
    )

    export_scope = st.radio(
        "Select Export Dataset:",
        ["All Leads in Database", "Relevant Opportunities Only", "High Priority Leads Only (Score 80-100)"],
        horizontal=True,
    )

    base_df = database.get_all_leads()

    if base_df.empty:
        st.warning("Database contains no leads to export.")
    else:
        if export_scope == "Relevant Opportunities Only":
            export_df = base_df[base_df["relevance"] == "Relevant"].copy()
        elif export_scope == "High Priority Leads Only (Score 80-100)":
            export_df = base_df[base_df["priority"] == "High"].copy()
        else:
            export_df = base_df.copy()

        st.write(f"Export dataset contains **{len(export_df)}** records.")

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
                label="📥 Download CSV File",
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
                label="📊 Download Excel Spreadsheet (.xlsx)",
                data=excel_bytes,
                file_name=f"lead_discovery_export_{timestamp_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
