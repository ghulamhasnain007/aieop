"""
Demo data seeder. Creates one realistic, interconnected scenario touching
every major feature so a first-time visitor sees a working product
instead of an empty database:

  - 4 services with a dependency chain (database <- payment-service <- api <- frontend)
  - A repository with commits, a build, and a production deployment
  - An alert 3 minutes after that deployment (feeds the Incident Agent /
    proactive detection / timeline reconstruction)
  - A sprint of issues with a mix of done/open/overdue (feeds health
    score, risk detection, predictive sprint risk)
  - A rollback-heavy second deployment history on payment-service (feeds
    deployment risk detection)
  - A runbook document (feeds the RAG knowledge base)

Idempotent: re-running returns the existing demo project instead of
creating duplicates.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.entities import (
    Project, Service, Repository, Commit, Build, Deployment, Alert, Issue,
)
from app.agents.incident_agent import IncidentAgent
from app.knowledge.rag_service import RagService

DEMO_PROJECT_NAME = "Payments Platform (Demo)"


def seed_demo_project(db: Session) -> dict:
    existing = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).first()
    if existing:
        service = db.query(Service).filter(
            Service.project_id == existing.id, Service.name == "payment-service"
        ).first()
        return {"project_id": existing.id, "service_id": service.id if service else None, "already_seeded": True}

    project = Project(
        name=DEMO_PROJECT_NAME,
        description="Seeded demo scenario - a payments platform with a live incident, "
                     "a sprint in progress, and a documented runbook.",
    )
    db.add(project); db.commit(); db.refresh(project)

    # --- dependency chain: database <- payment-service <- api <- frontend ---
    database = Service(project_id=project.id, name="database", owner="platform-team")
    db.add(database); db.commit(); db.refresh(database)

    payment_service = Service(project_id=project.id, name="payment-service",
                               owner="ahmed", depends_on=[database.id])
    db.add(payment_service); db.commit(); db.refresh(payment_service)

    api = Service(project_id=project.id, name="api", owner="sara", depends_on=[payment_service.id])
    db.add(api); db.commit(); db.refresh(api)

    frontend = Service(project_id=project.id, name="frontend", owner="sara", depends_on=[api.id])
    db.add(frontend); db.commit(); db.refresh(frontend)

    # --- repository + commit + build + deployment + alert -> live incident ---
    repo = Repository(project_id=project.id, provider="github",
                       external_id="acme/payments", name="payments")
    db.add(repo); db.commit(); db.refresh(repo)

    commit = Commit(repository_id=repo.id, sha="a1b2c3d4e5f6", author="ahmed",
                     message="Refactor token expiration handling",
                     committed_at=datetime.utcnow() - timedelta(hours=1))
    db.add(commit); db.commit(); db.refresh(commit)

    build = Build(repository_id=repo.id, provider="github_actions", external_id="run-382",
                  status="passed", triggered_by_commit_id=commit.id,
                  started_at=datetime.utcnow() - timedelta(minutes=50),
                  finished_at=datetime.utcnow() - timedelta(minutes=45))
    db.add(build); db.commit(); db.refresh(build)

    deploy_time = datetime.utcnow() - timedelta(minutes=40)
    deployment = Deployment(service_id=payment_service.id, build_id=build.id,
                             environment="production", status="completed", deployed_at=deploy_time)
    db.add(deployment); db.commit(); db.refresh(deployment)

    alert = Alert(service_id=payment_service.id, source="simulated", severity="critical",
                  message="Error rate for payment-service exceeded 5% threshold",
                  triggered_at=deploy_time + timedelta(minutes=3))
    db.add(alert); db.commit()

    # --- run the real incident agent so the seeded incident has genuine evidence ---
    incident_agent = IncidentAgent(db)
    from app.models.entities import Incident
    incident = Incident(project_id=project.id, service_id=payment_service.id,
                        title="Payment API failures", severity="critical",
                        opened_at=deploy_time + timedelta(minutes=4))
    result = incident_agent.investigate(payment_service.id, incident_title="Payment API failures")
    incident_agent.persist_root_cause(incident, result)

    # --- rollback-heavy deployment history on payment-service (deployment risk) ---
    for i in range(5):
        db.add(Deployment(
            service_id=payment_service.id, environment="production",
            status="completed", rolled_back=(i < 2),
            deployed_at=datetime.utcnow() - timedelta(days=i + 1),
        ))
    db.commit()

    # --- sprint issues: mix of done / open / overdue for health + prediction ---
    statuses_priorities = [
        ("done", "medium"), ("done", "medium"), ("done", "low"), ("done", "high"),
        ("open", "high"), ("open", "medium"),
    ]
    for i, (status, priority) in enumerate(statuses_priorities):
        due = datetime.utcnow() - timedelta(days=1) if (status == "open" and i == 4) else None
        db.add(Issue(
            project_id=project.id, provider="github", external_id=str(i + 1),
            title=[
                "Fix payment timeout handling", "Add retry logic to gateway",
                "Update API documentation", "Migrate to new auth provider",
                "Investigate elevated error rate", "Refactor checkout flow",
            ][i],
            status=status, priority=priority, sprint="14",
            assignee=["ahmed", "sara", "ahmed", "sara", "ahmed", "sara"][i],
            due_date=due,
        ))
    db.commit()

    # --- a runbook document for the knowledge base ---
    rag = RagService(db)
    rag.ingest_document(
        title="Payment Service Runbook",
        project_id=project.id,
        source="demo-seed",
        content=(
            "The payment service occasionally experiences elevated error rates after a deployment, "
            "usually related to token expiration or timeout handling changes.\n\n"
            "First response: check the Incident Center for an active investigation - the Incident "
            "Agent automatically correlates alerts with recent deployments and commits.\n\n"
            "If a rollback is recommended with confidence above 60%, escalate to the on-call "
            "engineer for approval before rolling back production.\n\n"
            "The payment service depends on the database service. If the database is degraded, "
            "payment-service, api, and frontend are all potentially affected - check the "
            "Dependencies panel to see the full blast radius before assuming payment-service "
            "itself is at fault."
        ),
    )

    return {"project_id": project.id, "service_id": payment_service.id, "already_seeded": False}
