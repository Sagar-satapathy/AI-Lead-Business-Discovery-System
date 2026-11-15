import urllib.request
import json

payload = {
    "location": "Hyderabad, Telangana, India",
    "category": "Healthcare",
    "service": "Website Development",
    "auto_ingest": False,
    "limit": 10,
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/discover",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read())
    print("HTTP_STATUS:", r.status)
    print("STATS:", json.dumps(data["stats"], indent=2))
    print("CANDIDATES_COUNT:", len(data["candidates"]))
    print("\n================== LIVE RESULTS FROM MWMBL ==================")
    for i, c in enumerate(data["candidates"], 1):
        print(f"\n--- Opportunity #{i} ---")
        print(f"Business Name:       {c.get('business_name')}")
        print(f"Source URL:          {c.get('source_url')}")
        print(f"Source Domain:       {c.get('source_domain')}")
        print(f"Buying Intent:       {c.get('buying_intent')}")
        print(f"Verification Status: {c.get('verification_status')}")
        print(f"Is Live Discovery:   {c.get('is_live_discovery')}")
        print(f"Provider:            {c.get('provider_name')}")
        print(f"Search Query:        {c.get('search_query')}")
        print(f"Discovered At:       {c.get('discovered_at')}")
        print(f"Snippet / Evidence:  {c.get('evidence_text')}")
        print(f"Audit Notes:         {c.get('verification_notes')}")
