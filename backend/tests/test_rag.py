from app.knowledge.rag_service import RagService
from app.knowledge.embeddings import embed_text, cosine_similarity


def test_embedding_is_deterministic_and_normalized():
    v1 = embed_text("payment service timeout error")
    v2 = embed_text("payment service timeout error")
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_similar_text_scores_higher_than_unrelated_text():
    query = embed_text("why is the payment service timing out")
    related = embed_text("The payment service has been experiencing timeout errors recently")
    unrelated = embed_text("The onboarding wizard now supports dark mode")

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_ingest_and_query_retrieves_relevant_chunk(db_session):
    service = RagService(db_session)
    service.ingest_document(
        title="Payment Service Runbook",
        content="The payment service occasionally times out under high load.\n\n"
                "Restarting the connection pool usually resolves transient timeouts.\n\n"
                "The onboarding wizard is unrelated to payments and lives in a separate module.",
    )

    result = service.query("payment service timeout")

    assert result.grounded is True
    assert "Payment Service Runbook" in result.answer
    assert len(result.sources) >= 1


def test_query_with_no_ingested_documents_does_not_fabricate(db_session):
    service = RagService(db_session)
    result = service.query("what is our deployment rollback policy")

    assert result.grounded is False
    assert "could not find" in result.answer.lower()
    assert result.sources == []


def test_project_scoped_query_ignores_other_projects_documents(db_session):
    service = RagService(db_session)
    service.ingest_document(title="Project A Doc", content="Project A uses blue-green deployments.",
                             project_id="proj-a")
    service.ingest_document(title="Project B Doc", content="Project B uses canary deployments.",
                             project_id="proj-b")

    result = service.query("deployment strategy", project_id="proj-a")

    assert result.grounded is True
    assert all(s.document_title == "Project A Doc" for s in result.sources)
