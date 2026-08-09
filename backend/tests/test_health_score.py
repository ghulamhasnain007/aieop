from datetime import datetime, timedelta

from app.models.entities import Project, Issue, Repository, Build, Incident
from app.intelligence.health_score import ProjectHealthScorer, DEFAULT_WEIGHTS


def test_no_data_returns_neutral_defaults_not_zero(db_session):
    project = Project(name="Empty"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    scorer = ProjectHealthScorer(db_session)

    result = scorer.score(project.id)

    assert result.breakdown["sprint_health"] == 70.0
    assert result.breakdown["code_health"] == 70.0
    assert result.breakdown["incident_health"] == 100.0  # no incidents IS a real positive signal
    assert 0 <= result.total <= 100


def test_all_issues_done_gives_high_sprint_health(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    for i in range(5):
        db_session.add(Issue(project_id=project.id, provider="taiga", external_id=str(i),
                              title=f"T{i}", status="done"))
    db_session.commit()

    scorer = ProjectHealthScorer(db_session)
    result = scorer.score(project.id)

    assert result.breakdown["sprint_health"] == 100.0


def test_overdue_issues_lower_sprint_health(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    for i in range(5):
        db_session.add(Issue(project_id=project.id, provider="taiga", external_id=str(i),
                              title=f"T{i}", status="open", due_date=datetime.utcnow() - timedelta(days=1)))
    db_session.commit()

    scorer = ProjectHealthScorer(db_session)
    result = scorer.score(project.id)

    assert result.breakdown["sprint_health"] < 70.0  # worse than the no-data neutral default


def test_critical_open_incident_lowers_incident_health(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    db_session.add(Incident(project_id=project.id, title="Outage", severity="critical", status="open"))
    db_session.commit()

    scorer = ProjectHealthScorer(db_session)
    result = scorer.score(project.id)

    assert result.breakdown["incident_health"] == 75.0  # 100 - 25


def test_total_is_weighted_sum_of_breakdown(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    scorer = ProjectHealthScorer(db_session)
    result = scorer.score(project.id)

    expected = sum(result.breakdown[k] * DEFAULT_WEIGHTS[k] for k in result.breakdown)
    assert abs(result.total - round(expected, 1)) < 0.1


def test_custom_weights_are_respected(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    custom_weights = {"sprint_health": 1.0, "code_health": 0, "cicd_health": 0, "incident_health": 0, "security_health": 0}
    scorer = ProjectHealthScorer(db_session, weights=custom_weights)
    result = scorer.score(project.id)

    assert result.total == result.breakdown["sprint_health"]
