# AI Lead Business Discovery System 💼🚀

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg)](https://streamlit.io/)
[![Google Gen AI SDK](https://img.shields.io/badge/Google%20Gen%20AI-SDK%20v1.0+-4285F4.svg)](https://github.com/google-gemini/generative-ai-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An internal AI-powered sales intelligence dashboard for digital agencies. The system ingests publicly available business requirements, cleans and deduplicates them, uses Google Gemini to extract structured purchasing intent and verbatim evidence, and computes an explainable 0–100 lead score using a deterministic Python algorithm.

> ⚠️ **Important Scope Clarification:** This is an **internal sales intelligence pipeline**, NOT a public freelance marketplace or a website builder. All demo data records are clearly labeled fictional examples with demonstrative URLs.

---

## 📑 Table of Contents

- [1. Business Objective & Core Services](#1-business-objective--core-services)
- [2. System Architecture & Data Flow](#2-system-architecture--data-flow)
- [3. Technology Stack](#3-technology-stack)
- [4. Project Structure](#4-project-structure)
- [5. Installation & Local Setup](#5-installation--local-setup)
- [6. Gemini API Configuration & Security](#6-gemini-api-configuration--security)
- [7. How to Use the System](#7-how-to-use-the-system)
- [8. Gemini AI Analysis Specification](#8-gemini-ai-analysis-specification)
- [9. Explainable Lead Scoring Rubric (0–100)](#9-explainable-lead-scoring-rubric-0100)
- [10. Data Export (CSV & Excel)](#10-data-export-csv--excel)
- [11. Assumptions & Limitations](#11-assumptions--limitations)
- [12. Cloud Deployment (Streamlit Community Cloud)](#12-cloud-deployment-streamlit-community-cloud)
- [13. Beginner's Interview Guide & Talking Points](#13-beginners-interview-guide--talking-points)

---

## 1. Business Objective & Core Services

Digital service agencies often waste hundreds of business development hours sifting through unstructured RFP listings, message boards, and public forums to find qualified client leads. 

This system automates that qualification workflow for a digital agency offering:
1. **Website Design & Development** (Corporate sites, redesigns, CMS implementations)
2. **E-commerce Website Development** (Shopify, WooCommerce, payment gateways, product catalogs)
3. **Mobile Application Development** (iOS, Android, Flutter, React Native apps)
4. **SEO Services** (Technical audits, local SEO, schema markup, organic search rankings)
5. **Digital Marketing** (PPC campaigns, Google Ads, LinkedIn paid ads, attribution tracking)

---

## 2. System Architecture & Data Flow

```
+---------------------------------------------------------------------------------+
|                                 DATA INGESTION                                  |
|  - Built-in Sample CSV (24 realistic demo records) OR Custom User Upload        |
|  - Schema Validation (Required Columns, String Sanitization, Type Conversion)   |
|  - Ingestion Filters: Drop Empty Requirements & Deduplicate Existing Records   |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                               PERSISTENCE LAYER                                 |
|  - SQLite Database (`leads.db`): Auto-initialized with unique constraints       |
|  - Prevents redundant duplicate AI calls                                       |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                              AI INTELLIGENCE LAYER                              |
|  - Official Google Gen AI SDK (`google-genai`)                                  |
|  - Configurable Model: Defaults to `gemini-3.8-flash`                           |
|  - Strict JSON Output Schema (Category, Intent, Relevance, Summary, Evidence)   |
|  - Zero Fabrication: Clear errors on API rate limit or auth failure             |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                          DETERMINISTIC LEAD SCORING                             |
|  - 100% Python-Calculated 0–100 Rubric (Never guessed by LLM arithmetic)        |
|  - Relevance (30 pts) + Intent (30 pts) + Clarity (20 pts)                     |
|    + Technical Features (10 pts) + Timeline / Urgency Evidence (10 pts)         |
|  - Priority Classification: High (80-100), Medium (50-79), Low (0-49)          |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                            STREAMLIT USER INTERFACE                             |
|  - Tab 1: Executive KPI Metrics & Category Distribution Visualizations          |
|  - Tab 2: CSV Validation Preview & Database Import Station                      |
|  - Tab 3: Controlled Batch AI Analyzer with Pacing Sliders & Real-Time Logs    |
|  - Tab 4: Searchable & Filterable Lead Explorer with Verbatim Proof Cards       |
|  - Tab 5: Downloadable CSV and Formatted Excel (.xlsx via OpenPyXL) Reports     |
+---------------------------------------------------------------------------------+
```

---

## 3. Technology Stack

Strict adherence to lightweight, Python-native technologies:

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.10 – 3.13 | Universal compatibility across local OS and Streamlit Cloud. |
| **User Interface** | Streamlit | Rapid, responsive web dashboard without Node.js or React overhead. |
| **AI Engine** | Google Gemini API | High-speed semantic reasoning and structured JSON output. |
| **AI SDK** | `google-genai` (Official) | Google's official next-generation Gen AI Python SDK. |
| **Data Processing** | Pandas | High-performance tabular transformation and validation. |
| **Database** | SQLite3 (`sqlite3`) | Built-in Python zero-configuration ACID-compliant SQL engine. |
| **Spreadsheet Engine** | OpenPyXL | Generates native Microsoft Excel `.xlsx` workbooks. |
| **Secrets Management** | `python-dotenv` | Loads environment variables locally without leaking credentials. |

---

## 4. Project Structure

```
AI-Lead-Business-Discovery-System/
├── app.py                  # Streamlit multi-tab dashboard interface
├── ai_analyzer.py          # Google Gen AI SDK integration & structured schema
├── lead_scoring.py         # 100% Python deterministic scoring engine & explainability
├── data_processor.py       # CSV validation, sanitization, and deduplication pipeline
├── database.py             # SQLite persistence, queries, and aggregations
├── requirements.txt        # Pinned dependencies compatible with Python 3.10+
├── .env.example            # Environment configuration template
├── .gitignore              # Protects .env, secrets, and SQLite files from Git
├── README.md               # Technical documentation & interview guide
└── data/
    └── sample_leads.csv    # 24 realistic fictional demo business requirements
```

---

## 5. Installation & Local Setup

### Step 1: Clone or Open the Repository
```bash
cd d:/AI-Lead-Business-Discovery-System
```

### Step 2: Create and Activate a Virtual Environment (Recommended)
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

---

## 6. Gemini API Configuration & Security

1. Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Copy the example configuration file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and add your key:
   ```ini
   GEMINI_API_KEY=AIzaSyYourActualKeyHere
   GEMINI_MODEL=gemini-3.8-flash
   ```

### 🔒 Security Guarantee
- `.env`, `.env.local`, and `*.db` are strictly excluded in `.gitignore`.
- Raw API keys are **never** logged to the terminal or exposed in the UI.
- The dashboard automatically detects keys from either local `.env` or Streamlit Cloud Secrets.
- Users can also paste a temporary session override key in the sidebar if running in demonstration mode.

---

## 7. How to Use the System

### Start the Application
Run the Streamlit dashboard:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### Recommended Walkthrough
1. **Explore Data Collection (Tab 2)**:
   - Click **"Load Built-in Sample Dataset (24 Demo Records)"**.
   - Review the validation statistics.
   - Click **"Import Validated Leads into Database"**.
2. **Execute AI Analysis (Tab 3)**:
   - Select **"Test 3 Leads (Quick Sanity Check)"** or **"Analyze 5 Leads"**.
   - Set the rate-limit delay slider (e.g. 1.2s per call).
   - Click **"Start Analysis"** to watch the real-time progress bar and classification log.
3. **Inspect Leads (Tab 4)**:
   - Search by keyword (e.g., *"Shopify"*, *"Mobile"*, *"SEO"*).
   - Filter by Category or Priority.
   - Open any lead card to inspect the verbatim evidence quote and itemized point breakdown.
4. **Export Results (Tab 5)**:
   - Download the analyzed results as CSV or formatted Excel (`.xlsx`).

---

## 8. Gemini AI Analysis Specification

The system uses `google.genai.Client` with strict Pydantic schema validation:

```python
class RequirementAnalysisSchema(BaseModel):
    service_requested: str
    category: str  # Must match 1 of 6 exact categories
    buying_intent: str  # 'Active', 'Potential', or 'Unclear'
    business_relevance: str  # 'Relevant' or 'Not Relevant'
    summary: str  # Concise 1-2 sentence overview
    evidence: str  # Exact verbatim substring from source requirement
```

### Strict Service Categories
1. `Website Development`
2. `Mobile Application Development`
3. `Web Application Development`
4. `SEO Services`
5. `Digital Marketing`
6. `Not Relevant` *(Critical for filtering out-of-scope noise like plumbing or office equipment)*

---

## 9. Explainable Lead Scoring Rubric (0–100)

Lead scores are computed via deterministic Python logic in [`lead_scoring.py`](lead_scoring.py):

| Component | Max Points | Criteria & Logic |
| :--- | :---: | :--- |
| **Service Relevance** | **30** | Relevant agency scope = 30 pts; Not Relevant = 0 pts. |
| **Buying Intent** | **30** | Active (urgent/budgeted) = 30 pts; Potential = 15 pts; Unclear = 0 pts. |
| **Requirement Clarity** | **20** | Detailed (>120 chars) = 20 pts; Moderate (50-120 chars) = 10 pts; Vague = 0 pts. |
| **Specific Features** | **10** | ≥2 tech keywords (Stripe, API, iOS, SEO audit) = 10 pts; 1 feature = 5 pts; 0 = 0 pts. |
| **Timeline / Urgency** | **10** | Verified deadline evidence ("ASAP", "within 6 weeks") = 10 pts; No evidence = 0 pts. |

### Priority Brackets
- 🟢 **High Priority**: 80 – 100
- 🟠 **Medium Priority**: 50 – 79
- ⚪ **Low Priority**: 0 – 49

### Sample Itemized Audit Trail
```text
Score: 90/100 (High Priority) | Relevance: 30/30 (Relevant service match (+30)) | 
Intent: 30/30 (Active intent (+30)) | Clarity: 10/20 (Moderate description (118 chars, +10)) | 
Features: 10/10 (Specific features (stripe, mobile app, +10)) | 
Timeline: 10/10 (Verified urgency/deadline ('urgent', +10))
```

---

## 10. Data Export (CSV & Excel)

- **CSV Export**: Standard UTF-8 encoded comma-separated values file compatible with HubSpot, Salesforce, and Zoho CRM.
- **Excel Export**: Native Microsoft Excel workbook (`.xlsx`) generated using OpenPyXL with formatted headers, auto-fit columns, and structured sheets.

---

## 11. Assumptions & Limitations

1. **Cloud Persistence (Streamlit Community Cloud)**:
   - Streamlit Community Cloud hosts apps in ephemeral container instances. SQLite database files stored on disk will reset if the cloud app reboots or enters a sleep state.
   - For enterprise production deployments, connect SQLite to a managed remote SQL database (e.g. Cloud SQL or RDS).
2. **Rate Limits on Free Tier**:
   - The free Gemini tier enforces rate limits (e.g. 15 requests/minute). The application includes adjustable pacing sliders (0.5s–3.0s) and batching options (3, 5, or all) to avoid hitting HTTP 429 errors.
3. **Fictional Demo Data**:
   - The included dataset contains 24 simulated requirements using `https://example.com/demo-rfp/...` URLs to demonstrate system features without scraping private information.

---

## 12. Cloud Deployment (Streamlit Community Cloud)

1. Push your repository to GitHub (ensure `.env` and `*.db` are ignored).
2. Visit [share.streamlit.io](https://share.streamlit.io/) and log in with GitHub.
3. Select this repository, branch `main`, and main file path `app.py`.
4. Under **Advanced Settings > Secrets**, enter your Gemini API key:
   ```toml
   GEMINI_API_KEY = "AIzaSyYourActualKeyHere"
   GEMINI_MODEL = "gemini-3.8-flash"
   ```
5. Click **Deploy!**

---

## 13. Beginner's Interview Guide & Talking Points

When presenting this project in a technical interview, use these structured talking points:

### Q1: "Why decouple the AI categorization from the Lead Scoring algorithm?"
> *"LLMs excel at natural language comprehension—understanding that 'Shopify inventory synchronization' belongs to E-commerce Development. However, LLMs are notoriously inconsistent at mathematical arithmetic and lead scoring. If you ask an LLM to score a lead from 1 to 100, the same lead could receive an 85 today and a 62 tomorrow. By letting Gemini handle qualitative extraction (intent, relevance, verbatim evidence) and using a pure Python mathematical algorithm for scoring, our scoring engine is 100% deterministic, explainable, and compliance-ready."*

### Q2: "How do you prevent the AI from hallucinating or making up evidence?"
> *"In our system instructions and Pydantic schema, we explicitly restrict the evidence field to verbatim text extracts. We also mandate that if a prospect does not state an explicit deadline or timeframe, 0 timeline points are awarded. In addition, when the Gemini API encounters rate limits or errors, our system records the failure status rather than silently fabricating mock results."*

### Q3: "Why choose SQLite over Postgres for this architecture?"
> *"For an internal single-node sales intelligence tool processing daily lead batches, SQLite provides zero-configuration, serverless, atomic ACID compliance with zero infrastructure overhead. It keeps the prototype completely self-contained and easy to review without spinning up external Docker containers or managed database servers."*
