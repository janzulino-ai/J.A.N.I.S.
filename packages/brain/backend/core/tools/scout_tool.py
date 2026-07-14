"""Tool ReAct scout — discovery, test, verify, promote."""
from __future__ import annotations

from backend.core.tools.registry import register


@register("scout")
async def scout_tool(args: dict) -> str:
    action = (args.get("action") or "status").lower().strip()
    candidate_id = (args.get("candidate_id") or args.get("id") or "").strip()
    topic = (args.get("topic") or "").strip()
    sources = args.get("sources") or ["watchlist", "github"]

    if action == "discover":
        from backend.core.tech_scout.discover import discover_all
        from backend.core.tech_scout.classifier import classify_candidate
        result = await discover_all(topic=topic, sources=sources if isinstance(sources, list) else [sources])
        for c in result.get("candidates") or []:
            classify_candidate(c)
        return f"Discovery: {result.get('count', 0)} candidati. IDs: " + ", ".join(
            c.get("id", "?") for c in (result.get("candidates") or [])[:8]
        )

    if action == "test":
        if not candidate_id:
            return "candidate_id obbligatorio per scout test"
        from backend.core.tech_scout.sandbox import run_sandbox_test
        r = await run_sandbox_test(candidate_id)
        return f"Sandbox {candidate_id}: ok={r.get('ok')} steps={len(r.get('steps') or [])}"

    if action == "verify":
        if not candidate_id:
            return "candidate_id obbligatorio per scout verify"
        from backend.core.tech_scout.verifier import verify_candidate
        r = await verify_candidate(candidate_id)
        return f"Verify {candidate_id}: verdict={r.get('verdict', r.get('error'))}"

    if action == "promote":
        if not candidate_id:
            return "candidate_id obbligatorio per scout promote"
        from backend.core.tech_scout.promote import promote_candidate
        r = await promote_candidate(candidate_id)
        if not r.get("ok"):
            return f"Promote fallito: {r.get('error')}"
        return f"Promosso {r.get('candidate')}: research={r.get('research_id')} proposals={r.get('proposals_created')}"

    if action == "status":
        from backend.core.tech_scout.discover import list_candidates
        items = list_candidates()
        lines = [f"Tech Scout: {len(items)} candidati"]
        for c in items[:8]:
            dep = c.get("deployment") or "?"
            lines.append(f"- [{c.get('status')}] {c.get('name')} ({dep}) id={c.get('id')}")
        return "\n".join(lines)

    return f"Azione scout sconosciuta: {action}. Usa: discover|test|verify|promote|status"
