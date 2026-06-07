#!/usr/bin/env python3
"""Static blog build — zero dependencies, pure standard library.

For every posts/*.md:
  1. parse the --- frontmatter block into a dict
  2. expand {% name %}...{% endname %} components via the COMPONENTS registry
  3. convert remaining Markdown prose to HTML; raw HTML blocks pass through
  4. auto-generate the on-this-page TOC from ## / ### headings
     (heading may carry {#explicit-id} and {toc:short label} overrides)
  5. assemble into templates/base.html with styles/site.css (+ optional
     per-post styles/<slug>.css) inlined, frontmatter-driven meta cards,
     and a post-specific footer note
  6. write dist/<slug>.html
Then regenerate dist/index.html from every non-draft post's frontmatter.

Adding a diagram type = one render_x(block) + a COMPONENTS entry. Run:
  python3 build.py
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).parent          # build/ — the tracked source: posts, templates, styles
OUT = ROOT.parent                     # repo root — GitHub Pages serves the generated HTML here
POSTS = ROOT / "posts"
STYLES = ROOT / "styles"
TEMPLATE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
INDEX_TEMPLATE = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (STYLES / "site.css").read_text(encoding="utf-8")

# Left-sidebar meta cards: (label, frontmatter value key, frontmatter sub key).
# A card whose value is absent is skipped, so posts can carry 3 or 4 cards.
META_CARDS = [
    ("By", "author", "authorsub"),
    ("Updated", "date", "datesub"),
    ("Read time", "reading", "readingsub"),
    ("Scope", "scope", "scopesub"),
]


# ── small shared helpers ──────────────────────────────────────────────────────
def slugify(text):
    s = re.sub(r"<[^>]+>", "", text).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def inline(text, bold_tag="strong"):
    """Inline Markdown: links, **bold**, *italic*, `code`."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", rf"<{bold_tag}>\1</{bold_tag}>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def aria(value):
    return f' aria-label="{value}"' if value else ""


def split_pipes(rest, n=None):
    parts = [p.strip() for p in rest.split("|")]
    if n is not None:
        parts += [""] * (n - len(parts))
    return parts


def split_vendor(cell):
    label, _, vendor = cell.partition("/")
    return label.strip(), vendor.strip()


def parse_lines(block):
    """Yield (key, variant_tokens, value) for each 'key[ tokens]: value' line."""
    for raw in block.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        head, _, value = line.partition(":")
        tokens = head.split()
        yield tokens[0], tokens[1:], value.strip()


def caption_html(text):
    return f'\n\n      <p class="caption">{inline(text)}</p>' if text else ""


# ── component renderers ───────────────────────────────────────────────────────
def render_flow(block):
    """Linear pipeline of nodes with arrows. Variants: quiet, slow, model."""
    a = cap = ""
    nodes, legend = [], []
    for key, toks, value in parse_lines(block):
        if key == "aria":
            a = value
        elif key == "caption":
            cap = value
        elif key == "legend":
            legend = [tuple(p.split("=", 1)) for p in value.split("|") if "=" in p]
        elif key == "node":
            variant = toks[0] if toks else ""
            label, text, sub = split_pipes(value, 3)[:3]
            nodes.append((variant, label, text, sub))

    cells = []
    for i, (variant, label, text, sub) in enumerate(nodes):
        if i:
            cells.append('          <div class="flow-arrow" aria-hidden="true">&#8594;</div>')
        cls = "flow-node" + (f" fn-{variant}" if variant else "")
        parts = [
            f'            <div class="fn-label">{label}</div>',
            f'            <div class="fn-text">{text}</div>',
        ]
        if sub:                                       # omit empty sub line, as in the originals
            parts.append(f'            <div class="fn-sub">{sub}</div>')
        cells.append(f'          <div class="{cls}">\n' + "\n".join(parts) + "\n          </div>")

    legend_html = ""
    if legend:
        items = "\n".join(
            f'          <span><i class="lg-{k.strip()}"></i>{v.strip()}</span>'
            for k, v in legend
        )
        legend_html = f'\n        <div class="flow-legend" aria-hidden="true">\n{items}\n        </div>'

    cap_html = f'\n        <p class="flow-caption">{inline(cap, bold_tag="b")}</p>' if cap else ""
    return (
        f'      <div class="flow" role="img"{aria(a)}>\n'
        f'        <div class="flow-row">\n' + "\n".join(cells) + "\n        </div>"
        f'{legend_html}{cap_html}\n'
        f'      </div>'
    )


