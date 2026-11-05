"""
ai_analyzer.py - Google Gemini AI Analysis Module

This module connects to the Google Gemini API using the official Google Gen AI SDK
(`google-genai`). It performs structured analysis on business requirements to determine:
1. Specific service requested
2. Relevant service category (from 6 exact categories)
3. Buying intent (Active, Potential, Unclear)
4. Business relevance (Relevant, Not Relevant)
5. Short evidence-based summary
6. Verbatim evidence quoted directly from the source requirement text

Crucial Design Decisions:
- Zero Fabrication: When the API fails or is not configured, errors are returned clearly.
  No mock or hallucinated leads are ever generated.
- Dual Secret Support: Checks both local `.env` and Streamlit Community Cloud `st.secrets`.
- Verbatim Evidence Enforcement: Directs Gemini to extract exact text substrings only.
- Configurable Model: Defaults to `gemini-3.8-flash`.
- Granular Error Diagnostics: Distinguishes 503 (Service Unavailable), 429 (Quota/Rate Limit),
  404 (Model Not Found), 403 (Permission Denied), and 400 (Invalid Request) with HTTP code,
  exception type, and safe sanitized error messages without exposing secret keys.
"""

from typing import Dict, Any, Optional, Tuple
import os
import json
import re
import time
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

# Official Google Gen AI SDK
try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
    from pydantic import BaseModel, Field
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    genai_errors = None

# Strict allowed service categories as required
ALLOWED_CATEGORIES = [
    "Website Development",
    "Mobile Application Development",
    "Web Application Development",
    "SEO Services",
    "Digital Marketing",
    "Not Relevant",
]

ALLOWED_BUYING_INTENT = ["Active", "Potential", "Unclear"]
ALLOWED_RELEVANCE = ["Relevant", "Not Relevant"]

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def sanitize_secret_text(text: str, secret_key: Optional[str] = None) -> str:
    """
    Guarantees that no raw API key or credential substring is present in the output.
    Redacts any passed secret_key as well as standard Google API key patterns (AIzaSy...).
    """
    if not text:
        return ""
    sanitized = str(text)
    if secret_key and secret_key in sanitized:
        sanitized = sanitized.replace(secret_key, "[REDACTED_API_KEY]")
    # Redact standard Google API Key pattern: AIzaSy + 33 chars
    sanitized = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "[REDACTED_API_KEY]", sanitized)
    return sanitized


def get_api_key() -> Optional[str]:
    """
    Retrieves the Gemini API key from environment variables or Streamlit secrets.
    Does NOT log or expose the raw key.
    """
    # 1. Check environment variable (from .env or OS environment)
    key = os.getenv("GEMINI_API_KEY")
    if key and key.strip() and key.strip() != "your_gemini_api_key_here":
        return key.strip()

    # 2. Check Streamlit Cloud Secrets if streamlit is active
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            cloud_key = st.secrets["GEMINI_API_KEY"]
            if cloud_key and cloud_key.strip():
                return cloud_key.strip()
    except Exception:
        pass

    return None


def get_configured_model() -> str:
    """
    Returns the configured Gemini model name.

    Precedence:
    1. Streamlit Secrets (GEMINI_MODEL) when available.
    2. Environment variable (GEMINI_MODEL).
    3. Default model (DEFAULT_MODEL = 'gemini-3.8-flash').

    Handles missing secrets safely and never exposes secrets.
    """
    # 1. Check Streamlit Cloud Secrets if available
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_MODEL" in st.secrets:
            secret_model = st.secrets["GEMINI_MODEL"]
            if secret_model and str(secret_model).strip():
                return str(secret_model).strip()
    except Exception:
        pass

    # 2. Check environment variable
    env_model = os.getenv("GEMINI_MODEL")
    if env_model and env_model.strip():
        return env_model.strip()

    # 3. Fallback to existing default model
    return DEFAULT_MODEL


