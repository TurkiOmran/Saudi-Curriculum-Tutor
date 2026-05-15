"""Outer graph — rewrite → decompose → map(inner) → merge.

Per L4 + L15:
  - `decompose` produces `list[TaskState]`. Even single-task queries go
    through this as `[task]`.
  - The map step is a plain sequential `for` loop (one task at a time)
    invoking the inner graph. Per L15, parallel is a one-line upgrade
    later (swap the loop for LangGraph `Send`).
  - `merge` joins each task's answer into the final response. When there
    is only one task this is a trivial passthrough (L4).
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.inner import inner_graph
from src.graph.nodes.decompose import decompose_node
from src.graph.nodes.rewrite import rewrite_node
from src.graph.state import OuterState, TaskState


async def map_tasks_node(state: OuterState) -> dict:
    """Sequential map: invoke the inner graph once per decomposed task."""
    updated: list[TaskState] = []
    for task in state["tasks"]:
        result = await inner_graph.ainvoke(task)
        updated.append(result)
    return {"tasks": updated}


def _format_task_answer(idx: int, task: TaskState, total: int) -> str:
    answer = task.get("answer", "")
    if total == 1:
        return answer
    header = f"### Part {idx + 1}: {task.get('standalone_question', '')}"
    return f"{header}\n\n{answer}"


async def merge_node(state: OuterState) -> dict:
    """Combine per-task answers into the final response."""
    tasks = state["tasks"]
    total = len(tasks)
    parts = [_format_task_answer(i, t, total) for i, t in enumerate(tasks)]
    final = "\n\n---\n\n".join(p for p in parts if p)
    return {"final_answer": final}


def _build_outer() -> "Any":  # noqa: F821
    g = StateGraph(OuterState)
    g.add_node("rewrite", rewrite_node)
    g.add_node("decompose", decompose_node)
    g.add_node("map_tasks", map_tasks_node)
    g.add_node("merge", merge_node)

    g.set_entry_point("rewrite")
    g.add_edge("rewrite", "decompose")
    g.add_edge("decompose", "map_tasks")
    g.add_edge("map_tasks", "merge")
    g.add_edge("merge", END)

    return g.compile()


outer_graph = _build_outer()
