from datetime import datetime, timedelta

from app.models.entities import Project, Issue
from app.agents.project_agent import ProjectAgent


def test_sprint_risk_no_data_flags_it_explicitly(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    agent = ProjectAgent(db_session)

    result = agent.sprint_risk(project.id, "14")

    assert result.total_tasks == 0
    assert "No issues found" in result.risk_factors[0]


def test_sprint_risk_with_overdue_tasks_lowers_probability(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)

    db_session.add_all([
        Issue(project_id=project.id, provider="taiga", external_id="1", title="A",
              status="done", sprint="14"),
        Issue(project_id=project.id, provider="taiga", external_id="2", title="B",
              status="open", sprint="14", due_date=datetime.utcnow() - timedelta(days=2)),
        Issue(project_id=project.id, provider="taiga", external_id="3", title="C",
              status="open", sprint="14", due_date=datetime.utcnow() - timedelta(days=1)),
    ])
    db_session.commit()

    agent = ProjectAgent(db_session)
    result = agent.sprint_risk(project.id, "14")

    assert result.total_tasks == 3
    assert result.completed_tasks == 1
    assert result.overdue_tasks == 2
    assert any("overdue" in f for f in result.risk_factors)


def test_workload_by_assignee_excludes_completed(db_session):
    project = Project(name="P"); db_session.add(project); db_session.commit(); db_session.refresh(project)
    db_session.add_all([
        Issue(project_id=project.id, provider="taiga", external_id="1", title="A", status="open", assignee="sara"),
        Issue(project_id=project.id, provider="taiga", external_id="2", title="B", status="done", assignee="sara"),
        Issue(project_id=project.id, provider="taiga", external_id="3", title="C", status="open", assignee="ahmed"),
    ])
    db_session.commit()

    agent = ProjectAgent(db_session)
    workload = agent.workload_by_assignee(project.id)

    assert workload == {"sara": 1, "ahmed": 1}
