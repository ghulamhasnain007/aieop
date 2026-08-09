from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.knowledge.rag_service import RagService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class DocumentIngest(BaseModel):
    title: str
    content: str
    project_id: str | None = None
    source: str | None = None


class KnowledgeQuery(BaseModel):
    question: str
    project_id: str | None = None
    top_k: int = 5


@router.post("/documents")
def ingest_document(payload: DocumentIngest, db: Session = Depends(get_db)):
    service = RagService(db)
    document = service.ingest_document(
        title=payload.title, content=payload.content,
        project_id=payload.project_id, source=payload.source,
    )
    return {"id": document.id, "title": document.title}


@router.post("/query")
def query_knowledge(payload: KnowledgeQuery, db: Session = Depends(get_db)):
    service = RagService(db)
    result = service.query(payload.question, project_id=payload.project_id, top_k=payload.top_k)
    return {
        "question": result.question,
        "answer": result.answer,
        "grounded": result.grounded,
        "sources": [
            {
                "document_id": s.document_id,
                "document_title": s.document_title,
                "chunk_id": s.chunk_id,
                "excerpt": s.content[:200],
                "score": s.score,
            }
            for s in result.sources
        ],
    }
