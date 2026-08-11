from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.integrations.github_sync import sync_repository, GitHubSyncError

router = APIRouter(prefix="/api/github", tags=["github"])


class SyncRequest(BaseModel):
    project_id: str
    repo: str  # "owner/name"
    token: str | None = None  # optional override of the server-configured GITHUB_TOKEN


@router.post("/sync")
def sync(req: SyncRequest, db: Session = Depends(get_db)):
    try:
        result = sync_repository(db, project_id=req.project_id, repo_full_name=req.repo, token=req.token)
    except GitHubSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
