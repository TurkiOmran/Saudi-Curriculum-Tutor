"""Aleem — Chainlit UI driving the workflow-sandbox tool-calling agent.

Wiring per WORKFLOW_SANDBOX.md §3 / §7:

  - Tool calls become ephemeral status updates (`Searching: "<query>"`).
  - The agent's chat-model stream pipes tokens into the live answer
    message (same `astream_events` plumbing the old per-node UI used —
    only the node-name filter changes).
  - After the stream closes, `finalize_agent_run()` runs citation parse
    + topical verifier + JSONL logging, and citation cards are attached
    to the answer.

Graph internals stay pure — this handler is the only place LangGraph
events meet Chainlit primitives.

Run from `src/ui/`:

    cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# When this file is run by Chainlit from `src/ui/`, the repo root is two
# levels up. Keep `from src...` imports resolvable without requiring
# PYTHONPATH (the explicit PYTHONPATH=../.. in the run command remains
# the documented convention; this is a belt-and-suspenders fallback).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import chainlit as cl  # noqa: E402
import chainlit.data as cl_data  # noqa: E402
from chainlit.input_widget import Select  # noqa: E402
from chainlit.types import ThreadDict  # noqa: E402
from langchain_core.messages import BaseMessage, HumanMessage  # noqa: E402
from langgraph.errors import GraphRecursionError  # noqa: E402

from src.config import settings  # noqa: E402
from src.graph.agent import (  # noqa: E402
    build_agent,
    finalize_agent_run,
    history_to_messages,
    recursion_limit,
)
from src.graph.logging import log_query  # noqa: E402
from src.graph.state import initial_agent_state  # noqa: E402
from src.graph.tools import set_request_context  # noqa: E402
from src.ui.persistence import (  # noqa: E402
    make_data_layer,
    parse_thread_metadata,
    rebuild_history,
)

# Subject options. Each entry is (internal_key, bilingual_label).
SUBJECTS: list[tuple[str, str]] = [
    ("arabic",          "العربية  ·  Arabic"),
    ("islamic_studies", "الدراسات الإسلامية  ·  Islamic Studies"),
    ("social_studies",  "الاجتماعيات  ·  Social Studies"),
    ("english",         "اللغة الإنجليزية  ·  English"),
    ("math",            "الرياضيات  ·  Math"),
]
SUBJECT_LABELS = [label for _, label in SUBJECTS]


# The prebuilt agent's internal nodes are named "agent" (the LLM call)
# and "tools" (the tool execution). We stream tokens from "agent" and
# surface tool-call invocations from "tools".
AGENT_LLM_NODE = "agent"


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


def _subject_index(key: str) -> int:
    for i, (k, _) in enumerate(SUBJECTS):
        if k == key:
            return i
    return 0


async def _persist_thread_metadata(**fields: object) -> None:
    """Merge fields into the current thread's metadata.

    SQLAlchemyDataLayer.update_thread merges with the existing row (it
    SELECTs first), so passing one field at a time is safe — it won't
    blow away the others. Wrapped in try/except so a storage hiccup
    never blocks the live chat.
    """
    layer = cl_data.get_data_layer()
    if layer is None:
        return
    thread_id = cl.context.session.thread_id
    if not thread_id:
        return
    try:
        await layer.update_thread(thread_id=thread_id, metadata=dict(fields))
    except Exception:  # noqa: BLE001 — never let bookkeeping break the UI
        pass


@cl.data_layer
def _data_layer():
    return make_data_layer()


@cl.header_auth_callback
def _header_auth(headers) -> cl.User | None:
    # Local-only build: a single hardcoded user so the data layer has
    # someone to scope threads to. Replace with real auth at deploy time.
    return cl.User(identifier="local", metadata={"role": "local"})


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
            name="Grade 8",
            markdown_description=(
                "**الصف الثاني المتوسط  ·  Grade 8**\n\n"
                "Middle school stage. Aleem will answer only from your Grade 8 "
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

    # Tag the thread so on_chat_resume can restore grade/subject without
    # walking the messages. Grade comes from the chat profile, subject
    # from the settings dropdown — neither is recoverable from the
    # transcript alone.
    await _persist_thread_metadata(grade=grade, subject=initial_subject)

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
        key = _label_to_key(label)
        cl.user_session.set("subject", key)
        await _persist_thread_metadata(subject=key)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Rehydrate cl.user_session from a persisted thread.

    Chainlit replays the transcript itself; this hook only re-fills the
    three values the pipeline reads from cl.user_session: grade,
    subject, and history. Grade & subject come from thread metadata
    (we tagged them at on_chat_start); history is rebuilt from the
    persisted user/assistant messages so the agent sees prior turns.
    """
    metadata = parse_thread_metadata(thread.get("metadata"))

    # Grade: prefer metadata; fall back to the chat profile name.
    grade = metadata.get("grade")
    if grade is None:
        profile = cl.user_session.get("chat_profile")
        try:
            grade = int(str(profile).split()[1])
        except (ValueError, IndexError, AttributeError):
            grade = None
    if grade is not None:
        cl.user_session.set("grade", int(grade))

    # Subject: prefer metadata; fall back to first SUBJECTS entry.
    subject = metadata.get("subject") or SUBJECTS[0][0]
    cl.user_session.set("subject", subject)

    # History: rebuild from persisted messages, capped to the rewrite
    # node's window so we don't blow the prompt budget.
    history = rebuild_history(thread, settings.memory.max_turns)
    cl.user_session.set("history", history)

    # Re-send the settings widget so the subject dropdown reflects the
    # persisted choice.
    await cl.ChatSettings(
        [
            Select(
                id="subject",
                label="Subject  ·  المادة",
                values=SUBJECT_LABELS,
                initial_index=_subject_index(subject),
            ),
        ]
    ).send()


