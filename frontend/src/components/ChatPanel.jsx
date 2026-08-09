import { useState, useRef, useEffect } from "react";
import EvidenceTrail from "./EvidenceTrail.jsx";

const SUGGESTIONS = [
  "Will we finish sprint 14?",
  "Why did the payment service fail?",
  "What changed in the auth repository?",
];

export default function ChatPanel({ projectId, role }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text) {
    const content = (text ?? input).trim();
    if (!content || loading) return;

    setMessages((m) => [...m, { role: "user", content }]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-User-Role": role },
        body: JSON.stringify({ message: content, project_id: projectId }),
      });
      const data = await resp.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer,
          intent: data.intent,
          domain: data.domain,
          confidence: data.confidence,
          riskLevel: data.risk_level,
          agentUsed: data.agent_used,
          evidence: data.evidence,
        },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Could not reach the backend. Is the API running on :8000?" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-view">
      <div className="chat-log" ref={logRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="glyph">// NATURAL LANGUAGE INTERFACE</div>
            <div>
              Ask about sprint risk, incident root cause, or recent code changes.
              Every answer that draws on data shows its evidence trail.
            </div>
            <div className="suggestion-row">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion-chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div className={`msg-row ${m.role}`} key={i}>
            <div className="bubble">{m.content}</div>
            {m.role === "assistant" && m.intent && (
              <div className="meta-row">
                <span className="pill">{m.intent}</span>
                <span className="pill">{m.domain}</span>
                {m.agentUsed && <span className="pill">{m.agentUsed}</span>}
                <span className={`pill risk-${m.riskLevel}`}>risk: {m.riskLevel}</span>
                <span>conf {(m.confidence * 100).toFixed(0)}%</span>
              </div>
            )}
            {m.role === "assistant" && <EvidenceTrail evidence={m.evidence} />}
          </div>
        ))}

        {loading && <div className="msg-row assistant"><div className="bubble">Thinking…</div></div>}
      </div>

      <div className="composer">
        <div className="composer-inner">
          <input
            placeholder="Ask the platform anything…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="send-btn" onClick={() => send()} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
