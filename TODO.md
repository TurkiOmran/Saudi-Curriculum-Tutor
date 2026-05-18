# TODO

Out-of-scope items that surfaced while building other features. Each
entry names the symptom, root cause, and a couple of fix options so
whoever picks it up doesn't have to re-derive the analysis.

---

## UI status label freezes during retrieve (first query)

**Symptom.** On the first query after server boot, the status bar in the
Chainlit answer stays on "⏳ Detecting intent…" for ~15s, then jumps
straight to "⏳ Composing answer…". The intent node isn't slow — the
retrieve node is, and its blocking work prevents the next
`on_chain_start` event from reaching the websocket.

**Root cause.** `src/graph/nodes/retrieve.py` does two synchronous heavy
ops in the same thread as the LangGraph runner: (a) lazy-loads
`jina-embeddings-v4` + `jina-reranker-v2-base-multilingual` from the HF
cache (~7s cold), (b) encodes the query on CPU (~7s). While that's
running the asyncio loop can't flush the `retrieve` node's
`on_chain_start`, so `app.py`'s status updater stays on the previous
label.

**Fix options (pick one when picking this up):**
1. **Pre-warm at startup.** Call the embedder + reranker once from
   `@cl.on_app_startup` so the model load happens before any user
   request. Removes the cold-load penalty; encode-time penalty remains.
2. **Run retrieve in a thread.** Wrap the blocking Jina calls in
   `asyncio.to_thread(...)` so the event loop stays free and
   `on_chain_start` for retrieve flushes to the UI immediately.
3. **Heartbeat the status.** In `app.py`, instead of updating only on
   `on_chain_start`, also update on a 500ms timer using the
   *expected-next-node* heuristic. Hides the symptom without fixing the
   underlying block.

**Scope note.** Pre-exists the `persistent-chat-sessions` branch.
Touches `src/graph/nodes/retrieve.py` and/or `src/ui/app.py`. No
data-layer implications.

---

## Intent classifier mis-labels "quiz me on …" as `qa`

**Symptom.** Asked "quiz me on earlier question in arabic" against a
resumed Grade 8 social-studies thread. Rewrite correctly expanded
"earlier question" into the prior turn's topic, but the intent node
classified the result as `qa` (Q&A) instead of `quiz`. Downstream
retrieval pulled weakly-scoring chunks (top rerank 0.38) and
self-check refused.

**Why it matters.** The `quiz` intent has different prompt scaffolding
and looser self-check criteria than `qa` — a quiz request that lands
on the `qa` branch will refuse on borderline retrieval scores where
the quiz branch would generate. Users typing "quiz me…" will hit
spurious refusals.

**Likely fix surface.** `src/graph/nodes/intent.py` + `prompts/intent.j2`.
The Jinja prompt may not give the classifier enough quiz examples, or
its few-shot block may be biased toward `qa`. Worth checking the
prompt with a few "quiz me on X" cases in `scripts/smoke_run.py`.

**Evidence.** `logs/queries-2026-05-18.jsonl`, last entry —
`query="quiz me on earlier question in arabic"`,
`standalone_question="quiz me on الخصائص الطبية للعالم العربي والإسلامي"`,
`intent="qa"`, `self_check_passed=false`, `refused=true`.

**Scope note.** Pre-exists the `persistent-chat-sessions` branch.
Caught while testing AC2 of that feature (history rehydration on
resume). No data-layer implications.
