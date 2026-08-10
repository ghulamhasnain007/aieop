import { useState } from "react";
import { useAppState } from "../context/AppStateContext.jsx";

export default function KnowledgeBase() {
  const { projectId } = useAppState();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState("");

  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [querying, setQuerying] = useState(false);

  async function ingest() {
    if (!title.trim() || !content.trim()) return;
    setIngesting(true);
    setIngestMsg("");
    try {
      await fetch("/api/knowledge/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, content, project_id: projectId }),
      });
      setIngestMsg(`Ingested "${title}"`);
      setTitle("");
      setContent("");
    } finally {
      setIngesting(false);
    }
  }

  async function query() {
    if (!question.trim()) return;
    setQuerying(true);
    setResult(null);
    try {
      const resp = await fetch("/api/knowledge/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, project_id: projectId }),
      });
      setResult(await resp.json());
    } finally {
      setQuerying(false);
    }
  }

  return (
    <div className="panel-body">
      <div className="section-title">Add a document</div>
      <div className="kb-form">
        <input
          placeholder="Title (e.g. Payment Service Runbook)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <textarea
          placeholder="Paste the document content here…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <div>
          <button className="send-btn" onClick={ingest} disabled={ingesting || !title.trim() || !content.trim()}>
            {ingesting ? "Ingesting…" : "Ingest"}
          </button>
          {ingestMsg && <span style={{ marginLeft: 10, fontSize: 11.5, color: "var(--accent)" }}>{ingestMsg}</span>}
        </div>
      </div>

      <div className="section-title">Ask the knowledge base</div>
      <div className="kb-form">
        <input
          placeholder="e.g. what should I do about payment timeouts?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && query()}
        />
        <div>
          <button className="send-btn" onClick={query} disabled={querying || !question.trim()}>
            {querying ? "Searching…" : "Ask"}
          </button>
        </div>
      </div>

      {result && (
        <>
          <div className="kb-answer">{result.answer}</div>
          {result.sources?.length > 0 && (
            <>
              <div className="section-title">Sources</div>
              {result.sources.map((s) => (
                <div className="kb-source" key={s.chunk_id}>
                  <span className="title">{s.document_title} — {s.excerpt}</span>
                  <span className="score">score {s.score}</span>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
