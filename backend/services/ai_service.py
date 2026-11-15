"""
backend/services/ai_service.py - Unified Multi-Provider AI Analysis Service

Integrates:
1. OpenAI API (gpt-4o-mini / gpt-4o) with structured JSON output and verbatim evidence enforcement.
2. Google Gemini API (gemini-3.8-flash) reusing existing robust genai integration with key redaction.
3. Deterministic Fallback NLP Analyzer (zero-dependency, rule-based classification when offline or keyless).
4. Deterministic 5-factor scoring engine integration via lead_scoring.py.
"""

from typing import Dict, Any, Optional, Tuple
import os
import json
import re
from backend.config import settings
from backend.db import update_lead_analysis, mark_lead_failed
import lead_scoring

# Strict Allowed Categories and Choices
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

SYSTEM_PROMPT = """You are an expert enterprise B2B procurement analyst and lead evaluator.
Evaluate the given business requirement for procurement of digital, software, web, mobile, SEO, or digital marketing services.

Return a valid JSON object with EXACTLY these keys:
{
  "specific_service": "Short title of requested service (e.g., E-commerce Redesign, iOS Driver App, B2B SEO)",
  "category": "Must be EXACTLY one of: Website Development, Mobile Application Development, Web Application Development, SEO Services, Digital Marketing, Not Relevant",
  "buying_intent": "Must be EXACTLY one of: Active, Potential, Unclear",
  "business_relevance": "Must be EXACTLY one of: Relevant, Not Relevant",
  "summary": "1-2 sentence concise, professional summary of what the business requires and why.",
  "evidence": "EXACT verbatim substring quote copied directly from the requirement text demonstrating their intent, features, or timeline. NEVER paraphrase or fabricate."
}

Rules:
- Category MUST match one of the 6 allowed values word-for-word.
- If the requirement is not asking for IT/software/digital services, set category='Not Relevant' and business_relevance='Not Relevant'.
- Evidence MUST be an exact verbatim substring from the requirement text.
"""


def _sanitize_secret(text: str) -> str:
    """Removes API keys from error messages."""
    if not text:
        return ""
    sanitized = str(text)
    if settings.OPENAI_API_KEY:
        sanitized = sanitized.replace(settings.OPENAI_API_KEY, "[REDACTED_OPENAI_KEY]")
    if settings.GEMINI_API_KEY:
        sanitized = sanitized.replace(settings.GEMINI_API_KEY, "[REDACTED_GEMINI_KEY]")
    sanitized = re.sub(r"sk-[A-Za-z0-9_-]{20,}", "[REDACTED_KEY]", sanitized)
    sanitized = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "[REDACTED_KEY]", sanitized)
    return sanitized


