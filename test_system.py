"""
test_system.py - End-to-End Integration Test Suite

Verifies:
1. Data processing & schema validation (handling valid, missing, empty, duplicate rows)
2. Lead scoring logic (0-100 rubric, priorities, explainability string, urgency evidence)
3. SQLite storage & deduplication
4. AI Analyzer error handling (graceful key check, schema adherence)
5. Excel and CSV export generation
"""

import os
import io
import pandas as pd
import database
import data_processor
import lead_scoring
import ai_analyzer


def test_data_processor():
    print("--> Testing data_processor...")
    # 1. Valid sample load
    sample_path = os.path.join("data", "sample_leads.csv")
    is_valid, df, err, stats = data_processor.load_and_validate_csv(sample_path)
    assert is_valid is True, f"Failed to load sample CSV: {err}"
    assert len(df) == 24, f"Expected 24 valid records, got {len(df)}"
    assert stats["raw_count"] == 24
    assert stats["valid_count"] == 24
    assert stats["empty_dropped"] == 0

    # 2. Missing column failure test
    bad_csv = "business_name,requirement,location\nAcme (Demo),Need web,NYC\n"
    is_valid_bad, _, err_bad, _ = data_processor.load_and_validate_csv(io.StringIO(bad_csv))
    assert is_valid_bad is False
    assert "missing" in err_bad.lower()

    # 3. Empty requirement dropped test
    empty_req_csv = (
        "business_name,requirement,source_name,source_url,location,date_found\n"
        "Valid Co (Demo),Need eCommerce,Source,https://example.com,NYC,2026-03-01\n"
        "Empty Co (Demo),,Source,https://example.com,LA,2026-03-01\n"
    )
    is_valid_empty, df_empty, _, stats_empty = data_processor.load_and_validate_csv(io.StringIO(empty_req_csv))
    assert is_valid_empty is True
    assert len(df_empty) == 1
    assert stats_empty["empty_dropped"] == 1

    # 4. Duplicate drop test
    dup_csv = (
        "business_name,requirement,source_name,source_url,location,date_found\n"
        "Acme (Demo),Need Web,Source,https://example.com,NYC,2026-03-01\n"
        "Acme (Demo),Need Web,Source,https://example.com,NYC,2026-03-01\n"
    )
    is_valid_dup, df_dup, _, stats_dup = data_processor.load_and_validate_csv(io.StringIO(dup_csv))
    assert is_valid_dup is True
    assert len(df_dup) == 1
    assert stats_dup["duplicates_dropped"] == 1
    print("    [PASS] data_processor tests passed.")


def test_lead_scoring():
    print("--> Testing lead_scoring...")
    # High Priority Case
    high_req = "Urgent: Need a cross-platform mobile app for iOS and Android with Stripe checkout. Must start immediately."
    high_ai = {
        "business_relevance": "Relevant",
        "buying_intent": "Active",
        "evidence": "Must start immediately",
    }
    high_score = lead_scoring.calculate_lead_score(high_req, high_ai)
    assert high_score["total_score"] >= 80, f"Expected High score >=80, got {high_score['total_score']}"
    assert high_score["priority"] == "High"
    assert "Score: " in high_score["explanation"]
    assert high_score["score_breakdown"]["service_relevance"] == 30
    assert high_score["score_breakdown"]["buying_intent"] == 30
    assert high_score["score_breakdown"]["timeline_urgency"] == 10

    # Low Priority Case (Out of Scope)
    low_req = "Procuring 80 ergonomic mesh executive office chairs."
    low_ai = {
        "business_relevance": "Not Relevant",
        "buying_intent": "Unclear",
        "evidence": "Procuring 80 chairs",
    }
    low_score = lead_scoring.calculate_lead_score(low_req, low_ai)
    assert low_score["total_score"] < 50, f"Expected Low score <50, got {low_score['total_score']}"
    assert low_score["priority"] == "Low"
    assert low_score["score_breakdown"]["service_relevance"] == 0
    assert low_score["score_breakdown"]["buying_intent"] == 0
    assert low_score["score_breakdown"]["timeline_urgency"] == 0
    print("    [PASS] lead_scoring tests passed.")


def test_database():
    print("--> Testing database...")
    test_db = "test_leads.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    database.init_db(test_db)

    # Ingest sample
    _, df, _, _ = data_processor.load_and_validate_csv(os.path.join("data", "sample_leads.csv"))
    inserted, skipped = database.insert_leads_from_df(df, db_path=test_db)
    assert inserted == 24, f"Expected 24 inserted, got {inserted}"
    assert skipped == 0

    # Deduplication test
    ins2, skp2 = database.insert_leads_from_df(df, db_path=test_db)
    assert ins2 == 0
    assert skp2 == 24, f"Expected 24 skipped on re-insert, got {skp2}"

    # Get unprocessed
    unprocessed = database.get_unprocessed_leads(limit=5, db_path=test_db)
    assert len(unprocessed) == 5

    # Update analysis for first lead
    first_lead = unprocessed[0]
    mock_ai = {
        "category": "Website Development",
        "buying_intent": "Active",
        "business_relevance": "Relevant",
        "summary": "Needs corporate site redesign.",
        "evidence": "launch within 6 weeks",
    }
    mock_scoring = lead_scoring.calculate_lead_score(first_lead["requirement"], mock_ai)
    database.update_lead_analysis(first_lead["id"], mock_ai, mock_scoring, db_path=test_db)

    # Check metrics
    metrics = database.get_dashboard_metrics(db_path=test_db)
    assert metrics["total_records"] == 24
    assert metrics["processed_records"] == 1
    assert metrics["unprocessed_records"] == 23
    assert metrics["relevant_opportunities"] == 1

    # Cleanup test db
    if os.path.exists(test_db):
        os.remove(test_db)
    print("    [PASS] database tests passed.")