# Define Pydantic schema for structured output enforcement
if HAS_GENAI:
    class RequirementAnalysisSchema(BaseModel):
        service_requested: str = Field(
            description="The specific service or task requested by the client (e.g. 'WordPress Website Redesign', 'Cross-Platform Mobile App', 'Janitorial Services')."
        )
        category: str = Field(
            description="Must be one of: 'Website Development', 'Mobile Application Development', 'Web Application Development', 'SEO Services', 'Digital Marketing', or 'Not Relevant'."
        )
        buying_intent: str = Field(
            description="Must be one of: 'Active' (ready to hire, immediate timeline, approved budget), 'Potential' (exploring options, future quarter), or 'Unclear' (vague mention, no clear purchasing signal)."
        )
        business_relevance: str = Field(
            description="Must be 'Relevant' if the requirement fits digital agency services (Web, Mobile, Web Apps, SEO, Digital Marketing). Must be 'Not Relevant' if outside this scope (e.g. plumbing, physical goods, cleaning)."
        )
        summary: str = Field(
            description="A concise 1-2 sentence evidence-based summary of what the business needs."
        )
        evidence: str = Field(
            description="EXACT verbatim quotation extracted directly from the requirement text demonstrating the need and timeline. Do NOT paraphrase or invent quotes."
        )


