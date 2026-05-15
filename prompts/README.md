# `prompts/` — Jinja2 prompt templates, one per node

Per L10 + L19, prompts live out of code so they can be iterated on without
touching Python. Format is **Jinja2** (`.j2`). The generate template uses
real iteration to render pre-numbered chunks (`[1] … [2] …`) that L5
depends on.

## Files

| Template          | Used by           | Variables                                                                                                                     | Phase |
| ----------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----- |
| `intent.j2`       | `nodes/intent`    | `question` — the standalone question.                                                                                          | C     |
| `self_check.j2`   | `nodes/self_check`| `question`, `chunks` (list of `Chunk`).                                                                                        | C     |
| `generate.j2`     | `nodes/generate`  | `question`, `chunks`, `intent`, `language`. Branches on `intent` (qa / explain / summarize / revise / quiz).                   | C     |
| `decompose.j2`    | `nodes/decompose` | `question`.                                                                                                                    | C     |
| `rewrite.j2`      | `nodes/rewrite`   | `question`, `history` (last `memory.max_turns` turns).                                                                         | E     |

## Loading

Resolved by Jinja's `FileSystemLoader` rooted at this folder. Nodes import
a small helper (lands in Phase C alongside the first real prompt):

```python
from jinja2 import Environment, FileSystemLoader
env = Environment(
    loader=FileSystemLoader(REPO_ROOT / "prompts"),
    autoescape=False,           # prompts are not HTML
    trim_blocks=True,
    lstrip_blocks=True,
)
tpl = env.get_template("generate.j2")
prompt = tpl.render(question="…", chunks=[…], intent="explain", language="ar")
```

## Conventions

- One template per node, named after the node.
- **Render chunks via the `{% for %}` loop**, not a pre-rendered string —
  the template tells the whole grounding story to anyone reading it.
- `loop.index` is the 1-based citation number you want ALLaM to emit, so
  `[{{ loop.index }}]` is the marker.
- Keep `system` and `user` separated by a top-level `---` divider (the
  node splits on this before calling the LLM).

## Not here

- Python-side templating helpers — `src/graph/nodes/*` use these templates
  but the loader code lives next to the first real-LLM node in Phase C.
- Per-grade or per-subject prompt variants — single template per node;
  variation goes through `{% if %}` branches inside the template.
