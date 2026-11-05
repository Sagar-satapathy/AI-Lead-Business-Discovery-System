"""
lead_scoring.py - Deterministic Lead Scoring & Explainability Engine

This module implements the 100% Python-based, deterministic scoring algorithm
for business leads. It scores each lead on a 0 to 100 scale based on 5 objective factors:

1. Service Relevance (30 pts max)
   - Relevant: 30 pts
   - Not Relevant: 0 pts

2. Buying Intent (30 pts max)
   - Active: 30 pts
   - Potential: 15 pts
   - Unclear: 0 pts

3. Requirement Clarity (20 pts max)
   - High (>120 chars, detailed scope): 20 pts
   - Moderate (50-120 chars): 10 pts
   - Minimal (<50 chars): 0 pts

4. Specific Features Mentioned (10 pts max)
   - >=2 concrete technical features: 10 pts
   - 1 technical feature: 5 pts
   - 0 technical features: 0 pts

5. Timeline or Urgency Evidence (10 pts max)
   - Verified timeline/deadline/urgency evidence in text: 10 pts
   - No timeline evidence: 0 pts (NEVER assume urgency without evidence)

Priority Brackets:
- High: 80 – 100
- Medium: 50 – 79
- Low: 0 – 49
"""

from typing import Dict, Any, Tuple, List
import re

# Keywords indicating specific digital product & tech features
FEATURE_PATTERNS = [
    r"\b(payment gateway|stripe|paypal|apple pay|google pay|checkout|cart)\b",
    r"\b(portal|client login|authentication|role-based|sso|user auth)\b",
    r"\b(api|webhook|rest|graphql|sync|integration|erp|crm)\b",
    r"\b(mobile app|ios|android|flutter|react native)\b",
    r"\b(responsive|mobile-responsive|wcag|accessibility|ui\/ux|redesign)\b",
    r"\b(seo audit|local seo|backlink|schema|meta tags|core web vitals|google business)\b",
    r"\b(ppc|google ads|linkedin ads|meta ads|tiktok|campaign|cac|attribution)\b",
    r"\b(cms|wordpress|shopify|magento|woocommerce|webflow)\b",
    r"\b(telemetry|iot|gps tracking|push notifications|barcode|telehealth)\b",
    r"\b(subscription|recurring|booking form|appointment scheduling|intake form)\b",
]

# Strict patterns indicating explicit deadlines or urgency
TIMELINE_PATTERNS = [
    r"\b(asap|immediately|urgent|urgently|immediate start|ready to hire|hiring immediately)\b",
    r"\b(deadline|target launch|rollout required|must be completed|launch within)\b",
    r"\b(within\s+\d+\s+(?:days|weeks|months))\b",
    r"\b(by\s+(?:end of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december|q[1-4]|next month|this month|\d{1,2}(?:st|nd|rd|th)?))\b",
    r"\b(for\s+holiday\s+sales|launching in q[1-4]|planned for next quarter)\b",
]


def evaluate_features(text: str) -> Tuple[int, List[str]]:
    """Detects specific technical features mentioned in the requirement text."""
    found_features = []
    lower_text = text.lower()
    for pattern in FEATURE_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            found_features.append(match.group(0))

    feature_count = len(found_features)
    if feature_count >= 2:
        return 10, found_features
    elif feature_count == 1:
        return 5, found_features
    return 0, []


def evaluate_timeline(text: str, evidence: str) -> Tuple[int, str]:
    """
    Evaluates whether the requirement or AI-extracted evidence contains
    explicit, verified timeline/urgency indicators.
    Never assumes urgency without textual proof.
    """
    combined_text = f"{text} {evidence}".lower()
    for pattern in TIMELINE_PATTERNS:
        match = re.search(pattern, combined_text)
        if match:
            return 10, match.group(0)
    return 0, ""


def calculate_lead_score(
    requirement: str,
    ai_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculates the explainable lead score (0-100) using deterministic Python logic.

    Args:
        requirement: The raw requirement text.
        ai_analysis: Dictionary returned by analyze_lead_with_gemini.

    Returns:
        Dictionary containing:
        - total_score (int): 0 to 100
        - priority (str): 'High', 'Medium', or 'Low'
        - score_breakdown (dict): Points per rubric component
        - explanation (str): Human-readable audit trail explaining the score
    """
    relevance = ai_analysis.get("business_relevance", "Not Relevant")
    intent = ai_analysis.get("buying_intent", "Unclear")
    evidence = ai_analysis.get("evidence", "")

    # 1. Relevance Score (Max 30)
    if relevance == "Relevant":
        rel_score = 30
        rel_reason = "Relevant service match (+30)"
    else:
        rel_score = 0
        rel_reason = "Out of agency scope (+0)"

    # 2. Buying Intent Score (Max 30)
    if intent == "Active":
        intent_score = 30
        intent_reason = "Active intent (+30)"
    elif intent == "Potential":
        intent_score = 15
        intent_reason = "Potential/exploratory intent (+15)"
    else:
        intent_score = 0
        intent_reason = "Unclear intent (+0)"

    # 3. Requirement Clarity Score (Max 20)
    clean_req = requirement.strip()
    req_len = len(clean_req)
    if req_len >= 120:
        clarity_score = 20
        clarity_reason = f"Detailed specification ({req_len} chars, +20)"
    elif req_len >= 50:
        clarity_score = 10
        clarity_reason = f"Moderate description ({req_len} chars, +10)"
    else:
        clarity_score = 0
        clarity_reason = f"Brief/vague description ({req_len} chars, +0)"

    # 4. Specific Features Mentioned (Max 10)
    feat_score, detected_features = evaluate_features(clean_req)
    if feat_score == 10:
        feat_reason = f"Specific features ({', '.join(detected_features[:3])}, +10)"
    elif feat_score == 5:
        feat_reason = f"Single feature ({detected_features[0]}, +5)"
    else:
        feat_reason = "No specific features identified (+0)"

    # 5. Timeline or Urgency Evidence (Max 10)
    time_score, matched_term = evaluate_timeline(clean_req, evidence)
    if time_score == 10:
        time_reason = f"Verified urgency/deadline ('{matched_term}', +10)"
    else:
        time_reason = "No timeline evidence (+0)"

    # Calculate Total Score
    total_score = rel_score + intent_score + clarity_score + feat_score + time_score
    total_score = max(0, min(100, total_score))  # Clamp between 0 and 100

    # Determine Priority Level
    if total_score >= 80:
        priority = "High"
    elif total_score >= 50:
        priority = "Medium"
    else:
        priority = "Low"

    # Assemble Structured Breakdown
    breakdown = {
        "service_relevance": rel_score,
        "buying_intent": intent_score,
        "requirement_clarity": clarity_score,
        "specific_features": feat_score,
        "timeline_urgency": time_score,
        "detected_features": detected_features,
        "timeline_phrase": matched_term,
    }

    # Build human-readable explainability string
    explanation = (
        f"Score: {total_score}/100 ({priority} Priority) | "
        f"Relevance: {rel_score}/30 ({rel_reason}) | "
        f"Intent: {intent_score}/30 ({intent_reason}) | "
        f"Clarity: {clarity_score}/20 ({clarity_reason}) | "
        f"Features: {feat_score}/10 ({feat_reason}) | "
        f"Timeline: {time_score}/10 ({time_reason})"
    )

    return {
        "total_score": total_score,
        "priority": priority,
        "score_breakdown": breakdown,
        "explanation": explanation,
    }