def _citation_elements(final_state: dict) -> list[cl.Text]:
    """Build expandable source cards from the parsed citations."""
    elements: list[cl.Text] = []
    seen: set[int] = set()
    for cit in (final_state.get("citations") or []):
        if cit.n in seen:
            continue
        seen.add(cit.n)
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

    state = initial_agent_state(
        grade=grade,
        subject=subject,
        user_query=message.content,
        history=history,
    )

    # Ephemeral status — updates with each tool call, removed once the
    # answer is ready so it doesn't persist in the transcript.
    status_msg = cl.Message(content="⏳ Thinking…", author="Aleem")
    await status_msg.send()

    # Answer message — tokens stream into this from the agent's LLM node.
    answer_msg = cl.Message(content="")
    await answer_msg.send()

    set_request_context(grade, subject)
    agent = build_agent(grade, subject)

    messages: list[BaseMessage] = [
        *history_to_messages(history),
        HumanMessage(content=message.content),
    ]

    ceiling_hit = False
    final_messages: list[BaseMessage] = list(messages)
    t0 = time.perf_counter()
    agent_loop_ms = 0

    try:
        async for ev in agent.astream_events(
            {"messages": messages},
            version="v2",
            config={"recursion_limit": recursion_limit()},
        ):
            et = ev["event"]
            name = ev["name"]
            md = ev.get("metadata") or {}

            # Tool-call surfacing — show the verbatim query.
            if et == "on_tool_start" and name == "retrieve":
                inputs = ev["data"].get("input") or {}
                query = inputs.get("query", "")
                status_msg.content = f"🔎 Searching: “{query}”"
                await status_msg.update()

            # Token streaming from the agent LLM node.
            if (
                et == "on_chat_model_stream"
                and md.get("langgraph_node") == AGENT_LLM_NODE
            ):
                chunk = ev["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    await answer_msg.stream_token(content)
                elif isinstance(content, list):
                    for part in content:
                        if (
                            isinstance(part, dict)
                            and isinstance(part.get("text"), str)
                            and part["text"]
                        ):
                            await answer_msg.stream_token(part["text"])

            # Capture the final message list from the root chain's end.
            if et == "on_chain_end" and name == "LangGraph":
                output = ev["data"].get("output")
                if isinstance(output, dict) and "messages" in output:
                    final_messages = list(output["messages"])

    except GraphRecursionError:
        ceiling_hit = True
    except Exception as exc:  # noqa: BLE001 — surface any failure visibly per L20
        try:
            await status_msg.remove()
        except Exception:  # noqa: BLE001
            pass
        await cl.Message(
            content=f"⚠️ **Pipeline error**\n\n```\n{exc}\n```"
        ).send()
        return
    finally:
        agent_loop_ms = int((time.perf_counter() - t0) * 1000)

    # Run post-hoc verifier + citation parse using the same finalize
    # helper that run_agent() uses.
    update = await finalize_agent_run(
        state,
        final_messages=final_messages,
        ceiling_hit=ceiling_hit,
    )

    # Merge update + per-phase latency into the state for L18 logging.
    debug = dict(state.get("debug") or {})
    debug.update(update.get("debug") or {})
    latency_ms = dict(debug.get("latency_ms") or {})
    latency_ms["agent_loop"] = agent_loop_ms
    latency_ms["total"] = int((time.perf_counter() - t0) * 1000)
    debug["latency_ms"] = latency_ms

    final_state: dict = {**state, **update, "debug": debug}

    try:
        log_query(final_state)
    except Exception:  # noqa: BLE001 — logging must never break the UI
        pass

    # Drop the ephemeral status line.
    try:
        await status_msg.remove()
    except Exception:  # noqa: BLE001
        pass

    final_answer = final_state.get("final_answer", "") or ""
    # Replace whatever the stream produced with the canonical final answer
    # (the verifier may have swapped it for a refusal; the streaming
    # tokens won't reflect that).
    answer_msg.content = final_answer
    answer_msg.elements = _citation_elements(final_state)
    await answer_msg.update()

    # Append this turn to history. Cap at memory.max_turns * 2 (user + assistant).
    history.append({"role": "user", "content": message.content})
    history.append({"role": "assistant", "content": final_answer})
    history = history[-(settings.memory.max_turns * 2):]
    cl.user_session.set("history", history)
