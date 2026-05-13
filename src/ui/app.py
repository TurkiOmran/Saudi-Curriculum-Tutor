"""Aleem — Chainlit UI shell.

This is the *shell*: grade picker (ChatProfile), subject picker (settings
panel), session state, and a placeholder message handler. There is no
retriever, embedder, or generator wired in yet — `@cl.on_message` only
confirms that the user's grade + subject were captured correctly.

Run from the repo root:

    chainlit run src/ui/app.py

The Chroma collections must already exist (run `python -m src.retrieval.init_chroma`
first). This file does not import the retrieval layer — that wiring comes
in a future task per `BUILD_SPEC.md §10`.
"""

from __future__ import annotations

import chainlit as cl
from chainlit.input_widget import Select

# Subject options. Each entry is (internal_key, bilingual_label).
# The internal key is what the retrieval pipeline will eventually filter
# Chroma metadata by; the label is what the user sees.
SUBJECTS: list[tuple[str, str]] = [
    ("arabic",          "العربية  ·  Arabic"),
    ("islamic_studies", "الدراسات الإسلامية  ·  Islamic Studies"),
    ("social_studies",  "الاجتماعيات  ·  Social Studies"),
    ("english",         "اللغة الإنجليزية  ·  English"),
    ("math",            "الرياضيات  ·  Math"),
]
SUBJECT_LABELS = [label for _, label in SUBJECTS]


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

    settings = await cl.ChatSettings(
        [
            Select(
                id="subject",
                label="Subject  ·  المادة",
                values=SUBJECT_LABELS,
                initial_index=0,
            ),
        ]
    ).send()

    initial_subject = _label_to_key(settings["subject"])
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
async def on_settings_update(settings: dict) -> None:
    label = settings.get("subject")
    if label:
        cl.user_session.set("subject", _label_to_key(label))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    grade = cl.user_session.get("grade")
    subject = cl.user_session.get("subject")

    if grade is None or subject is None:
        await cl.Message(
            content=(
                "Please pick a subject from the settings panel (⚙) before "
                "asking a question."
            ),
        ).send()
        return

    pretty_subject = _key_to_label(subject)
    await cl.Message(
        content=(
            f"⚙️  **Pipeline not connected yet  ·  لم يتم ربط النظام بعد**\n\n"
            f"Captured your profile:\n"
            f"- **Grade  ·  الصف:** {grade} ✓\n"
            f"- **Subject  ·  المادة:** {pretty_subject} ✓\n\n"
            f"_Once retrieval, reranking, and generation are wired in, your "
            f"question (\"{message.content}\") will be answered from the "
            f"Grade {grade} {pretty_subject} textbook with inline citations._"
        ),
    ).send()
