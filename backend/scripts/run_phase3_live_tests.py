"""
backend/scripts/run_phase3_live_tests.py - Live Verification Runner for Phase 3
Runs 3 live searches on official Mwmbl JSON API:
1. Healthcare + Website Development + Hyderabad
2. Education + Website Development + Hyderabad
3. Retail + E-commerce Website Development + Hyderabad
"""

import sys
import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.services.mwmbl_provider import MwmblProvider

provider = MwmblProvider()

test_cases = [
    {
        "id": 1,
        "name": "Healthcare + Website Development + Hyderabad",
        "location": "Hyderabad, Telangana, India",
        "category": "Healthcare",
        "service": "Website Development",
    },
    {
        "id": 2,
        "name": "Education + Website Development + Hyderabad",
        "location": "Hyderabad, Telangana, India",
        "category": "Education",
        "service": "Website Development",
    },
    {
        "id": 3,
        "name": "Retail + E-commerce Website Development + Hyderabad",
        "location": "Hyderabad, Telangana, India",
        "category": "Retail & E-commerce",
        "service": "E-commerce Website Development",
    },
]

print("================================================================================")
print("PHASE 3 LIVE SEARCH VERIFICATION (OFFICIAL MWMBL PUBLIC REST API)")
print("================================================================================")

all_results = []

for tc in test_cases:
    print(f"\n>>> Executing Live Search #{tc['id']}: {tc['name']}")
    time.sleep(1.0)  # Gentle spacing for Mwmbl open-source endpoint
    candidates, meta = provider.search(
        location=tc["location"],
        category=tc["category"],
        service=tc["service"],
        num_results=10,
    )

    tc_res = {
        "id": tc["id"],
        "name": tc["name"],
        "primary_query": meta.get("query"),
        "queries_executed": meta.get("queries_executed", []),
        "raw_results_count": meta.get("raw_results_count", 0),
        "relevant_count": meta.get("relevant_count", 0),
        "unqualified_count": meta.get("unqualified_count", 0),
        "api_errors": meta.get("error"),
        "elapsed_ms": meta.get("elapsed_ms", 0),
        "candidates": candidates,
        "unqualified_sample": meta.get("unqualified_sample", []),
    }
    all_results.append(tc_res)

    print(f"  Primary Search Query:     '{tc_res['primary_query']}'")
    print(f"  All Queries Executed:     {tc_res['queries_executed']}")
    print(f"  Raw Results Retrieved:    {tc_res['raw_results_count']}")
    print(f"  Relevant Leads (Demand):  {tc_res['relevant_count']}")
    print(f"  Unqualified Filtered:     {tc_res['unqualified_count']}")
    print(f"  API Errors:               {tc_res['api_errors'] or 'None (HTTP 200)'}")
    print(f"  Latency:                  {tc_res['elapsed_ms']}ms")

    print("\n  --- Relevant Opportunities (Active / Potential) ---")
    if not candidates:
        print("  (No candidates met strict demand criteria - zero false positives claimed)")
    for i, c in enumerate(candidates, 1):
        print(f"    [{i}] Name:           {c.get('business_name')}")
        print(f"        URL:            {c.get('source_url')}")
        print(f"        Domain:         {c.get('source_domain')}")
        print(f"        Buying Intent:  {c.get('buying_intent')}")
        print(f"        Status:         {c.get('verification_status')}")
        print(f"        Class Reason:   {c.get('classification_reason')}")
        print(f"        Evidence:       \"{c.get('evidence_text', '')[:100]}...\"")

    print("\n  --- Sample Unqualified Results Filtered Out ---")
    for j, u in enumerate(tc_res["unqualified_sample"][:3], 1):
        print(f"    [{j}] URL:    {u.get('url')}")
        print(f"        Title:  {u.get('title')[:60]}")
        print(f"        Domain: {u.get('domain')}")
        print(f"        Reason: {u.get('reason')}")

# Save detailed output to file for presentation
with open("backend/scripts/phase3_live_results.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=2)

print("\nSaved full results to backend/scripts/phase3_live_results.json")
