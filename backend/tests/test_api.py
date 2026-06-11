"""API integration tests covering the full happy path + policy editing."""
from __future__ import annotations


def _sample_application(**over) -> dict:
    payload = {
        "reference": "TEST-APP",
        "business": {
            "legal_name": "Acme Excavation LLC",
            "industry": "construction",
            "state": "TX",
            "years_in_business": 6,
            "annual_revenue": 1200000,
        },
        "guarantor": {
            "full_name": "Pat Owner",
            "fico": 730,
            "is_homeowner": True,
            "is_us_citizen": True,
            "industry_experience_years": 10,
        },
        "business_credit": {"paynet_score": 690, "comparable_credit_pct": 80},
        "loan_request": {"amount": 120000, "term_months": 60},
        "equipment": {"equipment_type": "construction_equipment", "year": 2022,
                      "condition": "used"},
    }
    payload.update(over)
    return payload


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_lenders_seeded(client):
    res = client.get("/api/lenders")
    assert res.status_code == 200
    names = {ln["name"] for ln in res.json()}
    assert {"Stearns Bank", "Apex Commercial Capital", "Advantage+ Financing",
            "Citizens Bank", "Falcon Equipment Finance"} <= names


def test_rule_types_exposed(client):
    res = client.get("/api/rule-types")
    assert res.status_code == 200
    keys = {rt["key"] for rt in res.json()}
    assert {"min_fico", "loan_amount_range", "excluded_industries"} <= keys
    # each rule-type advertises its editable params
    min_fico = next(rt for rt in res.json() if rt["key"] == "min_fico")
    assert any(p["name"] == "min" for p in min_fico["params"])


def test_full_underwriting_flow(client):
    created = client.post("/api/applications", json=_sample_application())
    assert created.status_code == 201
    app_id = created.json()["id"]

    run = client.post(f"/api/applications/{app_id}/underwrite")
    assert run.status_code == 201
    body = run.json()
    assert body["status"] == "completed"
    assert body["lender_count"] == 5
    assert body["eligible_count"] >= 1

    results = body["results"]
    # ranked, eligible first
    assert results[0]["rank"] == 1
    assert results[0]["eligible"] is True
    # detailed per-criterion breakdown is present
    assert any(c["label"] for c in results[0]["criteria"])

    # results retrievable via the dedicated endpoint too
    run_id = body["id"]
    again = client.get(f"/api/runs/{run_id}/results")
    assert again.status_code == 200
    assert len(again.json()) == 5


def test_underwrite_incomplete_application_fails_validation(client):
    # No credit scores at all -> validation should fail the run.
    payload = _sample_application(
        guarantor={"full_name": "No Credit"},
        business_credit={},
    )
    app_id = client.post("/api/applications", json=payload).json()["id"]
    run = client.post(f"/api/applications/{app_id}/underwrite").json()
    assert run["status"] == "failed"
    assert "credit score" in (run["error"] or "").lower()


def test_edit_policy_threshold_changes_outcome(client):
    """Editing a rule's config (no code change) changes the matching outcome.

    Uses a self-contained lender so the test never mutates seed data other tests
    rely on — which is exactly how a real edit would be scoped to one lender.
    """
    created = client.post("/api/lenders", json={
        "name": "Edit Test Capital", "slug": "edit-test-capital",
        "programs": [{"name": "Standard", "rank": 1, "rules": [
            {"rule_type": "min_fico", "severity": "qualification", "config": {"min": 600}},
            {"rule_type": "loan_amount_range", "severity": "qualification",
             "config": {"min": 10000, "max": 50000}},
        ]}],
    }).json()
    rule = next(r for r in created["programs"][0]["rules"]
                if r["rule_type"] == "loan_amount_range")

    app_id = client.post("/api/applications", json=_sample_application(
        loan_request={"amount": 120000, "term_months": 60})).json()["id"]

    # Before edit: $120k exceeds the $50k cap -> ineligible.
    run = client.post(f"/api/applications/{app_id}/underwrite").json()
    before = next(r for r in run["results"] if r["lender_name"] == "Edit Test Capital")
    assert before["eligible"] is False

    # Edit the cap to $200k (pure data change) ...
    patched = client.patch(f"/api/rules/{rule['id']}",
                           json={"config": {"min": 10000, "max": 200000}})
    assert patched.status_code == 200

    # After edit: same application is now eligible.
    run2 = client.post(f"/api/applications/{app_id}/underwrite").json()
    after = next(r for r in run2["results"] if r["lender_name"] == "Edit Test Capital")
    assert after["eligible"] is True


def test_create_new_lender_via_api(client):
    payload = {
        "name": "Test Capital",
        "slug": "test-capital",
        "description": "Created in a test",
        "rules": [{"rule_type": "excluded_states", "severity": "knockout",
                   "config": {"states": ["FL"]}}],
        "programs": [{
            "name": "Standard", "rank": 1,
            "rules": [{"rule_type": "min_fico", "severity": "qualification",
                       "config": {"min": 650}},
                      {"rule_type": "loan_amount_range", "severity": "qualification",
                       "config": {"min": 5000, "max": 500000}}],
        }],
    }
    res = client.post("/api/lenders", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "test-capital"
    assert len(body["programs"]) == 1
    assert len(body["rules"]) == 1  # lender-level knockout
