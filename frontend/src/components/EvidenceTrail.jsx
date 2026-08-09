export default function EvidenceTrail({ evidence }) {
  if (!evidence || evidence.length === 0) return null;

  return (
    <div className="evidence-trail">
      <div className="evidence-trail-label">Evidence trail</div>
      {evidence.map((e, i) => (
        <div className={`evidence-node ${e.type || "fact"}`} key={i}>
          <div className="evidence-type">{e.type || e.source}</div>
          <div className="evidence-detail">{e.detail || `${e.source} · ${e.id}`}</div>
          {e.id && <div className="evidence-id">{e.id}</div>}
        </div>
      ))}
    </div>
  );
}