def analyze_lead_with_gemini(
    business_name: str,
    requirement: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Submits a single business requirement to Gemini for structured analysis.

    Args:
        business_name: Name of the business.
        requirement: The raw requirement description text.
        api_key: Optional explicit API key override (otherwise fetched securely).
        model_name: Optional model override (defaults to GEMINI_MODEL or gemini-3.8-flash).

    Returns:
        Tuple containing:
        - success (bool): True if analysis was successful.
        - analysis (dict or None): Dictionary with structured fields if successful.
        - error_message (str): Explanatory error message if failed, formatted with error type and status code.
    """
    if not HAS_GENAI:
        return False, None, "The 'google-genai' SDK is not installed. Please install dependencies from requirements.txt."

    effective_key = api_key or get_api_key()
    if not effective_key:
        return (
            False,
            None,
            "Gemini API key is not configured. Please set GEMINI_API_KEY in your .env file or Streamlit Cloud Secrets.",
        )

    model = model_name or get_configured_model()

    system_instruction = (
        "You are an expert sales intelligence AI analyst for a premier digital agency that offers: "
        "Website Design & Development, E-commerce Development, Mobile Application Development, Web Application Development, "
        "SEO Services, and Digital Marketing.\n\n"
        "Your task is to analyze raw public business requirements with extreme analytical rigor and objectivity.\n"
        "Rules:\n"
        "1. CATEGORY: You MUST choose exactly one of: 'Website Development', 'Mobile Application Development', 'Web Application Development', 'SEO Services', 'Digital Marketing', 'Not Relevant'.\n"
        "2. BUYING INTENT: Choose 'Active' (immediate hiring, RFP, active budget, urgent timeline), 'Potential' (evaluating solutions, planning for upcoming quarter), or 'Unclear' (exploratory, ambiguous).\n"
        "3. RELEVANCE: Choose 'Relevant' if it falls under the 5 core agency services, or 'Not Relevant' if it is outside scope (e.g. manufacturing, facilities, physical commodities, general office supplies).\n"
        "4. EVIDENCE: Extract a VERBATIM text quote directly from the requirement text. NEVER paraphrase or invent quotations.\n"
        "5. SUMMARY: 1-2 objective, factual sentences describing the opportunity."
    )

    prompt = (
        f"Business Name: {business_name}\n"
        f"Business Requirement: {requirement}\n\n"
        "Analyze this requirement and output structured JSON adhering to the required schema."
    )

    try:
        # Initialize the official Google Gen AI client
        client = genai.Client(api_key=effective_key)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,  # Low temperature for deterministic classification
            response_mime_type="application/json",
            response_schema=RequirementAnalysisSchema,
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        raw_text = response.text
        if not raw_text:
            return False, None, "Gemini returned an empty response."

        data = json.loads(raw_text)

        # Validate and normalize category
        cat = data.get("category", "Not Relevant").strip()
        matched_cat = next((c for c in ALLOWED_CATEGORIES if c.lower() == cat.lower()), None)
        if not matched_cat:
            # Fallback based on relevance
            matched_cat = "Not Relevant" if data.get("business_relevance") == "Not Relevant" else "Website Development"
        data["category"] = matched_cat

        # Normalize buying intent
        intent = data.get("buying_intent", "Unclear").strip().capitalize()
        if intent not in ALLOWED_BUYING_INTENT:
            intent = "Unclear"
        data["buying_intent"] = intent

        # Normalize business relevance
        relevance = data.get("business_relevance", "Not Relevant").strip().title()
        if relevance not in ALLOWED_RELEVANCE:
            relevance = "Relevant" if matched_cat != "Not Relevant" else "Not Relevant"
        data["business_relevance"] = relevance

        # Consistency check: if Not Relevant, relevance cannot be Relevant
        if data["category"] == "Not Relevant":
            data["business_relevance"] = "Not Relevant"
        elif data["business_relevance"] == "Not Relevant":
            data["category"] = "Not Relevant"

        # Evidence safety check: ensure evidence is not empty
        if not data.get("evidence"):
            data["evidence"] = requirement[:150]

        return True, data, ""

    except Exception as e:
        # Check if it is a google.genai APIError (or subclass ServerError, ClientError)
        is_api_err = genai_errors and isinstance(e, genai_errors.APIError)
        err_type = type(e).__name__
        http_code = getattr(e, "code", None)
        api_status = getattr(e, "status", None)
        raw_msg = getattr(e, "message", str(e))
        safe_msg = sanitize_secret_text(raw_msg, effective_key)
        full_err_str = sanitize_secret_text(str(e), effective_key)

        # Extract HTTP status code from error string if not directly populated
        if not http_code:
            for code_cand in [503, 429, 404, 403, 400]:
                if str(code_cand) in full_err_str:
                    http_code = code_cand
                    break

        # 1. 503 Service Unavailable / Capacity Spikes
        if http_code == 503 or api_status == "UNAVAILABLE" or "503" in full_err_str or "temporarily unavailable" in safe_msg.lower():
            formatted_err = (
                f"Gemini API 503 Service Unavailable [{err_type}]: {safe_msg}\n"
                f"Google's servers are experiencing high demand for model '{model}'. "
                "Spikes are usually temporary. Please retry shortly or switch to another active model in the sidebar (e.g., gemini-3.5-flash)."
            )

        # 2. 429 Quota Exceeded / Rate Limit
        elif http_code == 429 or api_status == "RESOURCE_EXHAUSTED" or "429" in full_err_str or "quota" in safe_msg.lower() or "rate limit" in safe_msg.lower():
            formatted_err = (
                f"Gemini API 429 Quota/Rate Limit Exceeded [{err_type}]: {safe_msg}\n"
                f"The free-tier quota for model '{model}' has been reached. "
                "Please wait for your quota to replenish, increase pacing delay, or switch to an alternative model (e.g., gemini-3.5-flash)."
            )

        # 3. 404 Model Not Found / Retired
        elif http_code == 404 or api_status == "NOT_FOUND" or "404" in full_err_str or "not found" in safe_msg.lower():
            formatted_err = (
                f"Gemini API 404 Model Not Found [{err_type}]: {safe_msg}\n"
                f"The model '{model}' does not exist or is no longer accessible to your API key. "
                "Please select an active model from the sidebar."
            )

        # 4. 403 Permission Denied
        elif http_code == 403 or api_status == "PERMISSION_DENIED" or "403" in full_err_str or "permission" in safe_msg.lower():
            formatted_err = (
                f"Gemini API 403 Permission Denied [{err_type}]: {safe_msg}\n"
                "Your API key does not have permission to access this model or project. "
                "Please check your Google AI Studio project settings and key permissions."
            )

        # 5. 400 Invalid Request / Bad Argument / Invalid Key Format
        elif http_code == 400 or api_status == "INVALID_ARGUMENT" or "400" in full_err_str or "invalid" in safe_msg.lower():
            formatted_err = (
                f"Gemini API 400 Invalid Request [{err_type}]: {safe_msg}\n"
                "The request format or API key format was rejected. Please verify your GEMINI_API_KEY."
            )

        # 6. Network connectivity issues
        elif "connect" in err_type.lower() or "getaddrinfo" in safe_msg.lower():
            formatted_err = (
                f"Network Connection Error [{err_type}]: Unable to reach Google Gemini API servers. "
                "Please check your internet connection or proxy settings."
            )

        # 7. Other general API or runtime errors
        else:
            status_desc = f" ({api_status})" if api_status else ""
            code_desc = f" {http_code}" if http_code else ""
            formatted_err = f"Gemini API Error{code_desc}{status_desc} [{err_type}]: {safe_msg}"

        return False, None, formatted_err
