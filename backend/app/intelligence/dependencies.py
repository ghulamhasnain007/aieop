"""
Dependency awareness (FR-037).

Answers: "Which components may be affected if service X fails?" by
traversing Service.depends_on (a simple adjacency list already in the
unified data model - see app.models.entities.Service). No separate graph
database needed at FYP scale; this is a plain in-memory BFS over
services belonging to the same project.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.entities import Service


@dataclass
class DependencyImpact:
    service_id: str
    service_name: str
    direct_dependencies: list[str] = field(default_factory=list)   # what this service depends on
    dependents: list[str] = field(default_factory=list)             # what would be affected if THIS fails
    unknown_service: bool = False


class DependencyAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def impact_of_failure(self, service_id: str) -> DependencyImpact:
        service = self.db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return DependencyImpact(service_id=service_id, service_name="unknown", unknown_service=True)

        all_services = self.db.query(Service).filter(Service.project_id == service.project_id).all()
        by_id = {s.id: s for s in all_services}

        # Reverse adjacency: for each service, who depends on it?
        dependents_map: dict[str, list[str]] = {s.id: [] for s in all_services}
        for s in all_services:
            for dep_id in (s.depends_on or []):
                if dep_id in dependents_map:
                    dependents_map[dep_id].append(s.id)

        # BFS outward from the failing service through the dependents graph
        # to find every service transitively affected.
        visited: set[str] = set()
        queue = [service_id]
        while queue:
            current = queue.pop(0)
            for dependent_id in dependents_map.get(current, []):
                if dependent_id not in visited:
                    visited.add(dependent_id)
                    queue.append(dependent_id)

        return DependencyImpact(
            service_id=service_id,
            service_name=service.name,
            direct_dependencies=[by_id[d].name for d in (service.depends_on or []) if d in by_id],
            dependents=[by_id[d].name for d in visited if d in by_id],
        )
