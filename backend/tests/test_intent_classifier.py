from app.agents.intent_classifier import classify_intent


def test_incident_investigation_intent():
    r = classify_intent("Why did the payment service fail?")
    assert r.intent == "investigate"
    assert r.domain == "incident"
    assert r.confidence >= 0.55


def test_sprint_prediction_intent():
    r = classify_intent("Will we finish the sprint?")
    assert r.intent == "predict"
    assert r.domain == "project"


def test_create_issue_is_write_and_medium_risk():
    r = classify_intent("Create an issue for this problem and assign it to Ahmed")
    assert r.requires_write is True
    assert r.risk_level in {"medium", "high"}  # "assign" alone maps medium; combined phrase may vary


def test_deploy_is_high_risk():
    r = classify_intent("Deploy this to production")
    assert r.risk_level == "high"


def test_low_confidence_fallback():
    r = classify_intent("hello there")
    assert r.confidence < 0.55
    assert r.intent == "query"