def analyze_with_openai(requirement: str, business_name: str = "") -> Tuple[bool, Dict[str, Any], str]:
    """
    Evaluates business requirement using OpenAI's API.
    Returns (success, result_dict, error_message).
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return False, {}, "OpenAI API key not configured in environment (OPENAI_API_KEY)."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = settings.OPENAI_MODEL or "gpt-4o-mini"

        user_content = f"Business Name: {business_name}\nRequirement Text:\n{requirement}"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Validate category
        if data.get("category") not in ALLOWED_CATEGORIES:
            data["category"] = "Not Relevant"
        if data.get("buying_intent") not in ALLOWED_BUYING_INTENT:
            data["buying_intent"] = "Unclear"
        if data.get("business_relevance") not in ALLOWED_RELEVANCE:
            data["business_relevance"] = "Not Relevant"

        # Check verbatim evidence
        evidence = data.get("evidence", "").strip()
        if evidence and evidence.lower() not in requirement.lower():
            # If not exact match, find nearest match or fallback to snippet
            words = evidence.split()
            matched = False
            for span_len in range(min(len(words), 8), 2, -1):
                sub = " ".join(words[:span_len])
                if sub.lower() in requirement.lower():
                    # extract exact case from requirement
                    start = requirement.lower().find(sub.lower())
                    data["evidence"] = requirement[start:start + len(sub)]
                    matched = True
                    break
            if not matched:
                data["evidence"] = requirement[:120].strip()

        data["provider"] = f"OpenAI ({model})"
        return True, data, ""

    except Exception as e:
        err = _sanitize_secret(str(e))
        return False, {}, f"OpenAI analysis error: {err}"


def analyze_with_gemini(requirement: str, business_name: str = "") -> Tuple[bool, Dict[str, Any], str]:
    """
    Evaluates business requirement using Google Gemini API.
    Reuses existing ai_analyzer logic.
    Returns (success, result_dict, error_message).
    """
    try:
        import ai_analyzer
        success, result, err = ai_analyzer.analyze_lead_with_gemini(requirement, business_name=business_name)
        if success and result:
            result["provider"] = f"Google Gemini ({settings.GEMINI_MODEL})"
            return True, result, ""
        return False, {}, _sanitize_secret(err)
    except Exception as e:
        return False, {}, f"Gemini analysis error: {_sanitize_secret(str(e))}"


def analyze_with_fallback_nlp(requirement: str, business_name: str = "") -> Tuple[bool, Dict[str, Any], str]:
    """
    Deterministic rule-based NLP classifier.
    Guarantees 100% reproducible, zero-external-call analysis with verbatim evidence extraction.
    """
    req_lower = requirement.lower()

    # Category matching
    cat_scores = {
        "Website Development": 0,
        "Mobile Application Development": 0,
        "Web Application Development": 0,
        "SEO Services": 0,
        "Digital Marketing": 0,
    }

    # Keyword rules
    if any(k in req_lower for k in ["website", "web design", "redesign", "wordpress", "shopify", "woocommerce", "landing page", "ecommerce store", "e-commerce website"]):
        cat_scores["Website Development"] += 3
    if any(k in req_lower for k in ["mobile app", "ios", "android", "flutter", "react native", "app store", "play store", "cross-platform app"]):
        cat_scores["Mobile Application Development"] += 4
    if any(k in req_lower for k in ["portal", "dashboard", "saas", "web app", "web application", "crm integration", "erp system", "api integration", "backend system", "cloud portal"]):
        cat_scores["Web Application Development"] += 4
    if any(k in req_lower for k in ["seo", "search engine", "ranking", "organic traffic", "backlink", "google business", "local search"]):
        cat_scores["SEO Services"] += 4
    if any(k in req_lower for k in ["digital marketing", "ppc", "google ads", "meta ads", "social media", "paid ads", "campaign", "lead gen"]):
        cat_scores["Digital Marketing"] += 3

    top_cat = max(cat_scores, key=cat_scores.get)
    if cat_scores[top_cat] > 0:
        category = top_cat
        relevance = "Relevant"
    else:
        category = "Not Relevant"
        relevance = "Not Relevant"

    # Buying Intent
    if any(k in req_lower for k in ["rfp", "urgently", "asap", "immediate", "seeking agency", "looking to hire", "quote", "proposal", "budget allocated", "vendor", "ready to hire", "contract"]):
        intent = "Active"
    elif any(k in req_lower for k in ["exploring", "considering", "planning", "interested", "evaluating", "reviewing", "next quarter"]):
        intent = "Potential"
    else:
        intent = "Active" if relevance == "Relevant" else "Unclear"

    # Extract verbatim evidence
    evidence = ""
    for kw in ["seeking", "urgently", "need", "require", "looking for", "rfp", "redesign", "develop", "portal", "mobile app", "seo", "launch"]:
        if kw in req_lower:
            start = req_lower.find(kw)
            # Find sentence or clause
            end = len(requirement)
            for punct in [".", ";", "\n", ","]:
                p_idx = requirement.find(punct, start + 30)
                if p_idx != -1 and p_idx < end:
                    end = p_idx
            evidence = requirement[start:min(start + 120, end)].strip()
            break

    if not evidence:
        evidence = requirement[:min(100, len(requirement))].strip()

    result = {
        "specific_service": f"{category} Requirement" if category != "Not Relevant" else "General Ingestion",
        "category": category,
        "buying_intent": intent,
        "business_relevance": relevance,
        "summary": f"{business_name or 'Business'} has requested digital assistance regarding: {evidence[:80]}...",
        "evidence": evidence,
        "provider": "Rule-Based Deterministic NLP",
    }

    return True, result, ""


def evaluate_lead(requirement: str, business_name: str = "", preferred_provider: Optional[str] = None) -> Tuple[bool, Dict[str, Any], Dict[str, Any], str]:
    """
    Main evaluation pipeline.
    Selects AI provider based on preference and key availability:
    1. 'openai' -> OpenAI
    2. 'gemini' -> Gemini
    3. 'auto' -> Tries OpenAI, then Gemini, then Fallback
    4. 'fallback' -> Fallback NLP

    Computes deterministic 5-factor score via lead_scoring.
    Returns (success, ai_analysis, scoring_result, error_message).
    """
    provider = (preferred_provider or settings.AI_PROVIDER).lower()
    success = False
    ai_result = {}
    err = ""

    if provider == "openai":
        success, ai_result, err = analyze_with_openai(requirement, business_name)
    elif provider == "gemini":
        success, ai_result, err = analyze_with_gemini(requirement, business_name)
    elif provider == "fallback":
        success, ai_result, err = analyze_with_fallback_nlp(requirement, business_name)
    else:  # 'auto'
        if settings.OPENAI_API_KEY:
            success, ai_result, err = analyze_with_openai(requirement, business_name)
        if not success and settings.GEMINI_API_KEY:
            success, ai_result, err = analyze_with_gemini(requirement, business_name)
        if not success:
            # Fallback to deterministic NLP
            success, ai_result, _ = analyze_with_fallback_nlp(requirement, business_name)
            err = ""

    if not success or not ai_result:
        return False, {}, {}, err or "AI evaluation failed across all configured providers."

    # Compute deterministic score
    scoring_result = lead_scoring.calculate_lead_score(requirement, ai_result)
    return True, ai_result, scoring_result, ""


def process_and_save_lead(lead_id: int, requirement: str, business_name: str = "", provider: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Evaluates a single lead and commits results into the database.
    Marks lead as failed if evaluation fails.
    """
    success, ai_result, scoring_result, err = evaluate_lead(requirement, business_name, preferred_provider=provider)
    if success:
        update_lead_analysis(lead_id, ai_result, scoring_result)
        return True, "Analysis completed successfully.", {
            "lead_id": lead_id,
            "ai_analysis": ai_result,
            "scoring": scoring_result,
        }
    else:
        mark_lead_failed(lead_id, err)
        return False, err, None
