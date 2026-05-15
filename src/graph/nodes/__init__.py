"""Graph nodes — one file per node.

Outer-graph nodes:  rewrite, decompose, merge (merge lives in outer.py)
Inner-graph nodes:  intent, retrieve, self_check, generate, refuse, citations

Each node is an async function `(state) -> dict` that returns the partial
state update LangGraph should merge. Nodes do NOT import Chainlit (per L21);
the UI layer subscribes to events via `astream_events` instead.
"""