def render_stack(block):
    """Vertical layered stack, top to bottom."""
    a = cap = ""
    rows = []
    for key, toks, value in parse_lines(block):
        if key == "aria":
            a = value
        elif key == "caption":
            cap = value
        elif key == "flow":
            rows.append(("flow", value))
        elif key == "callout":
            rows.append(("callout", value))
        elif key == "layer":
            role = toks[0] if toks else ""
            num = toks[1] if len(toks) > 1 else ""
            title, tag, content = split_pipes(value, 3)[:3]
            rows.append(("layer", role, num, title, tag, content))

    out, seen_layer = [f'      <div class="stack" role="figure"{aria(a)}>'], False
    for row in rows:
        if row[0] == "layer":
            _, role, num, title, tag, content = row
            if seen_layer:
                out.append("")
            seen_layer = True
            tag_span = f'<span class="stack-tag">{tag}</span>' if tag else ""
            out.append(
                f'        <div class="stack-layer" data-role="{role}">\n'
                f'          <div class="stack-num">{num}</div>\n'
                f'          <div class="stack-body">\n'
                f'            <div class="stack-title">{title}{tag_span}</div>\n'
                f'            <div class="stack-content">{content}</div>\n'
                f'          </div>\n'
                f'        </div>'
            )
        elif row[0] == "flow":
            out.append(
                f'        <div class="stack-flow"><div class="stack-flow-arrow">↓</div>'
                f'<div class="stack-flow-label">{row[1]}</div></div>'
            )
        elif row[0] == "callout":
            out.append(f'        <div class="stack-callout"><span>{inline(row[1])}</span></div>')
    out.append("      </div>")
    return "\n".join(out) + caption_html(cap)


def render_matrix(block):
    """Capability grid; cell states: . | supports | default."""
    a = cap = ""
    cols, body, legend = [], [], []
    for key, toks, value in parse_lines(block):
        if key == "aria":
            a = value
        elif key == "caption":
            cap = value
        elif key == "cols":
            cols = [split_vendor(c) for c in split_pipes(value)]
        elif key == "legend":
            legend = [tuple(p.split("=", 1)) for p in value.split("|") if "=" in p]
        elif key == "row":
            cells = split_pipes(value)
            body.append((split_vendor(cells[0]), cells[1:]))

    def th(label, vendor, cls=""):
        cls_attr = f' class="{cls}"' if cls else ""
        span = f'<span class="matrix-vendor-tag">{vendor}</span>' if vendor else ""
        return f'<th{cls_attr}>{label}{span}</th>'

    def td(state):
        state = state.strip()
        if state == "supports":
            return '<td class="matrix-cell matrix-supports" aria-label="supported"><span class="matrix-dot"></span></td>'
        if state == "default":
            return '<td class="matrix-cell matrix-default" aria-label="default pairing"><span class="matrix-dot"></span></td>'
        return '<td class="matrix-cell"></td>'

    header_ths = ['              <th class="matrix-corner"></th>']
    header_ths += [f"              {th(l, v)}" for l, v in cols]
    thead = "          <thead>\n            <tr>\n" + "\n".join(header_ths) + "\n            </tr>\n          </thead>"

    body_rows = []
    for (label, vendor), states in body:
        cells = [f'              {th(label, vendor, "matrix-row")}']
        cells += [f"              {td(s)}" for s in states]
        body_rows.append("            <tr>\n" + "\n".join(cells) + "\n            </tr>")
    tbody = "          <tbody>\n" + "\n".join(body_rows) + "\n          </tbody>"

    legend_html = ""
    if legend:
        spans = "\n".join(
            f'          <span><span class="matrix-legend-dot is-{k.strip()}"></span> {v.strip()}</span>'
            for k, v in legend
        )
        legend_html = f'\n        <div class="matrix-legend">\n{spans}\n        </div>'

    return (
        f'      <div class="matrix-wrap" role="figure"{aria(a)}>\n'
        f'        <table class="matrix">\n{thead}\n{tbody}\n        </table>'
        f'{legend_html}\n'
        f'      </div>'
    ) + caption_html(cap)


COMPONENTS = {
    "flow": render_flow,
    "stack": render_stack,
    "matrix": render_matrix,
}


# ── page assembly ─────────────────────────────────────────────────────────────
def parse_heading(text):
    """'Title {#id} {toc:Short label}' -> (visible_title, id, toc_label).
    Both markers optional; default id = slugify(title), default label = title."""
    label = hid = None
    m = re.search(r"\{toc:([^}]*)\}", text)
    if m:
        label = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    m = re.search(r"\{#([\w-]+)\}", text)
    if m:
        hid = m.group(1)
        text = text[:m.start()] + text[m.end():]
    text = text.strip()
    return text, (hid or slugify(text)), (label if label is not None else text)


