"""Programmatic smoke test of the agentic pipeline — no Chainlit, no UI.

Day-one milestone per L10: with `llm.backend: fake` in `config.yaml`, this
runs the full outer graph end-to-end without an API key, printing the
merged answer + the inner-graph debug dict.

Usage (from repo root):

    uv run python scripts/smoke_run.py "what is photosynthesis?"
    uv run python scripts/smoke_run.py "explain X and quiz me" --grade 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Make `src.*` importable when running this script directly from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.outer import outer_graph  # noqa: E402
from src.graph.state import initial_outer_state  # noqa: E402


def _jsonable(obj):  # noqa: ANN001, ANN202
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


async def main(question: str, grade: int, subject: str) -> int:
    initial = initial_outer_state(
        grade=grade,
        subject=subject,
        user_query=question,
    )
    final = await outer_graph.ainvoke(initial)

    print("\n=== FINAL ANSWER ===\n")
    print(final.get("final_answer", "(no answer)"))

    tasks = final.get("tasks") or []
    for i, task in enumerate(tasks):
        print(f"\n=== TASK {i + 1} DEBUG ===\n")
        print(f"intent             : {task.get('intent')}")
        print(f"self_check_passed  : {task.get('self_check_passed')}")
        print(f"refused            : {task.get('refused')}")
        print(f"chunks             : {len(task.get('chunks') or [])}")
        print(f"citations          : {len(task.get('citations') or [])}")
        debug = task.get("debug") or {}
        if debug:
            print("debug              :", json.dumps(_jsonable(debug), indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("question", help="The student's question.")
    p.add_argument("--grade", type=int, default=7, choices=[4, 7, 10])
    p.add_argument("--subject", default="islamic_studies")
    args = p.parse_args()
    sys.exit(asyncio.run(main(args.question, args.grade, args.subject)))
