from datetime import datetime, timedelta

from app.models.entities import Project, Issue
from app.intelligence.predictive import SprintRiskPredictor


def test_no_data_returns_neutral_50_percent(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    predictor = SprintRiskPredictor(db_session)

    result = predictor.predict(project.id, "99")

    assert result.completion_probability == 0.5
    assert "No issues found" in result.risk_factors[0]


def test_mostly_done_sprint_predicts_high_completion(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    for i in range(8):
        db_session.add(Issue(project_id=project.id, provider="taiga", external_id=str(i),
                              title=f"T{i}", status="done", sprint="1", priority="low"))
    db_session.add(Issue(project_id=project.id, provider="taiga", external_id="9",
                          title="T9", status="open", sprint="1", priority="low"))
    db_session.commit()

    predictor = SprintRiskPredictor(db_session)
    result = predictor.predict(project.id, "1")

    assert result.completion_probability > 0.6
    assert result.features["remaining_fraction"] < 0.2


def test_overdue_and_high_priority_work_predicts_low_completion(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    for i in range(5):
        db_session.add(Issue(
            project_id=project.id, provider="taiga", external_id=str(i), title=f"T{i}",
            status="open", sprint="1", priority="critical",
            due_date=datetime.utcnow() - timedelta(days=2),
        ))
    db_session.commit()

    predictor = SprintRiskPredictor(db_session)
    result = predictor.predict(project.id, "1")

    assert result.completion_probability < 0.4
    assert len(result.risk_factors) >= 2


def test_features_and_model_note_are_always_present(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    db_session.add(Issue(project_id=project.id, provider="taiga", external_id="1",
                          title="T1", status="open", sprint="1"))
    db_session.commit()

    predictor = SprintRiskPredictor(db_session)
    result = predictor.predict(project.id, "1")

    assert set(result.features.keys()) == {
        "remaining_fraction", "velocity_delta", "overdue_fraction", "high_priority_unresolved_fraction",
    }
    assert "expert-elicited" in result.model_note
