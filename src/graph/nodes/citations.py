"""Citations node — parse `[n]` markers from the generated answer.

Per L5, ALLaM writes `[n]` markers inline during generation. This node
only renders them: regex-parse, map each number to its chunk, attach as
`state.citations`. Per L14, no retry on malformed markers — log and
move on.

Refusal answers have no citations to resolve, so they short-circuit.
"""

from __future__ import annotations

import re

from src.graph.state import Citation, TaskState

_CITATION_RE = re.compile(r"\[(\d+)\]")


async def citations_node(state: TaskState) -> dict:
    if state.get("refused"):
        return {"citations": []}

    answer = state.get("answer", "")
    chunks = state.get("chunks") or []

    seen: set[int] = set()
    citations: list[Citation] = []
    malformed: list[int] = []

    for match in _CITATION_RE.finditer(answer):
        n = int(match.group(1))
        if n in seen:
            continue
        seen.add(n)
        idx = n - 1  # `[1]` → chunks[0]
        if 0 <= idx < len(chunks):
            citations.append(Citation(n=n, chunk=chunks[idx]))
        else:
            malformed.append(n)

    debug = dict(state.get("debug") or {})
    if malformed:
        debug["citations_malformed"] = malformed
    debug["citations_count"] = len(citations)

    return {"citations": citations, "debug": debug}