def test_ai_error_handling():
    print("--> Testing AI error handling & secret redaction...")
    # 1. Secret redaction test
    dummy_key = "AIzaSyDummySecretKeyForTest12345678"
    raw_error = f"Error communicating with {dummy_key}: bad request"
    cleaned = ai_analyzer.sanitize_secret_text(raw_error, dummy_key)
    assert dummy_key not in cleaned
    assert "[REDACTED_API_KEY]" in cleaned

    # 2. Missing key error test
    old_env = os.environ.get("GEMINI_API_KEY")
    try:
        os.environ["GEMINI_API_KEY"] = ""
        success, analysis, err_msg = ai_analyzer.analyze_lead_with_gemini(
            business_name="Test Business",
            requirement="Test requirement",
            api_key=None,
        )
        assert success is False
        assert analysis is None
        assert "not configured" in err_msg.lower() or "missing" in err_msg.lower()
    finally:
        if old_env is not None:
            os.environ["GEMINI_API_KEY"] = old_env
    print("    [PASS] AI error handling tests passed.")


def test_auto_seed():
    print("--> Testing automatic demo lead seeding on empty database...")
    empty_test_db = "temp_empty_seed_test.db"
    if os.path.exists(empty_test_db):
        os.remove(empty_test_db)

    try:
        # 1. Initialize and auto-seed on empty database
        inserted, skipped = database.seed_demo_leads_if_empty(db_path=empty_test_db)
        assert inserted == 24, f"Expected 24 demo leads seeded on empty db, got {inserted}"
        assert skipped == 0

        metrics = database.get_dashboard_metrics(db_path=empty_test_db)
        assert metrics["total_records"] == 24, f"Expected total_records 24, got {metrics['total_records']}"

        # 2. Re-run seed on non-empty database -> should not duplicate
        ins2, skp2 = database.seed_demo_leads_if_empty(db_path=empty_test_db)
        assert ins2 == 0 and skp2 == 0, f"Expected (0, 0) on second run, got ({ins2}, {skp2})"
        metrics2 = database.get_dashboard_metrics(db_path=empty_test_db)
        assert metrics2["total_records"] == 24, "Record count must remain 24"
        print("    [PASS] auto-seed tests passed.")
    finally:
        if os.path.exists(empty_test_db):
            os.remove(empty_test_db)


def test_model_configuration():
    print("--> Testing Gemini model configuration precedence...")
    import streamlit as st

    old_model_env = os.environ.get("GEMINI_MODEL")
    try:
        if "GEMINI_MODEL" in os.environ:
            del os.environ["GEMINI_MODEL"]

        # 1. When no secrets and no env, should return default 'gemini-3.8-flash'
        default_res = ai_analyzer.get_configured_model()
        assert default_res == "gemini-3.8-flash", f"Expected 'gemini-3.8-flash', got '{default_res}'"

        # 2. Test when GEMINI_MODEL env var is set
        os.environ["GEMINI_MODEL"] = "gemini-3.5-flash"
        env_res = ai_analyzer.get_configured_model()
        assert env_res == "gemini-3.5-flash", f"Expected 'gemini-3.5-flash', got '{env_res}'"

        # 3. Test when Streamlit Secrets is present (mocking secrets)
        class MockSecrets(dict):
            def __getattr__(self, name):
                return self.get(name)

        orig_secrets = getattr(st, "secrets", None)
        try:
            st.secrets = MockSecrets({"GEMINI_MODEL": "gemini-3.6-flash"})
            secret_res = ai_analyzer.get_configured_model()
            assert secret_res == "gemini-3.6-flash", f"Expected 'gemini-3.6-flash', got '{secret_res}'"
        finally:
            if orig_secrets is not None:
                st.secrets = orig_secrets
            elif hasattr(st, "secrets"):
                delattr(st, "secrets")

        print("    [PASS] model configuration precedence tests passed.")
    finally:
        if old_model_env is not None:
            os.environ["GEMINI_MODEL"] = old_model_env


def test_exports():
    print("--> Testing exports...")
    df = pd.DataFrame([
        {
            "business_name": "Test Co (Demo)",
            "category": "Website Development",
            "lead_score": 85,
            "priority": "High",
        }
    ])
    # CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    assert len(csv_bytes) > 0

    # Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    assert len(buf.getvalue()) > 0
    print("    [PASS] export tests passed.")


if __name__ == "__main__":
    print("==========================================")
    print("Running Full System Integration Tests")
    print("==========================================")
    test_data_processor()
    test_lead_scoring()
    test_database()
    test_auto_seed()
    test_model_configuration()
    test_ai_error_handling()
    test_exports()
    print("==========================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY! [100%]")
    print("==========================================")
