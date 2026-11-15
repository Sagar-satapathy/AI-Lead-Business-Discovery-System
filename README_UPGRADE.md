# AI Lead Business Discovery System - Enterprise Full-Stack Upgrade

An enterprise-grade, full-stack application for commercial B2B procurement discovery, AI intent classification, and deterministic 5-factor lead scoring.

---

## 1. System Architecture

```
AI-Lead-Business-Discovery-System/
├── backend/                       # Python + FastAPI REST API
│   ├── config.py                  # Environment settings, dual AI keys, database URLs
│   ├── db.py                      # Unified DB adapter (SQLite leads.db default + PostgreSQL)
│   ├── main.py                    # REST API endpoints & static SPA server
│   ├── services/
│   │   ├── ai_service.py          # OpenAI + Gemini + Deterministic Fallback NLP
│   │   ├── discovery_service.py   # Multi-source commercial B2B discovery engine
│   │   └── export_service.py      # Scoped CSV (UTF-8 BOM) & styled Excel (.xlsx)
│   └── tests/
│       ├── run_tests.py           # 10-suite backend verification runner
│       └── test_api.py            # Pytest test cases
│
├── frontend/                      # React 19 + TypeScript + Vite SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.tsx         # Brand header, AI status, theme toggle, GitHub link
│   │   │   ├── KPISection.tsx     # KPI metrics & category/priority distribution bars
│   │   │   ├── LeadExplorer.tsx   # Paginated leads table, search, filters, batch AI
│   │   │   ├── DiscoverySection.tsx # Commercial discovery search form & presets
│   │   │   ├── LeadDetailModal.tsx# Verbatim evidence & 5-factor scoring rubric audit
│   │   │   ├── IngestionSection.tsx # Drag-and-drop CSV upload & deduplication
│   │   │   └── ExportSection.tsx  # 4 export scopes, CSV/Excel download & confirm
│   │   ├── services/
│   │   │   └── api.ts             # Typed REST API client
│   │   ├── types/
│   │   │   └── index.ts           # Core TypeScript data schemas
│   │   ├── App.tsx                # Master enterprise layout & tab router
│   │   ├── index.css              # Light & Dark theme enterprise stylesheet
│   │   └── main.tsx               # Entrypoint
│   ├── vite.config.ts             # Vite configuration with /api backend proxy
│   └── package.json
│
├── app.py                         # Existing Streamlit application (100% Preserved)
├── database.py                    # Existing SQLite helper (100% Preserved)
├── ai_analyzer.py                 # Existing Gemini analyzer (100% Preserved)
├── lead_scoring.py                # Existing 5-factor scoring engine (100% Preserved)
├── data_processor.py              # Existing CSV ingestion validator (100% Preserved)
├── test_system.py                 # Existing integration test suite (100% Preserved & Passing)
└── leads.db                       # Preserved local SQLite database with all 41 historical records (strictly excluded from Git/GitHub)
```

---

## 2. Quick Start Guide

### Option A: Run Both Frontend & Backend Together (Port 8000)
The FastAPI backend serves the pre-built React application from `frontend/dist` directly:

```powershell
# 1. Start the FastAPI server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open **`http://localhost:8000`** in your browser.

---

### Option B: Run in Development Mode (Hot Reloading)

#### 1. Start the FastAPI Backend:
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API docs are available at **`http://localhost:8000/docs`**.

#### 2. Start the React Frontend:
```powershell
cd frontend
npm run dev
```
Open **`http://localhost:5173`** in your browser. API requests are automatically proxied to port 8000.

---

## 3. Existing Streamlit Application (Unchanged)

The original Streamlit application remains completely intact and functional:

```powershell
streamlit run app.py
```

---

## 4. Environment Configuration (`.env`)

Create or update `.env` in the project root:

```env
# Database (Defaults to SQLite leads.db)
# To use PostgreSQL, set:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/leads_db

# AI Provider Keys (Both Optional; Deterministic NLP fallback works out-of-the-box)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Preferred Provider: auto, openai, gemini, or fallback
AI_PROVIDER=auto
```

---

## 5. Verification & Testing

- **Backend API Test Suite (10/10 Suites Passed)**:
  ```powershell
  python backend/tests/run_tests.py
  ```
- **Frontend TypeScript Build (100% Clean)**:
  ```powershell
  cd frontend
  npm run build
  ```
- **Existing System Integration Tests (100% Passed)**:
  ```powershell
  python test_system.py
  ```
