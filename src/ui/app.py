"""Aleem — Chainlit UI driving the LangGraph outer pipeline.

Wiring per L21: `@cl.on_message` invokes `outer_graph.astream_events(...)`
and maps LangGraph events to Chainlit UI primitives — `cl.Step` cards per
node start/end (L11 "showing work"), token-by-token streaming for the
generate node, and `cl.Text` citation cards attached to the final answer.

Graph nodes stay pure (no `cl.*` calls inside them) — this handler is the
only place the two worlds meet.

Run from `src/ui/`:

    cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# When this file is run by Chainlit from `src/ui/`, the repo root is two
# levels up. Keep `from src...` imports resolvable without requiring
# PYTHONPATH (the explicit PYTHONPATH=../.. in the run command remains
# the documented convention; this is a belt-and-suspenders fallback).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import chainlit as cl  # noqa: E402
from chainlit.input_widget import Select  # noqa: E402

from src.config import settings  # noqa: E402
from src.graph.outer import outer_graph  # noqa: E402
from src.graph.state import initial_outer_state  # noqa: E402

# Subject options. Each entry is (internal_key, bilingual_label).
SUBJECTS: list[tuple[str, str]] = [
    ("arabic",          "العربية  ·  Arabic"),
    ("islamic_studies", "الدراسات الإسلامية  ·  Islamic Studies"),
    ("social_studies",  "الاجتماعيات  ·  Social Studies"),
    ("english",         "اللغة الإنجليزية  ·  English"),
    ("math",            "الرياضيات  ·  Math"),
]
SUBJECT_LABELS = [label for _, label in SUBJECTS]


# Friendly per-node labels for cl.Step (L11). Keys are the LangGraph node
# names from outer.py / inner.py. Anything not in this map is treated as
# internal plumbing and won't get its own step card.
NODE_LABELS: dict[str, str] = {
    "rewrite": "Understanding your question…",
    "decompose": "Splitting compound requests…",
    "intent": "Detecting intent…",
    "retrieve": "Finding relevant pages…",
    "self_check": "Checking the textbook…",
    "generate": "Composing answer…",
    "refuse": "Preparing related topics…",
    "citations": "Resolving citations…",
    "chat": "Replying…",   # L22 — non-curriculum conversational replies
    "merge": "Combining answers…",
}

# Nodes whose token streams should pipe into the live Chainlit message
# (L11). Both `generate` (grounded answer) and `chat` (L22 conversational
# reply) emit user-facing text token-by-token.
STREAMING_NODES = {"generate", "chat"}


def _label_to_key(label: str) -> str:
    for key, lbl in SUBJECTS:
        if lbl == label:
            return key
    return label


def _key_to_label(key: str) -> str:
    for k, lbl in SUBJECTS:
        if k == key:
            return lbl
    return key


@cl.set_chat_profiles
async def chat_profiles() -> list[cl.ChatProfile]:
    return [
        cl.ChatProfile(
            name="Grade 4",
            markdown_description=(
                "**الصف الرابع  ·  Grade 4**\n\n"
                "Elementary stage. Aleem will answer only from your Grade 4 "
                "Ministry of Education textbooks."
            ),
        ),
        cl.ChatProfile(
            name="Grade 7",
            markdown_description=(
                "**الصف السابع  ·  Grade 7**\n\n"
                "Middle school stage. Aleem will answer only from your Grade 7 "
                "Ministry of Education textbooks."
            ),
        ),
        cl.ChatProfile(
            name="Grade 10",
            markdown_description=(
                "**الصف العاشر  ·  Grade 10**\n\n"
                "High school stage. Aleem will answer only from your Grade 10 "
                "Ministry of Education textbooks."
            ),
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    profile = cl.user_session.get("chat_profile")  # e.g. "Grade 7"
    grade = int(str(profile).split()[1])
    cl.user_session.set("grade", grade)
    cl.user_session.set("history", [])

    chat_settings = await cl.ChatSettings(
        [
            Select(
                id="subject",
                label="Subject  ·  المادة",
                values=SUBJECT_LABELS,
                initial_index=0,
            ),
        ]
    ).send()

    initial_subject = _label_to_key(chat_settings["subject"])
    cl.user_session.set("subject", initial_subject)

    await cl.Message(
        content=(
            f"**أهلاً بك في عليم  ·  Welcome to Aleem**\n\n"
            f"- **Grade  ·  الصف:** {grade}\n"
            f"- **Subject  ·  المادة:** {_key_to_label(initial_subject)}\n\n"
            f"To change the subject, open the settings panel (⚙) at the top "
            f"of the chat. Then ask your question — every answer will come "
            f"from your Grade {grade} textbook only."
        ),
    ).send()


@cl.on_settings_update
async def on_settings_update(chat_settings: dict) -> None:
    label = chat_settings.get("subject")
    if label:
        cl.user_session.set("subject", _label_to_key(label))


def _citation_elements(final_state: dict) -> list[cl.Text]:
    """Build expandable source cards for citations across all tasks."""
    elements: list[cl.Text] = []
    seen_ids: set[tuple[int, int]] = set()  # (task_idx, citation_n)
    tasks = final_state.get("tasks") or []
    for t_idx, task in enumerate(tasks):
        for cit in (task.get("citations") or []):
            key = (t_idx, cit.n)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            chunk = cit.chunk
            elements.append(
                cl.Text(
                    name=f"[{cit.n}] {chunk.lesson_title} · p.{chunk.page}",
                    content=chunk.text,
                    display="side",
                )
            )
    return elements


@cl.on_message
async def on_message(message: cl.Message) -> None:
    grade = cl.user_session.get("grade")
    subject = cl.user_session.get("subject")
    history = cl.user_session.get("history") or []

    if grade is None or subject is None:
        await cl.Message(
            content=(
                "Please pick a subject from the settings panel (⚙) before "
                "asking a question."
            ),
        ).send()
        return

    initial = initial_outer_state(
        grade=grade,
        subject=subject,
        user_query=message.content,
        history=history,
    )

    # The placeholder message we'll stream tokens into. Sent now so it
    # appears immediately under the steps.
    answer_msg = cl.Message(content="")
    await answer_msg.send()

    steps: dict[str, cl.Step] = {}
    root_run_id: str | None = None
    final_state: dict | None = None

    try:
        async for ev in outer_graph.astream_events(initial, version="v2"):
            et = ev["event"]
            name = ev["name"]
            run_id = ev["run_id"]
            md = ev.get("metadata") or {}

            # First event we see is the root chain's start.
            if root_run_id is None and et == "on_chain_start":
                root_run_id = run_id

            # Capture final state when the root chain ends.
            if et == "on_chain_end" and run_id == root_run_id:
                output = ev["data"].get("output")
                if isinstance(output, dict):
                    final_state = output

            # Per-node step cards (L11).
            label = NODE_LABELS.get(name)
            if label is not None:
                if et == "on_chain_start" and run_id not in steps:
                    step = cl.Step(name=label, type="tool")
                    await step.send()
                    steps[run_id] = step
                elif et == "on_chain_end" and run_id in steps:
                    step = steps.pop(run_id)
                    await step.update()

            # Token streaming for the generate / chat nodes (L21, L22).
            if (
                et == "on_chat_model_stream"
                and md.get("langgraph_node") in STREAMING_NODES
            ):
                chunk = ev["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    await answer_msg.stream_token(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            await answer_msg.stream_token(part["text"])

    except Exception as exc:  # noqa: BLE001 — surface any failure visibly per L20
        for step in steps.values():
            await step.update()
        await cl.Message(
            content=f"⚠️ **Pipeline error**\n\n```\n{exc}\n```"
        ).send()
        return

    if final_state is None:
        await cl.Message(content="⚠️ Pipeline produced no state.").send()
        return

    final_answer = final_state.get("final_answer", "") or ""

    # Always replace whatever the streaming produced with the canonical
    # merged answer. Streaming concatenates tokens from each task's generate
    # node into one cl.Message, which loses the "### Part N" headers and
    # the "---" separator that merge_node assembles for multi-task queries.
    # For single-task happy paths the two values are identical (no visual
    # jump); for refuse / chat / multi-task paths this restores structure.
    answer_msg.content = final_answer

    answer_msg.elements = _citation_elements(final_state)
    await answer_msg.update()

    # Append this turn to history for L7 rewrite (Phase E). Cap at the
    # configured max_turns * 2 (user+assistant per turn).
    history.append({"role": "user", "content": message.content})
    history.append({"role": "assistant", "content": final_answer})
    history = history[-(settings.memory.max_turns * 2):]
    cl.user_session.set("history", history)
