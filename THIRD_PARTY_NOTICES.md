# Third-party notices

Most of this repository is original work, released under the MIT License in
[LICENSE](LICENSE). The items below were written by others and are
redistributed here under their own licenses. Each one keeps its license text
next to the files it covers.

| Path | Upstream | License | License text |
|---|---|---|---|
| `agents/skills/rag-blueprint/` | NVIDIA RAG Blueprint, <https://github.com/NVIDIA-AI-Blueprints/rag> | Apache License 2.0 | [`agents/skills/rag-blueprint/LICENSE`](agents/skills/rag-blueprint/LICENSE) |
| `claude/skills/graphify/` | graphify by Safi Shamsi, <https://github.com/Graphify-Labs/graphify> (formerly `safishamsi/graphify`) | MIT License | [`claude/skills/graphify/LICENSE`](claude/skills/graphify/LICENSE) |

## Notes

- **rag-blueprint.** The skill's own front matter declares `license: Apache-2.0`
  and names NVIDIA as its author. The files are redistributed unmodified.
  Copyright NVIDIA Corporation.
- **graphify.** This copy of the `/graphify` skill was taken in April 2026, while
  upstream was MIT-licensed. Upstream relicensed to Apache 2.0 on 2026-07-22 and
  keeps the original MIT text in its `LICENSE-MIT` file; that text is
  reproduced here. If you replace this copy with a newer upstream release, take
  its Apache 2.0 `LICENSE` and `NOTICE` along with it.

## Adding third-party content

When you copy in a skill, agent, script or document that someone else wrote:

1. Put its license text in a `LICENSE` file inside its folder (verbatim, from
   the upstream source, never retyped), plus a `NOTICE` file if upstream ships
   one.
2. Add a row to the table above.