def render_body(body):
    """Body Markdown -> (html, toc). Components are stashed first so the
    blank-line paragraph splitter never cuts through them."""
    stash = {}

    def keep(match):
        name, inner = match.group(1), match.group(2)
        renderer = COMPONENTS.get(name)
        if renderer is None:
            return match.group(0)
        key = f"@@CMP{len(stash)}@@"
        stash[key] = renderer(inner)
        return key

    body = re.sub(r"\{%\s*(\w+)\s*%\}(.*?)\{%\s*end\1\s*%\}", keep, body, flags=re.S)

    def keep_pre(match):                       # stash <pre>…</pre> verbatim: preserve
        key = f"@@PRE{len(stash)}@@"           # internal blank lines + column-0 position,
        stash[key] = match.group(0)            # and keep the blank-line splitter out of it
        return key

    body = re.sub(r"<pre>.*?</pre>", keep_pre, body, flags=re.S)

    out, toc = [], []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block:
            continue
        if block in stash:
            out.append(stash[block])
        elif block.startswith("### "):
            text, hid, label = parse_heading(block[4:])
            toc.append((3, hid, label))
            out.append(f'      <h3 id="{hid}">{inline(text)}</h3>')
        elif block.startswith("## "):
            text, hid, label = parse_heading(block[3:])
            toc.append((2, hid, label))
            out.append(f'      <h2 id="{hid}">{inline(text)}</h2>')
        elif re.match(r"<(div|details|table|figure|ul|ol|blockquote|style|section|aside|nav|pre|p|h[1-6]|hr|script)\b", block):
            out.append("      " + block)        # block-level raw HTML passthrough
        else:
            # paragraph — may legitimately start with an inline tag (<strong>, <a>, <code>)
            cls = ' class="lede"' if not out else ""
            out.append(f"      <p{cls}>{inline(block)}</p>")
    return "\n\n".join(out), toc


def render_toc(toc):
    # quote=False: labels come from source/headings and use literal ' and " (not entities)
    return "\n".join(
        f'        <a href="#{hid}" class="toc-link toc-level-{lvl}">{html.escape(label, quote=False)}</a>'
        for lvl, hid, label in toc
    )


def render_meta_cards(meta):
    cards = []
    for label, vkey, skey in META_CARDS:
        val = meta.get(vkey, "")
        if not val:
            continue
        sub = meta.get(skey, "")
        sub_html = f'\n        <div class="meta-sub">{sub}</div>' if sub else ""
        cards.append(
            f'      <div class="meta-card">\n'
            f'        <div class="meta-label">{label}</div>\n'
            f'        <div class="meta-value">{val}</div>{sub_html}\n'
            f'      </div>'
        )
    return "\n".join(cards)


def parse_frontmatter(raw):
    if not raw.startswith("---"):
        return {}, raw
    _, fm, body = raw.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, body.strip()


def render_post(meta, body, slug):
    content, toc = render_body(body)
    post_css = STYLES / f"{slug}.css"
    extra = ("\n\n" + post_css.read_text(encoding="utf-8")) if post_css.exists() else ""
    page = TEMPLATE.replace("{{ styles }}", CSS + extra)
    page = page.replace("{{ meta_cards }}", render_meta_cards(meta))
    page = page.replace("{{ toc }}", render_toc(toc))
    page = page.replace("{{ content }}", content)
    for key, val in {**meta, "slug": slug}.items():
        page = page.replace("{{ " + key + " }}", val)
    page = re.sub(r"\{\{ \w+ \}\}", "", page)
    return page, toc, content


def render_index(entries):
    entries = sorted(entries, key=lambda m: m.get("date", ""), reverse=True)
    items = []
    for m in entries:
        items.append(
            '      <li class="post-item">\n'
            f'        <div class="post-date">{m.get("date", "")}</div>\n'
            f'        <h3 class="post-title"><a href="{m["slug"]}.html">{m.get("title", "")}</a></h3>\n'
            f'        <p class="post-desc">{m.get("summary", "")}</p>\n'
            '      </li>'
        )
    page = INDEX_TEMPLATE.replace("{{ styles }}", CSS)
    page = page.replace("{{ posts }}", "\n".join(items))
    return page


def build():
    posts = sorted(POSTS.glob("*.md"))
    index_entries = []
    for md in posts:
        meta, body = parse_frontmatter(md.read_text(encoding="utf-8"))
        meta.setdefault("pagetitle", meta.get("title", ""))   # <head> title; defaults to the h1
        slug = meta.get("slug", md.stem)
        page, toc, content = render_post(meta, body, slug)
        draft = meta.get("draft", "").lower() == "true"
        dest = (ROOT / "drafts") if draft else OUT       # drafts preview only, never the live root
        if draft:
            dest.mkdir(exist_ok=True)
        (dest / f"{slug}.html").write_text(page, encoding="utf-8")
        diagrams = sum(content.count(f'class="{c}"') for c in ("flow", "stack", "matrix-wrap"))
        print(f"  built {'drafts/' if draft else ''}{slug}.html  "
              f"({len(toc)} headings, {diagrams} diagrams{', draft — not indexed' if draft else ''})")
        if not draft:
            index_entries.append({**meta, "slug": slug})

    (OUT / "index.html").write_text(render_index(index_entries), encoding="utf-8")
    print(f"  built index.html  ({len(index_entries)} posts listed)")
    print(f"done — {len(posts)} post(s) -> {OUT}")


if __name__ == "__main__":
    build()
