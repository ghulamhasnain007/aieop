"""
RAG pipeline (FR-015, FR-038 Knowledge Base).

Pipeline exactly as specified:

    Question -> Embedding -> Vector Search -> Relevant Documents -> LLM -> Evidence-backed Answer

The retrieval half (chunking, embedding, vector search) is fully
implemented and real. The generation half is intentionally NOT an LLM
call yet - `synthesize_answer()` is a clearly-marked extractive stand-in
(concatenates the top-matching chunks) so the whole pipeline is runnable
and testable without an API key. Swap that one function for an LLM call
(prompt = question + retrieved chunks) when you wire up Gemini/LangChain;
nothing else in this module needs to change.

Chunking is intentionally simple (paragraph-based, capped length) - good
enough for architecture docs/runbooks at FYP scale. Swap for a
recursive/token-aware splitter if documents get large.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge.embeddings import embed_text, cosine_similarity
from app.models.entities import Document, DocumentChunk

MAX_CHUNK_CHARS = 800


def _chunk_text(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) + 1 <= MAX_CHUNK_CHARS:
            buffer = f"{buffer}\n\n{para}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = para
    if buffer:
        chunks.append(buffer)
    return chunks or ([text[:MAX_CHUNK_CHARS]] if text.strip() else [])


@dataclass
class RetrievedChunk:
    document_id: str
    document_title: str
    chunk_id: str
    content: str
    score: float


@dataclass
class RagResult:
    question: str
    answer: str
    sources: list[RetrievedChunk]
    grounded: bool  # False when nothing relevant enough was found (FR-032)


class RagService:
    MIN_RELEVANCE_SCORE = 0.05  # below this, treat as "no relevant document"

    def __init__(self, db: Session):
        self.db = db

    # -- ingestion ------------------------------------------------------------

    def ingest_document(self, title: str, content: str, project_id: str | None = None,
                         source: str | None = None) -> Document:
        document = Document(title=title, content=content, project_id=project_id, source=source)
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        for i, chunk_text in enumerate(_chunk_text(content)):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=str(i),
                content=chunk_text,
                embedding=embed_text(chunk_text),
            )
            self.db.add(chunk)
        self.db.commit()
        return document

    # -- retrieval + answer -----------------------------------------------------

    def query(self, question: str, project_id: str | None = None, top_k: int = 5) -> RagResult:
        query_vector = embed_text(question)

        chunk_query = self.db.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
        if project_id:
            chunk_query = chunk_query.filter(Document.project_id == project_id)

        scored: list[RetrievedChunk] = []
        for chunk, document in chunk_query.all():
            score = cosine_similarity(query_vector, chunk.embedding or [])
            scored.append(RetrievedChunk(
                document_id=document.id, document_title=document.title,
                chunk_id=chunk.id, content=chunk.content, score=round(score, 4),
            ))

        scored.sort(key=lambda c: c.score, reverse=True)
        top = [c for c in scored[:top_k] if c.score >= self.MIN_RELEVANCE_SCORE]

        if not top:
            return RagResult(
                question=question,
                answer="I could not find relevant documentation to answer this. "
                       "Try rephrasing, or check that the relevant document has been ingested.",
                sources=[],
                grounded=False,
            )

        answer = self.synthesize_answer(question, top)
        return RagResult(question=question, answer=answer, sources=top, grounded=True)

    def synthesize_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        """
        EXTRACTIVE STAND-IN for the LLM generation step. Returns the
        single most relevant chunk verbatim with an explicit pointer to
        its source, rather than a fabricated synthesis - this keeps the
        pipeline honest (FR-032) while the real LLM call isn't wired up.
        Replace this method's body with an LLM call once you have an API
        key; keep the RagResult contract the same.
        """
        best = chunks[0]
        excerpt = best.content if len(best.content) <= 400 else best.content[:400].rsplit(" ", 1)[0] + "…"
        return f"From '{best.document_title}': {excerpt}"
