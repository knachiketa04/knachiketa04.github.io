# Diagram components — the shared contract

This is the single source of truth for the blog's diagram vocabulary. Two
consumers read it:

- **`build.py`** implements each component listed here (one `render_x()` per type).
- **The `concept-to-post` skill** authors diagrams by emitting these components.

When the two ever disagree, this file wins. Add a component here the moment you
add its renderer, and the skill picks it up for free.

---

## The three rules (how the palette grows)

1. **Prefer a component.** If a diagram fits one of the grammars below, author it
   as that component. You get consistency and a 5-line edit instead of 40 lines
   of `<div>`s.
2. **Freeform when nothing fits.** A genuinely new visual is written as raw HTML
   straight in the Markdown (see *Escape hatch*). Your creativity is never capped
   by the palette. This is where new ideas start.
3. **Promote on the second sighting.** The first time you invent a bespoke
   diagram, it stays raw HTML. The *second* time you reach for the same shape,
   promote it: move its CSS into `styles/site.css`, add a `render_x()` to
   `build.py`, and document it here. Componentize what has proven it recurs;
   never build a component for a one-off.

The palette today is `flow`, `stack`, `matrix`. It grew from `flow` (used 5×
before it earned a component). Everything else in the existing posts
(`cwindow`, `dtree`, `usecase`, `compose`, `lifecycle`) is still one-off raw HTML
and stays that way until it recurs.

---

## Syntax basics

A component is a fenced block:

```
{% name %}
key: value
key variant: a | b | c
{% endname %}
```

- One directive per line, `key: value`.
- `|` separates fields within a value.
- `aria:` sets the figure's accessible label (always include it).
- `caption:` renders the muted caption under the figure. `**bold**` allowed.
- Plain text and HTML entities (`↓`, `·`, `↔`, `&#8594;`) pass through verbatim.

Anything `build.py` doesn't recognize as a registered component is left in the
Markdown untouched, so an unknown `{% foo %}` block is harmless, not an error.

---

## `flow` — a linear pipeline

A left-to-right chain of nodes with arrows. Use for "data moves through stages,"
"where's the slow step," cold/warm paths. The workhorse.

```
{% flow %}
aria: <accessible description of the whole flow>
node: Label | main text | sub text
node quiet: Storage | lands on disk | 3% full, idle
node slow: Slow part | the real work | three passes
node model: The tutor | a big 32B model | ~61 GB brain
legend: slow=the real slow part | model=the model doing AI work | quiet=storage, sitting quiet
caption: One sentence under the diagram. **Bold** the key phrase.
{% endflow %}
```

- **Node variants** (the `word` after `node`): *(none)* = neutral; `quiet` =
  dashed teal (storage idling); `slow` = yellow (the bottleneck); `model` =
  violet (AI doing work). Arrows are inserted automatically between nodes.
- `legend` keys map to the variant colors (`slow`, `model`, `quiet`).

## `stack` — a layered system, top to bottom

Vertical layers with connectors between them and optional callouts. Use for
"how a system is layered," bottom-to-top builds, dependency stacks.

```
{% stack %}
aria: <accessible description>
layer user 05: You | human surface | prompts · slash commands · edits
flow: input
layer config 04: Harness configuration | your knobs | CLAUDE.md · skills · hooks
callout: **Agent SDK**, a way to build your own. Not a layer.
flow: shapes behavior of
layer model 01: Claude model | stateless | tokens → next-token distribution
caption: One sentence under the diagram.
{% endstack %}
```

- `layer <role> <num>: title | tag | content`. The **role** sets the accent
  color and is one of `user` (yellow), `config` (teal), `harness` (grey),
  `api` (dashed slate), `model` (violet). Extend the role palette in `site.css`.
- `flow: <label>` is the connector arrow shown *between* layers.
- `callout: <text>` is a violet aside attached under the preceding layer.

## `matrix` — a capability grid

A table of rows × columns where each cell is a state dot. Use for compatibility,
"who supports what," feature comparisons.

```
{% matrix %}
aria: <accessible description>
cols: Claude/Anthropic | GPT/OpenAI | Gemini/Google | Open-source/Llama · Qwen
row: Claude Code/Anthropic | default | . | . | .
row: Cursor | supports | supports | supports | .
legend: default=default / first-party pairing | supports=supported
caption: One sentence under the diagram.
{% endmatrix %}
```

- `cols:` and each `row:` label may carry a vendor tag after a `/`
  (`Label/Vendor`); omit the slash for no tag.
- **Cell states:** `.` (or empty) = blank; `supports` = teal dot; `default` =
  glowing violet dot. Cells line up with the columns in order.

---

## Escape hatch — raw HTML for one-offs

When a concept needs a visual no component covers, write the HTML directly in the
Markdown. It passes through untouched (any block starting with `<`). Keep its CSS
inline in a `<style>` scoped block or, if it might recur, add it to `site.css`
and plan to promote it.

```html
<div class="cwindow" role="figure" aria-label="...">
  ... bespoke markup ...
</div>
```

This is not a workaround; it is the intended on-ramp. Every component here began
as raw HTML and got promoted once it earned its place.
