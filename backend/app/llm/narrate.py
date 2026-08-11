"""
Root-cause narration.

Turns a RootCauseResult's structured evidence into a fluent explanation.
The prompt is deliberately restrictive: the LLM is given the exact facts,
hypotheses, confidence, and recommendation the Incident Agent already
computed, and is told not to introduce anything beyond them. This keeps
the deterministic correlation logic (app.agents.incident_agent) as the
sole source of truth for WHAT happened; the LLM only controls HOW it's
phrased.

Returns None (not an exception) when the LLM isn't configured or fails -
callers use that as the signal to fall back to the deterministic template
string, exactly like app.knowledge.rag_service does.
"""
from __future__ import annotations

from app.llm.client import generate, is_configured, LLMError


def narrate_root_cause(result) -> str | None:
    """`result` is an app.agents.incident_agent.RootCauseResult."""
    if not is_configured() or result.insufficient_evidence:
        return None

    facts = [e.detail for e in result.evidence if e.type == "fact"]
    hypotheses = [e.detail for e in result.evidence if e.type == "hypothesis"]

    system = (
        "You are an SRE assistant explaining an incident root-cause analysis to an engineer. "
        "Use ONLY the facts, hypotheses, confidence, and recommendation given below - do not "
        "introduce any additional causes, systems, or evidence not listed. Clearly distinguish "
        "confirmed facts from correlational hypotheses in your phrasing. Keep it to 3-4 sentences "
        "and end by stating the given recommendation."
    )
    user = (
        f"Incident: {result.incident_title}\n"
        f"Confidence: {result.confidence:.0%}\n"
        f"Likely cause: {result.likely_cause}\n"
        f"Facts:\n" + "\n".join(f"- {f}" for f in facts) + "\n\n"
        f"Hypotheses (correlational, not confirmed):\n" + "\n".join(f"- {h}" for h in hypotheses) + "\n\n"
        f"Recommendation: {result.recommendation}"
    )

    try:
        return generate(system, user, max_tokens=300)
    except LLMError:
        return None
