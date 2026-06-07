---
title: The harness, the model, and me
pagetitle: The harness, the model, and me — a mental model for AI coding agents
subtitle: A mental model for AI coding agents, notes from the AIHomeLab
byline: Kumar Nachiketa · AIHomeLab · Personal capacity
author: Kumar Nachiketa
authorsub: AIHomeLab · personal capacity
date: 2026-05-31
datesub: Living document
scope: Mental model for AI coding agents
scopesub: Examples from Claude Code; concepts apply to Cursor, Cline, Codex, Antigravity, and custom SDK builds
slug: harness-model-me
description: A mental model for AI coding agents — Claude Code, Cursor, Cline, Codex, Antigravity, custom SDK builds. The harness/model split, context windows, tools, subagents, skills, MCP, and governance.
summary: Five things I had to internalize about AI coding agents (Claude Code, Cursor, Cline, Codex, Antigravity, custom SDK builds): the harness/model split, where context goes, why descriptions matter, picking the right primitive, soft vs hard governance.
sourcenote: <strong>A note on sources.</strong> This is my mental model of how Claude Code works, built up through conversations with Claude and months of running my AIHomeLab. It's an interpretation, not Anthropic's official documentation. If you spot something factually wrong, a gap, or a place where my framing misses what's actually happening under the hood, I'd appreciate the correction. I'd rather update this than be wrong in public.
---

      <p class="lede">Here's how I think about AI coding agents now, after spending weeks building my AIHomeLab in one. The category includes Claude Code, Cursor, Cline, Codex, Antigravity, and whatever you build with one of the agent SDKs. They all wrap a frontier model in a stateful loop with tools, memory, and procedures. My examples here are from Claude Code because that's the one I learned in, but the mental model travels. If you use any of these systems, the same five insights apply.</p>

I wrote these notes for myself, to remember what stuck rather than transcribe everything I did.

      <hr>

## TL;DR {#tldr} {toc:TL;DR}

      <p class="lede">If you have 2 minutes, here's what I learned compressed into five things.</p>

I've worked hands-on with Claude Code building my AIHomeLab. <strong>The same architecture shows up across the whole AI coding agent category (Cursor, Cline, Codex, Antigravity, custom SDK builds): a frontier model wrapped by a <em>harness</em>.</strong> The model is the brain, stateless and forgetful between calls. The harness is the body, the program that gives the model a loop with tools, memory, and governance. Almost everything I could shape, and almost every frustration I hit, lived in the harness configuration layer, not in the model.

<strong>The five things I had to internalize:</strong>

      <ol>
        <li><strong>Model vs. harness diagnostic.</strong> When something misbehaves: was it the <em>model</em> (wrong code, weak reasoning) or the <em>harness</em> (wrong tool, missing config)? Different layers, different fixes.</li>
        <li><strong>Tool results dominate context.</strong> Heavy file reads, noisy bash output, and web fetches eat most of the token budget. I learned to be deliberate, and to delegate to subagents for anything read-heavy.</li>
        <li><strong>Descriptions are the universal discovery surface.</strong> Tools, skills, subagents, MCP tools, all rely on descriptions to tell the model when to use them. When something I built wasn't getting used, the fix was always the description, not the body.</li>
        <li><strong>Pick the right primitive.</strong> New capability → MCP server. Bounded autonomous work → subagent. Procedure with user interaction → skill. One-off action → built-in tool.</li>
        <li><strong>Soft vs hard governance.</strong> Safety and security-critical things go in permissions and hooks (deterministic). Conventions and style go in CLAUDE.md or skills (suggestions). Match the mechanism to the stakes.</li>
      </ol>

What stuck most: the harness is a configurable system, whichever agent you're using. Most frustrations resolve once you know which knob to turn for which problem.

<strong>Document map</strong> (jump to whichever pulls you in):

      <ul>
        <li><a href="#stack">The stack</a>: model vs. harness mental model</li>
        <li><a href="#conversation">What a conversation actually is</a>: tokens, context window, prompt cache</li>
        <li><a href="#tools">Tools and tool calls</a>: how the model invokes work</li>
        <li><a href="#subagents">Subagents</a>: context isolation through delegation</li>
        <li><a href="#skills">Skills</a>: procedural knowledge with progressive disclosure</li>
        <li><a href="#mcp">MCP</a>: extending the toolbelt with external capabilities</li>
        <li><a href="#picking-primitive">Picking the right primitive</a>: the decision tree</li>
        <li><a href="#governance">Memory, hooks, permissions, plan mode</a>: the governance layer</li>
        <li><a href="#productivity">Productivity patterns</a>: the synthesis</li>
      </ul>

      <hr>

## The stack {#stack} {toc:The stack}

People say "Claude" to mean four different things: the model, the API, the harness, and the SDK. I conflated them at first too. The lesson that stuck: when something goes wrong, you can't fix it until you know which layer is broken.

### The stack, from bottom to top {#five-layers} {toc:The stack, bottom to top}

{% stack %}
aria: The five-layer conceptual stack
layer user 05: You | human surface | prompts · slash commands · edits
flow: input
layer config 04: Harness configuration | your knobs | CLAUDE.md · skills · hooks · memory · MCP · subagents · permissions
flow: shapes behavior of
layer harness 03: Harness program | vendor-built loop | Claude Code · Cursor · Cline · Aider · Antigravity · custom
callout: **Agent SDK**, kit for building your own harness. Not a layer, a way to author one.
flow: inference + tool-call protocol
layer api 02: Anthropic API | HTTP contract | messages + tool defs ↔ response + tool calls
flow: runs the model
layer model 01: Claude model | stateless | Sonnet · Opus · Haiku · tokens → next-token distribution
{% endstack %}

      <p class="caption">Bottom-up: model (stateless function) → API (HTTP contract) → harness (the agent loop). Above the harness sit two user-facing layers: your configuration (CLAUDE.md, skills, hooks, memory) and you (prompts, slash commands). The SDK is a related concept, the kit for building harnesses, shown as a callout, not a layer in the running stack.</p>

<strong>Claude is the model.</strong> A neural network, a function from tokens to a next-token distribution. Stateless. Each call is independent; the model has no memory of yesterday's chat. "Sonnet 4.6," "Opus 4.7," "Haiku 4.5" are snapshots of model weights, different brains in the same family.

<strong>The Anthropic API is the contract.</strong> An HTTP endpoint in front of the model. You POST messages and tool definitions; you get back text and tool-call requests. The API does not execute tools. It does not remember the conversation. If you want an agent, you build the loop.

<strong>The harness is the agent loop.</strong> A program that wraps the API and gives the model a body: Claude Code, Cursor, Aider, Antigravity, or anything custom-built. It maintains history, assembles the system prompt, <em>executes tool calls</em> (when the model says "run <code>ls</code>," the harness actually runs it), manages context, enforces permissions, spawns subagents. The model is the brain; the harness is everything else.

<strong>The SDK is for building harnesses.</strong> Same primitives Anthropic uses, packaged as a library. If Claude Code is "the harness Anthropic ships," the SDK is "build your own."

The practical rule when something misbehaves: <strong>was it the model or the harness?</strong> "Claude didn't run my skill" is almost always a harness problem: discovery, permissions, or configuration. "Claude wrote a bug" is almost always a model problem. Different layers, different fixes.

### Harness and model are independent {#harness-model} {toc:Harness ↔ model independence}

{% matrix %}
aria: Harness and model compatibility matrix
cols: Claude/Anthropic | GPT/OpenAI | Gemini/Google | Open-source/Llama · Qwen · GPT-OSS
row: Claude Code/Anthropic | default | . | . | .
row: Codex/OpenAI | . | default | . | .
row: Antigravity/Google | supports | . | default | supports
row: Cursor | supports | supports | supports | .
row: Cline · Aider · Continue.dev | supports | supports | supports | supports
row: Custom/SDK-built | supports | . | . | .
legend: default=default / first-party pairing | supports=supported
{% endmatrix %}

      <p class="caption">Harness and model are independent dimensions. An AI coding tool is a (harness, model) pair.</p>

The conflation worth killing: "Claude Code = Claude." It doesn't. The harness and the model are independent choices.

Anthropic ships Claude Code, OpenAI ships Codex, Google ships Antigravity, each defaults to its own model. Third-party harnesses are mostly model-agnostic: Cursor, Cline, Aider, Continue.dev let you point at Claude, GPT, Gemini, or open-source models. Build your own harness with the Agent SDK and pick whatever model you want.

So when you compare "Claude Code vs. Cursor," you're comparing two harnesses, not two models. The same Claude weights feel different across them because the <em>harness</em> shapes the experience: what system prompt the model sees, what tools it has, how context is managed, what gets cached, how permissions work. <strong>Model is raw capability. Harness is workflow.</strong>

### Inside the harness — where you live {#inside-harness} {toc:Inside the harness}

      <div class="surface" role="figure" aria-label="Vendor-built surface vs user-configured surface">
        <div class="surface-col surface-vendor">
          <div class="surface-header">
            <span class="surface-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </span>
            <h4>Vendor-built surface</h4>
            <span class="surface-tag">fixed code</span>
          </div>
          <ul class="surface-items">
            <li>Agent loop &amp; context management</li>
            <li>Built-in tools<span class="surface-sub">Read · Edit · Bash · Glob · Grep · WebFetch</span></li>
            <li>Base system prompt</li>
            <li>Permissions engine</li>
            <li class="surface-socket"><span class="surface-socket-label">Extension points</span><span class="surface-sub">skills · hooks · MCP · subagents · memory</span></li>
          </ul>
        </div>
        <div class="surface-bridge" aria-hidden="true">
          <div class="surface-bridge-arrow">⟵</div>
          <div class="surface-bridge-label">plugs<br>into</div>
        </div>
        <div class="surface-col surface-user">
          <div class="surface-header">
            <span class="surface-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>
            </span>
            <h4>Your harness engineering</h4>
            <span class="surface-tag">you author</span>
          </div>
          <ul class="surface-items">
            <li><code>CLAUDE.md</code><span class="surface-sub">appended to base prompt</span></li>
            <li>Skills<span class="surface-sub">loaded on demand</span></li>
            <li>Hooks<span class="surface-sub">deterministic event handlers</span></li>
            <li>MCP servers<span class="surface-sub">external tools</span></li>
            <li>Memory<span class="surface-sub">facts across sessions</span></li>
            <li>Custom subagents<span class="surface-sub">scoped child Claudes</span></li>
            <li>Permissions allowlist<span class="surface-sub">pre-approved actions</span></li>
          </ul>
        </div>
      </div>

      <p class="caption">Inside one harness. Vendor builds the sockets: loop, built-in tools, base prompt, permissions engine, extension points. You author what plugs in.</p>

A single harness instance has two surfaces, and the boundary between them is where productivity is won or lost.

<strong>The vendor's surface is fixed.</strong> Anthropic decides what the agent loop does, which tools are built in (<code>Read</code>, <code>Edit</code>, <code>Bash</code>, <code>Glob</code>, <code>Grep</code>, <code>WebFetch</code>), how context is managed, how permissions work, what the base system prompt says. You don't change any of this, but the vendor also wires <em>extension points</em>: a skills runtime, a hooks runtime, an MCP client, a subagent spawner, a memory loader. The vendor builds the sockets.

<strong>Your surface is what plugs into them.</strong> <code>CLAUDE.md</code> gets appended to the base prompt. Skills get loaded on demand. Hooks fire on events. MCP servers add new tools. Memory persists facts across sessions. Custom subagents are scoped child Claudes you've defined. The permissions allowlist tells the engine what's pre-approved.

This is harness engineering. Your <code>.claude/</code> directory and your settings files are the visible shape of it. When you ask yourself "should I write a skill or a hook or a slash command for this?", you're asking which socket to plug into.

<strong>A useful test</strong>: if you can change something by editing a file in your repo or your <code>~/.claude/</code> directory, you're in the user surface. If changing it would require Anthropic to ship a new release, you're hitting the vendor surface. Most frustrations live at that boundary, and most of them are solvable on the user side once you know which socket to use.

## What a conversation actually is {#conversation} {toc:What a conversation is}

Three things to get straight before "context fills up too fast" can have concrete handles. First, what counts as a unit. Second, what's actually in the bucket. Third, what makes re-using the bucket cheap.

### The unit: tokens {#tokens} {toc:The unit: tokens}

The model doesn't see characters and it doesn't see words. It sees <strong>tokens</strong>: chunks of text decided by the tokenizer that ships with the model.

      <ul>
        <li><strong>English prose</strong>: ~4 characters per token, ~0.75 words per token. "Hello, world!" is about 4 tokens.</li>
        <li><strong>Code</strong>: tokenizes differently. Whitespace, indentation, and punctuation all count. A line of Python costs more than a line of English of the same length.</li>
        <li><strong>Filenames, paths, hashes</strong>: often each character is its own token. SHA hashes are token-heavy.</li>
        <li><strong>Image inputs</strong>: also tokenized. A typical screenshot is ~1500 tokens.</li>
      </ul>

The numbers matter because <strong>everything is metered in tokens</strong>: context window, prompt cache, API bill. When someone says "Sonnet has a 200K context window," they mean 200,000 tokens.

### The bucket: the context window {#context-window} {toc:The bucket: context window}

Every model has a maximum input size: the context window. Hard ceiling.

      <ul>
        <li>Sonnet 4.6, 200K tokens</li>
        <li>Haiku 4.5, 200K tokens</li>
        <li>Opus 4.7, 1M tokens</li>
      </ul>

The window holds <em>everything the model sees on a single API call</em>: base system prompt + <code>CLAUDE.md</code> + loaded skills + memory + conversation history + tool results + this turn's message. When the sum approaches the limit, <strong>autocompact</strong> kicks in: the harness summarizes earlier turns to free space. You stay below the ceiling but you lose fidelity.

So "context fills up too fast" really means: <em>the things you've put in the window are accumulating faster than you've stopped putting them in</em>.

### What actually fills the window {#filling-window} {toc:What fills the window}

I learned the hard way: context doesn't fill because a conversation is long. It fills because some kinds of content are expensive.

      <div class="cwindow" role="figure" aria-label="Context window breakdown for a typical Claude Code turn">
        <div class="cwindow-bar">
          <div class="cwindow-seg cwindow-system" style="width: 5%" title="Base system prompt, 10K tokens">
            <span class="cwindow-seg-label">System</span>
            <span class="cwindow-seg-tokens">10K</span>
          </div>
          <div class="cwindow-seg cwindow-mem" style="width: 1.5%" title="CLAUDE.md + memory, 3K tokens">
            <span class="cwindow-seg-label">Mem</span>
            <span class="cwindow-seg-tokens">3K</span>
          </div>
          <div class="cwindow-seg cwindow-skills" style="width: 1%" title="Loaded skills, 2K tokens">
            <span class="cwindow-seg-label">Skl</span>
            <span class="cwindow-seg-tokens">2K</span>
          </div>
          <div class="cwindow-seg cwindow-history" style="width: 7.5%" title="Conversation history, 15K tokens">
            <span class="cwindow-seg-label">History</span>
            <span class="cwindow-seg-tokens">15K</span>
          </div>
          <div class="cwindow-seg cwindow-tools" style="width: 25%" title="Tool results, 50K tokens (often dominant)">
            <span class="cwindow-seg-label">Tool results</span>
            <span class="cwindow-seg-tokens">50K</span>
          </div>
          <div class="cwindow-seg cwindow-available" style="width: 60%" title="Available, 120K tokens">
            <span class="cwindow-seg-label">Available</span>
            <span class="cwindow-seg-tokens">120K</span>
          </div>
        </div>
        <div class="cwindow-scale">
          <span>0</span>
          <span>50K</span>
          <span>100K</span>
          <span>150K</span>
          <span>200K (Sonnet max)</span>
        </div>
      </div>

      <p class="caption">Typical Claude Code turn. Tool results usually dominate, system overhead is fixed; Reads, Bash output, and WebFetch grow with what you ask for.</p>

In a typical turn:

      <ul>
        <li><strong>Base system prompt</strong>: vendor preamble + tool definitions for all built-in tools + MCP tool definitions. ~5–15K tokens, mostly fixed.</li>
        <li><strong>CLAUDE.md + memory files</strong>: your project instructions + auto-memory. ~1–5K tokens.</li>
        <li><strong>Loaded skills</strong>: when a skill's description triggers, its full content gets concatenated. ~100–1000 tokens per skill.</li>
        <li><strong>Conversation history</strong>: your messages and Claude's responses. Grows linearly with turns.</li>
        <li><strong>Tool results</strong>: almost always the biggest line item:
          <ul>
            <li>Read of a 1000-line file ≈ 5–10K tokens</li>
            <li>A noisy bash command (logs, builds) → 10–100K tokens</li>
            <li>A web fetch → 5–50K tokens depending on the page</li>
            <li>An image attachment ≈ 1–2K tokens</li>
          </ul>
        </li>
      </ul>

One careless <code>cat huge-log.txt</code>, one verbose <code>npm install</code>, one fetched page, half your window is gone.

### Assembly: how the system prompt gets built {#assembly} {toc:System prompt assembly}

Every API call, the harness concatenates many sources into a single system message.

      <div class="assembly" role="figure" aria-label="System prompt assembly">
        <div class="assembly-sources">
          <div class="assembly-source">Vendor preamble<span class="sub">Claude Code's built-in instructions</span></div>
          <div class="assembly-source"><code>CLAUDE.md</code><span class="sub">walked up the directory tree</span></div>
          <div class="assembly-source">Memory files<span class="sub">MEMORY.md + auto-memory entries</span></div>
          <div class="assembly-source">Available subagents<span class="sub">names + descriptions for delegation</span></div>
          <div class="assembly-source">Loaded skills<span class="sub">skills whose triggers match</span></div>
          <div class="assembly-source">Tool definitions<span class="sub">built-in + MCP</span></div>
        </div>
        <div class="assembly-arrow" aria-hidden="true">⟶</div>
        <div class="assembly-output">
          <div class="assembly-output-title">System message</div>
          <div class="assembly-output-sub">sent on every API call</div>
        </div>
      </div>

      <p class="caption">Every API call, the harness glues these sources together into one system message. CLAUDE.md changes apply on the next turn, not the next session.</p>

Two consequences worth banking:

      <ol>
        <li><strong>CLAUDE.md changes take effect on the next turn</strong>: not the next session. It's re-loaded and re-concatenated every call.</li>
        <li><strong>The full system prompt is re-sent every turn.</strong> Nothing is stored on Anthropic's side persistently. Which is why the next piece matters.</li>
      </ol>

### The accelerator: prompt cache {#prompt-cache} {toc:The prompt cache}

Without optimization, every turn would reprocess the entire system prompt + history from scratch. The prompt cache fixes this:

      <ul>
        <li>Anthropic's inference servers cache <em>intermediate computations</em> (attention key/value states) for the <strong>prefix</strong> of your messages.</li>
        <li>When you re-POST the same prefix on the next turn, the servers reuse the cached work and only compute the <em>new</em> part.</li>
        <li>Cache hits are ~10x cheaper and noticeably faster than cold processing.</li>
      </ul>

      <div class="cache-seq" role="figure" aria-label="Prompt cache prefix mechanics">
        <div class="cache-msg cache-cached">System<br>prompt</div>
        <div class="cache-msg cache-cached">msg 1</div>
        <div class="cache-msg cache-cached">asst 1</div>
        <div class="cache-msg cache-cached">msg 2</div>
        <div class="cache-msg cache-cached">asst 2</div>
        <div class="cache-msg cache-new">new msg</div>
      </div>

      <div class="cache-legend">
        <span><span class="cache-dot cache-dot-cached"></span> Cached prefix, server reuses prior computation</span>
        <span><span class="cache-dot cache-dot-new"></span> New tail, full processing</span>
      </div>

      <p class="caption">The cache works on prefixes. Each turn extends the prefix; only the new tail is full-price. Appending at the end keeps the cache warm; changing anything early invalidates everything after.</p>

Two practical implications:

      <ol>
        <li><strong>Cache TTL is ~5 minutes by default.</strong> Pause longer and the next turn is full-price.</li>
        <li><strong>Order matters because cache is prefix-based.</strong> Append at the end → cache warm. Change something early → cache busted from that point on.</li>
      </ol>

### What this means for "context fills up too fast" {#implications} {toc:Knobs for the frustration}

After running out of context too many times, these are the moves I learned:

      <ul>
        <li><strong>Tool results are usually the culprit.</strong> Be deliberate about what you Read, Bash, or Fetch. A big file or noisy command eats tens of thousands of tokens in one shot.</li>
        <li><strong>Subagents save your main context.</strong> Letting an Explore agent read 50 files in <em>its</em> window and return a 200-word summary means your main thread pays for 200 words, not 50 files. Massive leverage when used right.</li>
        <li><strong>Memory and CLAUDE.md beat re-explanation.</strong> Durable facts get re-injected automatically every session, so they don't fight for chat-history budget.</li>
        <li><strong><code>/clear</code> between phases.</strong> Memory and CLAUDE.md still load, so durable context survives.</li>
        <li><strong>Cache awareness.</strong> Sessions active within 5-minute gaps stay cheap. Long pauses cost.</li>
        <li><strong>Bigger window ≠ free space.</strong> Opus 4.7's 1M context is "more room" not "free room." You still pay per token. Pick the window to fit the workload, not the biggest by default.</li>
      </ul>

## Tools and tool calls {#tools} {toc:Tools and tool calls}

The model doesn't <em>do</em> anything. It only <em>recommends actions</em>. Tool calls are how those recommendations become real work.

### What a tool definition actually is {#tool-definition} {toc:What a tool definition is}

A tool definition is a JSON schema with three parts: a <strong>name</strong>, a <strong>description</strong>, and an <strong>input schema</strong>:

<pre><code>{
  "name": "Read",
  "description": "Reads a file from the filesystem and returns its contents with line numbers, up to 2000 lines...",
  "input_schema": {
    "type": "object",
    "properties": {
      "file_path": { "type": "string", "description": "The absolute path..." }
    },
    "required": ["file_path"]
  }
}</code></pre>

The harness sends a list of these to the API on every turn alongside the messages. <strong>The model sees only this</strong>: name, description, and parameter schema. It does <em>not</em> see the implementation. It doesn't know <code>Read</code> opens a file handle and slurps content. All it knows is what the description says it does.

The load-bearing insight: <strong>a tool's description is a prompt to the model</strong>, not documentation for humans. Vague description → the model can't tell when to reach for it. Specific, action-verb-led description → clear matching.

### The tool call lifecycle {#lifecycle} {toc:The tool call lifecycle}

      <div class="lifecycle" role="figure" aria-label="Tool call lifecycle">
        <div class="lc-step lc-model">
          <div class="lc-num">1</div>
          <div>
            <div class="lc-title">Model emits tool_use block</div>
            <div class="lc-sub">Structured intent: { name, input }</div>
          </div>
        </div>
        <div class="lc-arrow" aria-hidden="true">↓</div>
        <div class="lc-step lc-harness">
          <div class="lc-num">2</div>
          <div>
            <div class="lc-title">Harness intercepts</div>
            <div class="lc-sub">Looks up the tool in its registry</div>
          </div>
        </div>
        <div class="lc-arrow" aria-hidden="true">↓</div>
        <div class="lc-branch">
          <div class="lc-branch-q">Permission required?</div>
          <div class="lc-branch-paths">
            <div class="lc-branch-path">
              <div class="lc-branch-label">Yes</div>
              <div class="lc-mini-step">Ask user (blocking)</div>
              <div class="lc-mini-step">If approved → continue</div>
            </div>
            <div class="lc-branch-path">
              <div class="lc-branch-label">No (pre-approved)</div>
              <div class="lc-mini-step">Skip → execute directly</div>
            </div>
          </div>
        </div>
        <div class="lc-arrow" aria-hidden="true">↓</div>
        <div class="lc-step lc-harness">
          <div class="lc-num">3</div>
          <div>
            <div class="lc-title">Execute the tool</div>
            <div class="lc-sub">Subprocess, API call, file I/O, whatever the tool actually does</div>
          </div>
        </div>
        <div class="lc-arrow" aria-hidden="true">↓</div>
        <div class="lc-step lc-harness">
          <div class="lc-num">4</div>
          <div>
            <div class="lc-title">Package tool_result</div>
            <div class="lc-sub">{ content } on success, or { error: '...' } on failure</div>
          </div>
        </div>
        <div class="lc-arrow" aria-hidden="true">↓</div>
        <div class="lc-step lc-harness">
          <div class="lc-num">5</div>
          <div>
            <div class="lc-title">Append to message list, re-POST</div>
            <div class="lc-sub">Full conversation re-sent on next API call</div>
          </div>
        </div>
        <div class="lc-arrow" aria-hidden="true">↓</div>
        <div class="lc-step lc-model">
          <div class="lc-num">6</div>
          <div>
            <div class="lc-title">Model sees result, continues</div>
            <div class="lc-sub">May emit text, call another tool, or finish the turn</div>
          </div>
        </div>
      </div>

      <p class="caption">The model recommends; the harness executes. The model never touches your filesystem; it just emits structured intent the harness translates into action.</p>

### How the model picks a tool {#tool-selection} {toc:How the model picks}

When you send a message, the model sees: system prompt + conversation history + tool definitions + your new message. Three things shape the choice:

      <ol>
        <li><strong>Description match.</strong> The model compares your intent against each tool's described purpose. Specific descriptions match better than abstract ones.</li>
        <li><strong>Input schema fit.</strong> If your request maps cleanly onto one tool's required parameters, that biases the model toward it.</li>
        <li><strong>Context examples.</strong> If the conversation has used <code>Bash</code> 10 times for similar tasks, the model is more likely to use <code>Bash</code> again. Patterns reinforce themselves.</li>
      </ol>

"Picks the wrong tool" is almost always one of:

      <ul>
        <li>A description too vague to disambiguate</li>
        <li>Two tools with overlapping descriptions</li>
        <li>A tool the model doesn't realize is available (description doesn't match your phrasing)</li>
      </ul>

The fix in all three cases: <strong>rewrite the description</strong>.

### Parallel tool calls {#parallel-tools} {toc:Parallel tool calls}

Modern Claude can recommend multiple tool calls in a single response. The model decides which calls are independent and emits them as a batch. The harness executes concurrently and returns all results before the next inference step.

      <div class="ps-compare" role="figure" aria-label="Parallel vs serial tool calls comparison">
        <div class="ps-col ps-serial">
          <div class="ps-col-header">
            <h4>Serial — 3 round-trips</h4>
            <div class="ps-col-cost">4 model calls · 3 sequential executions</div>
          </div>
          <div class="ps-timeline">
            <div class="ps-step ps-model">Model call 1<span>asks for tool A</span></div>
            <div class="ps-step ps-tool">Tool A executes</div>
            <div class="ps-step ps-model">Model call 2<span>asks for tool B</span></div>
            <div class="ps-step ps-tool">Tool B executes</div>
            <div class="ps-step ps-model">Model call 3<span>asks for tool C</span></div>
            <div class="ps-step ps-tool">Tool C executes</div>
            <div class="ps-step ps-model">Model call 4<span>final response</span></div>
          </div>
        </div>
        <div class="ps-col ps-parallel">
          <div class="ps-col-header">
            <h4>Parallel — 1 round-trip</h4>
            <div class="ps-col-cost">2 model calls · 3 concurrent executions</div>
          </div>
          <div class="ps-timeline">
            <div class="ps-step ps-model">Model call 1<span>emits 3 tool_use blocks</span></div>
            <div class="ps-parallel-row">
              <div class="ps-step ps-tool">Tool A</div>
              <div class="ps-step ps-tool">Tool B</div>
              <div class="ps-step ps-tool">Tool C</div>
            </div>
            <div class="ps-step ps-model">Model call 2<span>final response</span></div>
          </div>
        </div>
      </div>

      <p class="caption">Serial costs 4 model calls and sequential tool execution. Parallel costs 2 model calls and concurrent execution. The round-trip and wall-clock win compounds with more tools.</p>

The model has to <em>recognize</em> independence. "Read A, then based on it, read B" can't parallelize; there's a dependency. "Read A, B, and C" can. You can nudge by phrasing requests as "in parallel" or "independently"; the model picks up the cue.

### When tools fail {#tool-errors} {toc:When tools fail}

A tool call can fail: file not found, command exits non-zero, network error. The harness packages the failure into the tool_result with an error indicator. The model gets that error on the next turn and decides what to do: retry, switch tools, or ask you.

<strong>The error message you write into a tool's failure path matters.</strong> A tool result of <code>"error: failed"</code> tells the model almost nothing. A tool result of <code>"error: file not found at /path/X. Check with ls"</code> gives the model concrete next steps.

This is why MCP servers and custom tools you build need <em>good error surfaces</em>. The harness can't help if the tool itself returns junk in its error message.

### Descriptions as the discovery surface {#discovery-surface} {toc:Descriptions as discovery}

The connection across the agent stack: <strong>the model only knows what your descriptions tell it.</strong> This applies to:

      <ul>
        <li><strong>Built-in tools</strong>: Anthropic writes them; you can't change. (<code>Read</code>, <code>Edit</code>, <code>Bash</code>, <code>Glob</code>, <code>Grep</code>, <code>WebFetch</code>.)</li>
        <li><strong>MCP tools</strong>: you write the server; you control the description. Good descriptions → the model uses your tool. Vague descriptions → it gets ignored.</li>
        <li><strong>Skills</strong>: same principle. The skill description triggers loading. (More in the next section.)</li>
        <li><strong>Custom subagents</strong>: your subagent description is how the parent decides when to delegate.</li>
      </ul>

The "I built a thing and the model never uses it" problem is almost always a description problem.

## Subagents {#subagents} {toc:Subagents}

A subagent is the same Claude model running in a fresh sandbox (its own context window, its own system prompt, its own toolbelt), spawned by the parent to handle a delegated piece of work. The parent pays only for the <em>summary</em> the subagent returns, not the work the subagent did.

This is one of the highest-leverage productivity tools in Claude Code, and it's underused because the model rarely volunteers. You usually have to know when to ask.

### What a subagent actually is {#subagent-what} {toc:What a subagent is}

Mechanically, a subagent is:

      <ul>
        <li>A fresh Claude inference loop, started by the harness in a child execution context</li>
        <li>Its own context window (empty at start except for the subagent's system prompt + your task prompt)</li>
        <li>Its own toolbelt (often restricted, e.g., <code>Explore</code> has only read tools)</li>
        <li>A single return value: one string the parent gets back as the result of a <code>Task</code> tool call</li>
      </ul>

The parent doesn't see the subagent's intermediate turns. It only sees the final summary. From the parent's perspective, a subagent call is just another tool call, one that happens to take longer and return prose instead of file contents.

### The delegation handoff {#subagent-handoff} {toc:The delegation handoff}

When the parent decides to delegate:

      <ol>
        <li>Parent emits a <code>Task</code> tool_use block: <code>{ subagent_type, description, prompt }</code></li>
        <li>Harness recognizes <code>Task</code>, starts the child Claude with the named subagent type</li>
        <li>Child loads its own system prompt (subagent definition + the prompt passed in)</li>
        <li>Child runs its own loop, tool calls, file reads, reasoning, using <em>its</em> context window</li>
        <li>Child returns a single string (its final message) as the tool_result</li>
        <li>Parent gets that string, integrates it, continues</li>
      </ol>

      <div class="subagents" role="figure" aria-label="Subagent topology">
        <div class="sa-parent">
          <div class="sa-parent-label">Parent Claude</div>
          <div class="sa-parent-sub">Main conversation, you talk to this thread</div>
        </div>
        <div class="sa-flow-label">↓ Task tool call · ↑ summary string</div>
        <div class="sa-children">
          <div class="sa-child">
            <div class="sa-child-name">Explore (built-in)</div>
            <div class="sa-child-task">"Find references to X"</div>
            <div class="sa-child-context">fresh context · 50 file reads</div>
            <div class="sa-child-return">↑ ~30 tokens back</div>
          </div>
          <div class="sa-child">
            <div class="sa-child-name">custom subagent</div>
            <div class="sa-child-task">"Review this draft"</div>
            <div class="sa-child-context">fresh context · reads draft + refs</div>
            <div class="sa-child-return">↑ ~100 tokens back</div>
          </div>
          <div class="sa-child">
            <div class="sa-child-name">custom subagent</div>
            <div class="sa-child-task">"Audit references"</div>
            <div class="sa-child-context">fresh context · grep + glob</div>
            <div class="sa-child-return">↑ ~50 tokens back</div>
          </div>
        </div>
      </div>

      <p class="caption">The parent's context stays clean; each child's context absorbs its own work and evaporates after the call returns. Only the summary survives.</p>

### Why isolation matters: the token economics {#subagent-economics} {toc:Token economics}

The moment subagents clicked for me: a child's context evaporates after the call returns. That asymmetry is where the leverage lives.

      <div class="econ" role="figure" aria-label="Token economics comparison">
        <div class="econ-col econ-without">
          <div class="econ-col-header">
            <h4>Without subagent</h4>
            <div class="econ-tagline">Parent reads 50 files itself</div>
          </div>
          <div class="econ-bar-label">Parent context after the work</div>
          <div class="econ-bar">
            <div class="econ-bar-fill" style="width: 95%">~100K tokens</div>
          </div>
          <div class="econ-note">All 50 file contents now live in the parent's conversation history. Heavy. Autocompact looms.</div>
        </div>
        <div class="econ-col econ-with">
          <div class="econ-col-header">
            <h4>With Explore subagent</h4>
            <div class="econ-tagline">Subagent reads 50 files in its sandbox</div>
          </div>
          <div class="econ-bar-label">Parent context after the work</div>
          <div class="econ-bar">
            <div class="econ-bar-fill" style="width: 3%">+30</div>
          </div>
          <div class="econ-note">Only the summary returns to the parent. The subagent's context (which absorbed all 50 file reads) evaporates after the call.</div>
        </div>
      </div>

      <p class="caption">Without subagent: 50 file contents live in the parent's conversation forever. With subagent: only the summary survives; the child's context evaporates.</p>

A worked example:

      <ul>
        <li><strong>Without subagent</strong>: Parent reads 50 files to find a pattern. Parent's context now contains 50 file contents ≈ 50–200K tokens. Heavy. Autocompact looms.</li>
        <li><strong>With subagent</strong>: Parent asks <code>Explore</code>: "Find all references to X." <code>Explore</code> reads the 50 files in <em>its</em> context, returns: <em>"X is referenced in <code>src/auth.ts:42</code>, <code>src/api.ts:118</code>, and <code>src/utils/jwt.ts:7</code>. The auth.ts version is canonical."</em> Parent's context grows by ~30 tokens.</li>
      </ul>

The savings compound when:

      <ul>
        <li>The work involves many file reads (research, audits, codebase exploration)</li>
        <li>The work involves heavy <code>WebFetch</code>es</li>
        <li>The work has many branching tool calls but a small final answer</li>
      </ul>

This is also why "I ran out of context" is often solvable structurally, by delegating the <em>biggest</em> reads to subagents instead of pulling them into the main thread.

### Reading vs. writing subagents {#subagent-flavors} {toc:Reading vs. writing}

Two flavors that matter:

      <ul>
        <li><strong>Read-only subagents</strong> (like <code>Explore</code>): restricted to read tools. Safe to spawn liberally for research. Can't modify state. Pattern: <em>"Go look at a bunch of stuff and tell me what you found."</em></li>
        <li><strong>General-purpose subagents</strong>: full toolbelt, can edit files, run commands, modify state. Powerful but riskier. Pattern: <em>"Do this whole subtask and report back."</em></li>
      </ul>

Most <em>context-saving</em> leverage comes from read-only subagents. Most <em>autonomy</em> leverage comes from general-purpose subagents.

### Custom subagents {#subagent-custom} {toc:Custom subagents}

Like skills, you can define your own. A subagent definition lives in <code>.claude/agents/&lt;name&gt;.md</code> and includes:

      <ul>
        <li><strong>A name</strong> (the slug)</li>
        <li><strong>A description</strong> (the discovery surface, same principle as tools and skills)</li>
        <li><strong>A model</strong> (Haiku for cheap research, Sonnet for complex work, Opus for the hardest)</li>
        <li><strong>A toolbelt</strong> (which tools the subagent can use, restrict aggressively)</li>
        <li><strong>A system prompt</strong> (custom behavior instructions)</li>
      </ul>

The parent sees the subagent's description and decides when to delegate. As with tools, <strong>the description is the discovery surface</strong>. Vague description means the parent never invokes it.

### When NOT to use subagents {#subagent-anti} {toc:When NOT to delegate}

Subagents have overhead: spawning a child is a real round trip. They're the wrong tool for:

      <ul>
        <li>Short, fast tasks (don't pay overhead for a 3-token answer)</li>
        <li>Tasks where the parent needs the intermediate context in its thread (delegation hides it)</li>
        <li>Iterative back-and-forth (each turn is a new spawn, expensive)</li>
        <li>Tasks where you want to <em>learn</em> the steps (you only see the summary)</li>
      </ul>

The leverage rule: <strong>delegate when the work is read-heavy and the answer is short.</strong> That's the sweet spot.

## Skills {#skills} {toc:Skills}

A skill is <em>procedural knowledge</em> the model can load into its context on demand. Unlike a tool (a callable function) or a subagent (a separate Claude process), a skill is <strong>a text artifact that gets injected into the parent's system prompt when its description matches</strong>. The model then reads the skill body and follows the instructions inline.

This is where the "picks the wrong skill" frustration lives, and almost always, the fix is the same as for tools and subagents: <strong>the description</strong>.

### What a skill actually is {#skill-what} {toc:What a skill is}

Mechanically, a skill is a markdown file at <code>.claude/skills/&lt;skill-name&gt;/SKILL.md</code> with YAML frontmatter:

<pre><code>---
name: my-skill
description: Use when [trigger phrases]. Does [what it does].
---

[Body content with instructions, examples, reference material]</code></pre>

That's the whole thing. Two fields in the frontmatter (<code>name</code>, <code>description</code>), plus a body. The body can be a paragraph or a full procedure with sub-headers, code snippets, references.

A skill can also bundle supplementary files alongside <code>SKILL.md</code>: scripts, templates, examples. These don't auto-load; they're referenced from the body and read on demand.

      <div class="skill-anatomy" role="figure" aria-label="Skill file structure">
        <div class="sa-dir-row">
          <span class="sa-icon" aria-hidden="true">▾</span>
          <code>.claude/skills/&lt;skill-name&gt;/</code>
        </div>
        <div class="sa-tree">
          <div class="sa-file sa-file-skill">
            <div class="sa-file-name"><span class="sa-tree-line" aria-hidden="true">├</span> <code>SKILL.md</code></div>
            <div class="sa-file-inner">
              <div class="sa-section sa-section-frontmatter">
                <div class="sa-section-label">frontmatter</div>
                <div class="sa-section-content"><code>name</code> + <code>description</code></div>
                <div class="sa-section-badge">always loaded · ~150 tokens</div>
              </div>
              <div class="sa-section sa-section-body">
                <div class="sa-section-label">body</div>
                <div class="sa-section-content">procedure, examples, references</div>
                <div class="sa-section-badge">loaded on demand · ~500-3000 tokens</div>
              </div>
            </div>
          </div>
          <div class="sa-file sa-file-bundled">
            <div class="sa-file-name"><span class="sa-tree-line" aria-hidden="true">├</span> <code>scripts.sh</code></div>
            <div class="sa-file-note">referenced from body · read when needed</div>
          </div>
          <div class="sa-file sa-file-bundled">
            <div class="sa-file-name"><span class="sa-tree-line" aria-hidden="true">└</span> <code>reference/</code></div>
            <div class="sa-file-note">supplementary material · read on demand</div>
          </div>
        </div>
      </div>

      <p class="caption">Skill anatomy. Frontmatter is always loaded (cheap); body loads on demand when the description matches. Bundled files are referenced from the body and read only when the procedure calls for them.</p>

### Progressive disclosure — the load-bearing mechanic {#progressive-disclosure} {toc:Progressive disclosure}

This is the most important thing to internalize about skills, and the source of most "why didn't my skill trigger?" confusion.

Skills use <strong>two-phase loading</strong>:

<strong>Phase 1 (always)</strong>: For every installed skill, only the <strong>name + description</strong> are loaded into the system prompt. The body is NOT loaded. The harness puts a compact list, descriptions are typically 100–200 tokens each. Even 20 skills cost ~3K tokens.

<strong>Phase 2 (on demand)</strong>: When the model decides a skill is relevant (based on the request and the descriptions it sees), it calls a tool to <strong>load that skill's full content</strong> into context. Only then does the body become available.

      <div class="pdisclose" role="figure" aria-label="Progressive disclosure of skill content">
        <div class="pd-phase pd-phase-1">
          <div class="pd-phase-header">
            <span class="pd-phase-label">Phase 1</span>
            <span class="pd-phase-title">Always loaded, cheap</span>
          </div>
          <ul class="pd-desc-list">
            <li class="pd-desc"><code>diagrams</code><span class="pd-desc-text">use when creating, editing, reviewing diagrams…</span></li>
            <li class="pd-desc"><code>publication-safety</code><span class="pd-desc-text">use when preparing repo for public sharing…</span></li>
            <li class="pd-desc"><code>verify</code><span class="pd-desc-text">verify changes by running the app…</span></li>
          </ul>
          <div class="pd-phase-cost">~150 tokens each · ~500 total for 3 skills</div>
        </div>
        <div class="pd-trigger">
          <div class="pd-user">User: <em>"draw a diagram of the system"</em></div>
          <div class="pd-match-arrow" aria-hidden="true">↓</div>
          <div class="pd-match-label">Model matches <code>diagrams</code> description → triggers body load</div>
        </div>
        <div class="pd-phase pd-phase-2">
          <div class="pd-phase-header">
            <span class="pd-phase-label">Phase 2</span>
            <span class="pd-phase-title">On demand, full body</span>
          </div>
          <div class="pd-body">
            <div class="pd-body-header"><code>diagrams</code> body now loaded</div>
            <div class="pd-body-text">Mermaid syntax, color palette, anti-patterns, examples, render commands…</div>
          </div>
          <div class="pd-phase-cost">+1500 tokens (just for the matched skill)</div>
        </div>
      </div>

      <p class="caption">Progressive disclosure. Phase 1 is cheap: just descriptions. Phase 2 loads the full body only when the description matches what the user asked for. This is why descriptions matter more than skill content for triggering.</p>

This is why descriptions matter so much. The model is doing pattern matching between <em>what the user asked</em> and <em>what each skill's description says</em>. If the description doesn't surface naturally from the user's phrasing, the skill won't load, even if its body would handle the request perfectly.

### Why skills don't trigger when you expect {#skill-triggering} {toc:Why skills don't trigger}

Almost always one of these:

      <ol>
        <li><strong>Description uses different language than the user.</strong> User says "make a chart"; description says "produces visualizations." Semantic matching is good but not magic.</li>
        <li><strong>Description is too vague.</strong> "Handles various data tasks" doesn't trigger on anything specific.</li>
        <li><strong>Description doesn't include trigger phrases.</strong> Action-verb-led, scenario-led descriptions trigger better than abstract definitions.</li>
        <li><strong>Competing skills with overlapping descriptions.</strong> The model picks one, maybe the wrong one.</li>
        <li><strong>Skill is out of scope.</strong> A project skill only loads when working in that project; user skills load everywhere.</li>
      </ol>

Diagnostic: <strong>read the description like the model would.</strong> Does it specifically tell the model when to use it? Does it use the language users would use?

### Description engineering {#description-engineering} {toc:Description engineering}

Good description structure:

<pre><code>description: Use when: [trigger scenarios]. The skill [what it actually does].
[Optional: distinguishing factors vs related skills]</code></pre>

A well-engineered example (the <code>diagrams</code> skill):

<pre><code>description: Use when: creating, editing, or reviewing technical diagrams;
the user mentions diagram, mermaid, visualize, topology, flow chart,
pipeline picture, or asks to draw a system, a data path, or a cold/warm path.</code></pre>

What makes this work:

      <ul>
        <li>Lists multiple trigger words (<code>diagram, mermaid, visualize, topology…</code>)</li>
        <li>Includes scenario phrases ("asks to draw a system")</li>
        <li>Front-loads the trigger conditions ("Use when:") so the model can pattern-match fast</li>
        <li>Doesn't bury triggers in prose</li>
      </ul>

### Bundled resources — when skills get bigger {#bundled-resources} {toc:Bundled resources}

Skills can come with companion files in the same directory:

<pre><code>.claude/skills/aihomelab-lustre-cluster/
├── SKILL.md
├── lustre-bringup.sh
└── reference/
    └── lustre-modules-checklist.md</code></pre>

The body of <code>SKILL.md</code> references these. The model reads <code>SKILL.md</code> and follows the procedure, reaching for the companion files only when the procedure calls for them.

This keeps the loaded body lean: only the procedure loads, not the supporting material.

### Skill scope: user / project / built-in {#skill-scope} {toc:Skill scope}

Three scopes, each with implications for <em>when</em> a skill is available:

      <ul>
        <li><strong>Project skills</strong>: <code>&lt;project-root&gt;/.claude/skills/</code>. Load only when working in that project. Good for project-specific procedures.</li>
        <li><strong>User skills</strong>: <code>~/.claude/skills/</code>. Load in every project on your machine. Good for cross-cutting procedures (diagrams, publication-safety).</li>
        <li><strong>Built-in skills</strong>: ship with Claude Code, always available (<code>verify</code>, <code>simplify</code>, <code>init</code>, etc.).</li>
      </ul>

Scope matters because triggering happens against <em>currently loaded</em> descriptions. A user skill is invisible when working from a machine that doesn't have it installed.

## MCP {#mcp} {toc:MCP}

MCP (Model Context Protocol) is the standardized way to <strong>add new tools</strong> to any harness. MCP servers expose tools that the harness routes the model's calls to. This section goes a layer deeper: the protocol, the deferred-tools optimization, and when you'd actually build one.

### What MCP actually is {#mcp-what} {toc:What MCP is}

MCP is an open protocol that defines:

      <ul>
        <li><strong>A standardized way for a "server" (your code) to expose tools</strong>: each with a name, description, input schema (same shape as built-in tools)</li>
        <li><strong>A standardized way for a "client" (the harness) to discover and invoke those tools</strong> over a transport (stdio for local processes, HTTP for remote services)</li>
        <li><strong>Lifecycle hooks</strong>: initialization, capability negotiation, resource listing, prompt templates</li>
      </ul>

For the harness, an MCP tool is <strong>indistinguishable from a built-in tool</strong>: same <code>tool_use</code> structure, same <code>tool_result</code> flow. The harness just routes the call to the right MCP server instead of executing locally.

For your code (the MCP server side), you implement a small program that:

      <ol>
        <li>Speaks the MCP protocol on stdio or HTTP</li>
        <li>Declares what tools it offers (name + description + schema)</li>
        <li>Receives tool invocations and returns results</li>
      </ol>

That's the whole contract. It works the same way across Claude Code, Cursor, Cline, custom SDK harnesses, anything that implements an MCP client.

      <div class="mcp-topo" role="figure" aria-label="MCP architecture topology">
        <div class="mcp-model">
          <div class="mcp-model-label">Model</div>
          <div class="mcp-model-sub">sees one unified tool list, built-in + MCP indistinguishable</div>
        </div>
        <div class="mcp-arrow-pair" aria-hidden="true">
          <span>↑ tool list</span>
          <span>↓ tool calls</span>
        </div>
        <div class="mcp-harness">
          <div class="mcp-harness-header">Harness (Claude Code)</div>
          <div class="mcp-harness-inner">
            <div class="mcp-builtin">
              <div class="mcp-builtin-label">Built-in tools</div>
              <div class="mcp-builtin-tools">Read · Edit · Bash · Glob · Grep · WebFetch</div>
            </div>
            <div class="mcp-client">
              <div class="mcp-client-label">MCP client</div>
              <div class="mcp-client-sub">routes calls to MCP servers</div>
            </div>
          </div>
        </div>
        <div class="mcp-arrow-pair" aria-hidden="true">
          <span>↑ tools exposed</span>
          <span>↓ stdio / HTTPS</span>
        </div>
        <div class="mcp-servers">
          <div class="mcp-server mcp-server-stdio">
            <div class="mcp-server-header">
              <span class="mcp-server-name">computer-use</span>
              <span class="mcp-server-transport">stdio · local</span>
            </div>
            <div class="mcp-server-tools">screenshot · click · type · scroll · 22 more</div>
          </div>
          <div class="mcp-server mcp-server-http">
            <div class="mcp-server-header">
              <span class="mcp-server-name">company-jira</span>
              <span class="mcp-server-transport">HTTP · remote</span>
            </div>
            <div class="mcp-server-tools">jira_search · jira_create · jira_update · …</div>
          </div>
        </div>
      </div>

      <p class="caption">MCP architecture. From the model's perspective, built-in tools and MCP tools look identical: same call shape. The harness routes calls to the right server using stdio for local servers and HTTP for remote ones.</p>

### Why MCP exists {#mcp-why} {toc:Why MCP exists}

Before MCP, every harness had its own way of adding extension tools. Cursor had Cursor's way; Claude Code had Anthropic's way; custom SDK code had to roll its own. If you wrote a "talks to GitHub" integration for one harness, you'd have to rewrite it for another.

MCP standardizes the contract. Now:

      <ul>
        <li>You write one MCP server for "talk to GitHub"</li>
        <li>It works in Claude Code, Cursor, any MCP-aware harness</li>
        <li>You don't rewrite when you switch tools</li>
        <li>The community can share servers: github-mcp, slack-mcp, postgres-mcp, filesystem-mcp</li>
      </ul>

This is the agent-tool equivalent of <strong>LSP</strong> (Language Server Protocol) for IDEs: same standardization story.

### Transports: stdio vs HTTP {#mcp-transports} {toc:Transports}

Two ways the harness connects to an MCP server:

      <ul>
        <li><strong>stdio (local)</strong>: harness spawns the MCP server as a child process and pipes messages over stdin/stdout. Fast, secure, no network. Used for tools that need local access (filesystem, local services, computer-use).</li>
        <li><strong>HTTP (remote)</strong>: harness connects to an MCP server over the network. Used for SaaS integrations or shared company services. Authentication happens at the HTTP layer.</li>
      </ul>

You configure each MCP server in your settings: a command + args for stdio, a URL for HTTP.

### Deferred tools — same progressive-disclosure trick {#mcp-deferred} {toc:Deferred tools}

Some MCP servers expose <em>many</em> tools. A <code>computer-use</code> server has 26 tools. If every MCP tool's full schema were loaded into every conversation, the system prompt would balloon.

The solution: <strong>deferred tools</strong>. The harness only loads the <em>names</em> of MCP tools into the always-available list, not the full schemas. When the model wants to use one, it first calls a <code>ToolSearch</code> to fetch the actual schema, then calls the tool.

      <div class="dtools" role="figure" aria-label="Deferred tools loading mechanic">
        <div class="dt-phase dt-phase-1">
          <div class="dt-phase-header">
            <span class="dt-phase-label">Phase 1</span>
            <span class="dt-phase-title">Always loaded, names only</span>
          </div>
          <ul class="dt-name-list">
            <li><code>mcp__computer-use__screenshot</code></li>
            <li><code>mcp__computer-use__click</code></li>
            <li><code>mcp__computer-use__type</code></li>
            <li class="dt-more">… 23 more deferred names</li>
          </ul>
          <div class="dt-phase-cost">~5 tokens per name · ~130 tokens for 26 tools</div>
        </div>
        <div class="dt-trigger">
          <div class="dt-step">
            <span class="dt-step-num">1</span>
            <span>Model wants to use <code>click</code>, calls <code>ToolSearch("click")</code></span>
          </div>
          <div class="dt-step">
            <span class="dt-step-num">2</span>
            <span>Harness returns the full schema for that tool</span>
          </div>
          <div class="dt-step">
            <span class="dt-step-num">3</span>
            <span>Model now has the schema, calls the tool with proper arguments</span>
          </div>
        </div>
        <div class="dt-phase dt-phase-2">
          <div class="dt-phase-header">
            <span class="dt-phase-label">Phase 2</span>
            <span class="dt-phase-title">Schema fetched on demand</span>
          </div>
          <div class="dt-schema">
            <div class="dt-schema-header">click full schema (fetched)</div>
            <div class="dt-schema-content">params: { x: int, y: int, button: enum }<br>… full description and constraints</div>
          </div>
          <div class="dt-phase-cost">+~150 tokens (just for the one used tool)</div>
        </div>
      </div>

      <p class="caption">Deferred tools: same progressive-disclosure pattern as skills. Names are cheap to keep around (~5 tokens each); full schemas load only on demand via ToolSearch.</p>

This is why having a big MCP server like <code>computer-use</code> connected doesn't blow up your context budget.

### When to build an MCP server {#mcp-when-build} {toc:When to build one}

The question to ask: <strong>does Claude need access to a capability the built-in tools can't provide?</strong>

Good MCP server candidates:

      <ul>
        <li>Talk to your company's internal API (Jira, Confluence, internal services)</li>
        <li>Query your database with proper authentication</li>
        <li>Drive a specific external tool (Figma, Linear, your CI system)</li>
        <li>Wrap a complex CLI tool with structured I/O instead of raw shell parsing</li>
      </ul>

Not-MCP-server candidates (often there's an easier way):

      <ul>
        <li>"Run a shell command" → <code>Bash</code> already does this</li>
        <li>"Read a file" → <code>Read</code> already does this</li>
        <li>"Search the web" → <code>WebFetch</code> for one page, or an existing search MCP server</li>
        <li>"Write a procedure the model should follow" → that's a <strong>skill</strong>, not an MCP server</li>
      </ul>

### Ecosystem {#mcp-ecosystem} {toc:Ecosystem}

There's a growing ecosystem of community MCP servers: GitHub, Slack, Postgres, filesystem, browser automation, search, and many more. Most are open source. You install them like any other dependency and configure your harness to connect.

### The bottom line {#mcp-bottom-line} {toc:The bottom line}

MCP is the extension mechanism for <strong>adding capabilities</strong> Claude doesn't otherwise have. It's a protocol, not a feature.

      <ul>
        <li>"Claude needs to be able to do X" where X is a new external interaction → <strong>MCP</strong></li>
        <li>"Claude needs to follow this procedure" → <strong>skill</strong></li>
        <li>"Claude needs to delegate this isolated work and report back" → <strong>subagent</strong></li>
      </ul>

We'll formalize the full decision tree in the next section.

## Picking the right primitive {#picking-primitive} {toc:Picking the right primitive}

You now have four ways to shape what Claude can do:

      <ul>
        <li><strong>Tool</strong>: a callable function the model invokes</li>
        <li><strong>Skill</strong>: procedural knowledge the model loads into context when triggered</li>
        <li><strong>Subagent</strong>: a fresh Claude process spawned to do isolated work</li>
        <li><strong>MCP server</strong>: protocol for exposing new tools (a tool factory, essentially)</li>
      </ul>

They look similar from a distance. They're not. Each occupies a specific role, and choosing the wrong one is the source of most "I built this and it doesn't work" frustration.

### Comparison at a glance {#primitive-comparison} {toc:Comparison at a glance}

      <div class="matrix-wrap">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Tool</th>
              <th>Skill</th>
              <th>Subagent</th>
              <th>MCP server</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>What it is</th>
              <td>Function the model calls</td>
              <td>Text injected into parent's prompt</td>
              <td>Fresh Claude with isolated context</td>
              <td>Protocol for exposing tools</td>
            </tr>
            <tr>
              <th>Where it lives</th>
              <td>Harness (built-in) or via MCP</td>
              <td><code>.claude/skills/</code></td>
              <td><code>.claude/agents/</code></td>
              <td>Separate process or service</td>
            </tr>
            <tr>
              <th>What it returns</th>
              <td>Data (<code>tool_result</code>)</td>
              <td>Nothing (influences parent inline)</td>
              <td>A summary string</td>
              <td>Data (<code>tool_result</code>)</td>
            </tr>
            <tr>
              <th>Cost idle</th>
              <td>Definition in tool list</td>
              <td>~150 tok per description</td>
              <td>~150 tok per description</td>
              <td>~5 tok per name (deferred)</td>
            </tr>
            <tr>
              <th>Cost active</th>
              <td>Same as idle</td>
              <td>+500–3000 tok (body)</td>
              <td>Just the summary</td>
              <td>+~500 tok (schema)</td>
            </tr>
            <tr>
              <th>Best for</th>
              <td>Atomic capabilities</td>
              <td>Procedures with user decisions</td>
              <td>Read-heavy isolated work</td>
              <td>Adding new capabilities</td>
            </tr>
          </tbody>
        </table>
      </div>

### The decision tree {#primitive-decision-tree} {toc:Decision tree}

Start at the top and answer each question:

      <div class="dtree" role="figure" aria-label="Decision tree for picking the right primitive">
        <div class="dtree-node">
          <div class="dtree-q">
            <span class="dtree-q-label">Q1</span>
            <span class="dtree-q-text">Need to ADD a capability Claude doesn't have?</span>
          </div>
          <div class="dtree-branch">
            <span class="dtree-arm">└ YES →</span>
            <span class="dtree-result dtree-mcp">Build an MCP server</span>
          </div>
          <div class="dtree-branch">
            <span class="dtree-arm">└ NO →</span>
          </div>
          <div class="dtree-sub">
            <div class="dtree-q">
              <span class="dtree-q-label">Q2</span>
              <span class="dtree-q-text">Bounded + autonomous work? (no user decisions mid-way)</span>
            </div>
            <div class="dtree-branch">
              <span class="dtree-arm">└ YES →</span>
              <span class="dtree-result dtree-subagent">Spawn a subagent</span>
            </div>
            <div class="dtree-branch">
              <span class="dtree-arm">└ NO →</span>
            </div>
            <div class="dtree-sub">
              <div class="dtree-q">
                <span class="dtree-q-label">Q3</span>
                <span class="dtree-q-text">Follow a procedure with user interaction?</span>
              </div>
              <div class="dtree-branch">
                <span class="dtree-arm">└ YES →</span>
                <span class="dtree-result dtree-skill">Write a skill</span>
              </div>
              <div class="dtree-branch">
                <span class="dtree-arm">└ NO →</span>
                <span class="dtree-result dtree-tool">Use a built-in tool</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p class="caption">Walk top-down. First question that returns YES wins. Most "I built the wrong primitive" mistakes happen when Q1 and Q2 get mixed up.</p>

### Anti-patterns {#primitive-anti-patterns} {toc:Anti-patterns}

<strong>Skill where you needed a subagent.</strong> You wrote a skill: "Read every file under <code>src/</code> and find references to function X." The skill loads, the parent runs Read 50 times in the main thread, context bloats. → Should have been a <strong>subagent</strong> with a small return.

<strong>Subagent where you needed a skill.</strong> You wrote a subagent that walks the user through a deployment checklist: "Did you check X? What's the staging URL? Should we tag the release?" Subagents can't easily interact with the user mid-flight. → This is a <strong>skill</strong>.

<strong>MCP server where you needed a skill.</strong> You built an MCP server with a single tool called <code>publication-checklist</code> that returns a multi-step procedure. → A procedure isn't a capability; it's a <strong>skill</strong>. MCP is for external capabilities, not for stored checklists.

<strong>Tool where you needed an MCP server.</strong> You're embedding "talk to our company's Jira" as ad-hoc Bash + curl in many sessions. Every session re-invents the wheel. → The structured, schema-typed version belongs in an <strong>MCP server</strong>.

### The complementary pattern {#primitive-complementary} {toc:Complementary pattern}

Real workflows often use all four primitives composed together. Here's a hypothetical "publish a release" workflow:

      <div class="compose" role="figure" aria-label="Composition example using all four primitives">
        <div class="compose-header">Example: "Publish v2.4" workflow</div>
        <div class="compose-steps">
          <div class="compose-step">
            <div class="compose-step-num">1</div>
            <div class="compose-step-primitive compose-primitive-user">User</div>
            <div class="compose-step-text">"Let's publish v2.4"</div>
          </div>
          <div class="compose-step">
            <div class="compose-step-num">2</div>
            <div class="compose-step-primitive compose-primitive-skill">Skill</div>
            <div class="compose-step-text"><code>release-checklist</code> triggers; parent now has the procedure + user interaction</div>
          </div>
          <div class="compose-step">
            <div class="compose-step-num">3</div>
            <div class="compose-step-primitive compose-primitive-tool">Built-in</div>
            <div class="compose-step-text"><code>Edit</code> bumps version in <code>package.json</code></div>
          </div>
          <div class="compose-step">
            <div class="compose-step-num">4</div>
            <div class="compose-step-primitive compose-primitive-subagent">Subagent</div>
            <div class="compose-step-text"><code>changelog-auditor</code> reads 200 commits, returns 5-line gap report</div>
          </div>
          <div class="compose-step">
            <div class="compose-step-num">5</div>
            <div class="compose-step-primitive compose-primitive-mcp">MCP tool</div>
            <div class="compose-step-text"><code>slack__post_message</code> announces the release</div>
          </div>
          <div class="compose-step">
            <div class="compose-step-num">6</div>
            <div class="compose-step-primitive compose-primitive-mcp">MCP tool</div>
            <div class="compose-step-text"><code>deploy__mark_released</code> updates the dashboard</div>
          </div>
          <div class="compose-step">
            <div class="compose-step-num">7</div>
            <div class="compose-step-primitive compose-primitive-skill">Skill</div>
            <div class="compose-step-text">Reports completion to user</div>
          </div>
        </div>
      </div>

      <p class="caption">Composition pattern. Each primitive plays its specific role. Skill orchestrates; subagent does isolated research; MCP provides external capabilities; built-ins handle local actions.</p>

Each primitive plays its role:

      <ul>
        <li><strong>Skill</strong> is the orchestrator: knows the steps, knows when to invoke other primitives, interacts with the user</li>
        <li><strong>Subagent</strong> does bounded research (200 commits → 5-line report, context isolation)</li>
        <li><strong>MCP servers</strong> provide capabilities Claude doesn't natively have (Slack, deployment dashboard)</li>
        <li><strong>Built-in tools</strong> handle local stuff (edit version number, read files)</li>
      </ul>

They don't compete; they complement. Skills tell the parent <em>when</em> to use subagents and tools. Subagents do <em>isolated work</em>. MCP adds <em>new capabilities</em>. Tools are <em>the actual function calls</em>.

### "Name the primitive" exercise {#primitive-exercise} {toc:"Name the primitive" exercise}

For each scenario, the right primitive:

      <table>
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Primitive</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>"When the user mentions security review, walk them through these 8 checks"</td><td><strong>Skill</strong></td></tr>
          <tr><td>"Search all 500 files for instances of deprecated API X"</td><td><strong>Subagent</strong> (read-heavy, small answer)</td></tr>
          <tr><td>"Let Claude post to our team's status board"</td><td><strong>MCP server</strong> (new capability)</td></tr>
          <tr><td>"Read the contents of this file"</td><td><strong>Tool</strong> (built-in <code>Read</code>)</td></tr>
          <tr><td>"Audit 30 published artifacts for stale links, report which need updates"</td><td><strong>Subagent</strong></td></tr>
          <tr><td>"Provide a hard-gated procedure for promoting drafts to public"</td><td><strong>Skill</strong></td></tr>
          <tr><td>"Connect Claude to our Postgres for schema queries"</td><td><strong>MCP server</strong></td></tr>
        </tbody>
      </table>

### The unified lesson {#primitive-unified-lesson} {toc:The unified lesson}

Across all four primitives, the same pattern shows up:

      <ul>
        <li><strong>Tools</strong> rely on a clear description for the model to know when to call them</li>
        <li><strong>Skills</strong> rely on a clear description for triggering</li>
        <li><strong>Subagents</strong> rely on a clear description for delegation</li>
        <li><strong>MCP server tools</strong> rely on a clear description (same as built-in tools)</li>
      </ul>

<strong>Descriptions are the universal discovery surface.</strong> When something you built doesn't get used, the first investigation is always the description, across all four primitives.

## Memory, hooks, permissions, plan mode {#governance} {toc:Memory, hooks, permissions, plan mode}

These are the <strong>governance layer</strong>: the four knobs that let you shape <em>how</em> Claude Code behaves across sessions, what it can do without asking, when it intervenes deterministically, and how it stays in "design" mode before acting. None of these add capabilities the way MCP or skills do. They shape what's allowed, what's remembered, and what triggers automatically.

This section is shorter than the primitives sections; these are conceptually simpler, but they're the difference between a harness that <em>just works</em> and one that's calibrated to you.

<em>(Other tools have analogous concepts under different names: Cursor's rules system, Cline's custom instructions, similar patterns in agent SDKs. The soft/hard distinction below is what travels.)</em>

      <div class="govern-grid" role="figure" aria-label="The four governance knobs at a glance">
        <div class="gov-card gov-memory">
          <div class="gov-header">
            <span class="gov-name">Memory</span>
            <span class="gov-label">system prompt</span>
          </div>
          <div class="gov-text">Shapes what Claude knows across sessions. CLAUDE.md + auto-memory files concatenated into the system prompt every turn.</div>
        </div>
        <div class="gov-card gov-hooks">
          <div class="gov-header">
            <span class="gov-name">Hooks</span>
            <span class="gov-label">event boundary</span>
          </div>
          <div class="gov-text">Deterministic event handlers run by the harness. Fire on UserPromptSubmit, PreToolUse, PostToolUse, Stop, SessionStart.</div>
        </div>
        <div class="gov-card gov-perms">
          <div class="gov-header">
            <span class="gov-name">Permissions</span>
            <span class="gov-label">tool boundary</span>
          </div>
          <div class="gov-text">Allow / Ask / Deny per tool or pattern. The load-bearing safety layer, every tool call passes through here first.</div>
        </div>
        <div class="gov-card gov-plan">
          <div class="gov-header">
            <span class="gov-name">Plan mode</span>
            <span class="gov-label">session mode</span>
          </div>
          <div class="gov-text">Read-only design mode. Model can think and search; cannot write or run side-effecting commands until approved.</div>
        </div>
      </div>

      <p class="caption">The four governance knobs operate at different layers of the session, memory in system-prompt assembly, hooks at event boundaries, permissions at tool boundaries, plan mode at the session level.</p>

### Memory — durable facts across sessions {#memory-layer} {toc:Memory}

Skills and CLAUDE.md cover within-session and within-project context. <strong>Memory</strong> covers cross-session, longer-lived facts the model should know on every interaction.

Two mechanisms in Claude Code:

      <ul>
        <li><strong><code>CLAUDE.md</code> files</strong>, project-level instructions loaded automatically when working in that directory. Walked up the directory tree (so <code>src/CLAUDE.md</code> + project root <code>CLAUDE.md</code> both apply when editing under <code>src/</code>). Best for project conventions, architecture notes, "always do X here" rules.</li>
        <li><strong>Auto-memory</strong>: Claude can save and recall durable facts about <em>you</em> (preferences, work style, recurring projects) at <code>~/.claude/projects/&lt;project-slug&gt;/memory/</code>. Each entry is its own markdown file with name, description, content; <code>MEMORY.md</code> indexes them.</li>
      </ul>

Memory files get concatenated into the system prompt on every turn (same assembly mechanic from earlier). They cost tokens but don't fight for conversation budget.

<strong>When to add a memory entry vs CLAUDE.md vs skill:</strong>

      <ul>
        <li><em>Fact about how you personally work</em> (preferences, conventions) → auto-memory</li>
        <li><em>Fact about this specific project</em> (architecture, where things live) → <code>CLAUDE.md</code></li>
        <li><em>Procedure to follow when a specific trigger fires</em> → skill</li>
      </ul>

### Hooks — deterministic event handlers {#hooks-layer} {toc:Hooks}

A hook is a shell command the harness runs at specific event moments. <strong>Not</strong> a model decision; the harness fires hooks deterministically when configured events happen.

The hook events I reach for most (the Claude Code docs have the full list):

      <ul>
        <li><code>PreToolUse</code>: fires before a tool runs (can block the call)</li>
        <li><code>PostToolUse</code>: fires after a tool returns (can inspect/modify the result)</li>
        <li><code>UserPromptSubmit</code>: fires when you send a message (can inject context, redirect)</li>
        <li><code>Stop</code>: fires when Claude finishes a turn (good for notifications)</li>
        <li><code>SessionStart</code>: fires when a session begins (good for setup)</li>
      </ul>

Others worth knowing exist for subagent stops, pre/post-compaction, session end, and desktop notifications.

      <div class="hook-timeline" role="figure" aria-label="Hook event timeline during a turn">
        <div class="ht-step ht-action">Session starts</div>
        <div class="ht-event">SessionStart</div>
        <div class="ht-step ht-action">Waiting</div>
        <div class="ht-step ht-action">User sends prompt</div>
        <div class="ht-event">UserPromptSubmit</div>
        <div class="ht-step ht-action">Model inference</div>
        <div class="ht-step ht-action">Model emits tool_use</div>
        <div class="ht-event">PreToolUse</div>
        <div class="ht-step ht-action">Tool executes</div>
        <div class="ht-event">PostToolUse</div>
        <div class="ht-step ht-action">Model continues</div>
        <div class="ht-step ht-action">Turn ends</div>
        <div class="ht-event">Stop</div>
      </div>

      <p class="caption">Hook event timeline. Each amber band is a deterministic firing point where the harness can run a shell command: block a tool, inject context, format output, notify, etc.</p>

Hooks are configured in your settings as <code>{ event, matcher, command }</code>. The harness runs the command, reads the exit code and stdout, and acts accordingly.

<strong>What hooks are good for:</strong>

      <ul>
        <li><strong>Safety enforcement</strong>: block writes to <code>~/secrets/</code> regardless of what the model decides</li>
        <li><strong>Auto-formatting</strong>: run <code>prettier</code> after every Edit</li>
        <li><strong>Notifications</strong>: ping a desktop notification when a long task finishes</li>
        <li><strong>Context injection</strong>: append current git status to every prompt</li>
        <li><strong>Deterministic automation</strong>: "every time the agent stops, run <code>gitleaks</code>"</li>
      </ul>

<strong>Hook vs CLAUDE.md instruction</strong>: an instruction in CLAUDE.md is a <em>suggestion</em> the model may or may not follow. A hook is <em>enforcement</em>: the harness runs it regardless of model intent. Use hooks for safety/security; use CLAUDE.md for conventions you can live without 100% compliance on.

### Permissions — what's pre-approved {#permissions-layer} {toc:Permissions}

Every tool call the model wants to make goes through the permissions engine. Three states per tool/pattern:

      <ul>
        <li><strong>Allow</strong>: auto-approved, no prompt</li>
        <li><strong>Ask</strong>: prompts you each time</li>
        <li><strong>Deny</strong>: blocked outright</li>
      </ul>

You configure these per-tool, per-pattern. Examples:

      <ul>
        <li><code>Read</code> → allow (reading files is safe)</li>
        <li><code>Bash(npm:*)</code> → allow (npm commands pre-approved)</li>
        <li><code>Bash(rm -rf:*)</code> → deny (never)</li>
        <li><code>Edit(~/secrets/*)</code> → deny (never touch secrets)</li>
        <li><code>Bash(*)</code> → ask (any other shell command requires approval)</li>
      </ul>

Permission patterns use the same matching mechanic as hooks. Specific patterns take precedence over general ones.

<strong>The permission engine is the load-bearing safety layer.</strong> Skills, hooks, and the model itself all sit <em>behind</em> permissions. Even if a skill says "now run <code>rm -rf /</code>," the permission engine intercepts before the tool runs.

The opposite extremes ("allowlist everything" vs "ask for every command") both have failure modes. Allowing everything trades safety for speed; asking everything makes work tedious. Most productive users converge on a middle ground: allow common safe operations, ask for everything that touches shared state or is hard to reverse.

### Plan mode — design before doing {#plan-mode-layer} {toc:Plan mode}

Plan mode is a harness-level state where:

      <ul>
        <li>The model can read, think, search, ask questions</li>
        <li>The model <strong>cannot</strong> write to any file except a designated plan file</li>
        <li>The model <strong>cannot</strong> run side-effecting commands</li>
        <li>At the end, the model presents a plan, and you approve before execution begins</li>
      </ul>

It's a "dry run" mode that scales to complex tasks. Useful when:

      <ul>
        <li>You want the model to think through a task before acting</li>
        <li>The task spans many files or has irreversible steps</li>
        <li>You want to vet the approach before any side effects</li>
        <li>You want the planning artifact preserved as documentation</li>
      </ul>

Enter via the <code>/plan</code> command or certain workflows. Exit with <code>ExitPlanMode</code> (the model calls this when the plan is ready). Your approval starts execution.

### How they fit together {#governance-composition} {toc:How they fit together}

These four knobs operate at different layers of the session:

      <table>
        <thead>
          <tr>
            <th>Knob</th>
            <th>Layer</th>
            <th>Acts on</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Memory</td><td>System prompt</td><td>What Claude <em>knows</em> across sessions</td></tr>
          <tr><td>Hooks</td><td>Event boundary</td><td>What the <em>harness</em> does deterministically</td></tr>
          <tr><td>Permissions</td><td>Tool boundary</td><td>What <em>gets approved</em> without prompting</td></tr>
          <tr><td>Plan mode</td><td>Session mode</td><td>What the <em>model can do</em> (read-only design vs. full execution)</td></tr>
        </tbody>
      </table>

They compose: memory shapes Claude's defaults; hooks enforce deterministic behavior; permissions gate every action; plan mode constrains the whole session. Together they let you dial in how Claude Code behaves to match your taste and your safety bar.

## Productivity patterns {#productivity} {toc:Productivity patterns}

The final synthesis. Nothing new mechanically: just how to combine the primitives and governance knobs into a usable daily playbook.

### Context budgeting — the highest-leverage habit {#context-budgeting} {toc:Context budgeting}

The single biggest productivity gain comes from treating context as a budget, not an unlimited resource:

      <ul>
        <li><strong>Watch tool results.</strong> They're ~90% of "where did my context go?" One careless <code>cat huge-log.txt</code> or one verbose <code>npm install</code> can eat 50K tokens.</li>
        <li><strong>Delegate heavy reads to subagents.</strong> Anything more than ~5 file reads to find an answer is a candidate for an <code>Explore</code> subagent. Subagent reads 50 files in <em>its</em> context, returns a 30-token summary, your main thread saves ~99% of the cost.</li>
        <li><strong>Move durable facts to memory.</strong> If you're re-explaining the same context across sessions, that's a memory entry waiting to be written.</li>
        <li><strong><code>/clear</code> between phases.</strong> Memory and CLAUDE.md still load; durable context survives.</li>
        <li><strong>Cache awareness.</strong> Don't let conversations cool beyond ~5 minutes between turns if you can help it.</li>
        <li><strong>Run <code>/context</code> when something feels heavy.</strong> It tells you exactly what's eating budget.</li>
      </ul>

### Description-first design {#description-first} {toc:Description-first design}

When you build something (a skill, a custom subagent, an MCP tool), the description determines whether it's ever used. Workflow:

      <ol>
        <li><strong>Write the description first</strong>: before the body/implementation</li>
        <li><strong>List 3–5 user phrases</strong> that should trigger it. Paste actual things you'd say</li>
        <li><strong>Front-load <code>Use when:</code></strong>, the model treats this as a strong signal</li>
        <li><strong>Distinguish from neighbors</strong>: what else might match? Why is this one right?</li>
        <li><strong>Test it</strong>: try invoking it, see if it fires. Iterate on description more than body.</li>
      </ol>

When a primitive doesn't fire as expected: <strong>edit the description first.</strong> Rewrite the body only after the description fix fails.

### Picking the right primitive (recap) {#picking-recap} {toc:Picking the right primitive}

      <ul>
        <li>New capability Claude doesn't have → <strong>MCP server</strong></li>
        <li>Bounded autonomous work, small answer → <strong>Subagent</strong></li>
        <li>Procedure with user interaction → <strong>Skill</strong></li>
        <li>One-off action → <strong>built-in tool</strong></li>
      </ul>

If you're tempted to build a custom subagent that needs user input mid-flight, you wanted a skill. If you're tempted to write a skill that reads 50 files autonomously, you wanted a subagent.

### Soft vs hard governance — pick the right mechanism {#soft-hard} {toc:Soft vs hard governance}

For each requirement, ask: <em>"if the model occasionally ignored this, would it matter?"</em>

      <table>
        <thead>
          <tr>
            <th>Stakes</th>
            <th>Mechanism</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Safety, security, reversibility-critical</td><td><strong>Hard</strong>: permissions deny, hook block</td></tr>
          <tr><td>Conventions, style, defaults</td><td><strong>Soft</strong>: CLAUDE.md, skill</td></tr>
          <tr><td>Cross-session personal preferences</td><td><strong>Memory</strong></td></tr>
          <tr><td>One-time per-session constraint</td><td><strong>Plan mode</strong></td></tr>
        </tbody>
      </table>

Default failure mode: putting safety-critical rules in CLAUDE.md (soft). They'll be violated. Move them to hard mechanisms.

### Session hygiene {#session-hygiene} {toc:Session hygiene}

      <ul>
        <li><strong><code>/clear</code> between unrelated phases.</strong> Each phase starts fresh; memory + CLAUDE.md persist.</li>
        <li><strong>Switch models to fit the task.</strong> Haiku for cheap read-heavy research subagents; Sonnet as the workhorse; Opus when the task demands deep reasoning. Same harness, different brain.</li>
        <li><strong>Plan mode for high-blast-radius work.</strong> Multi-file refactors, auth/security/migration work.</li>
        <li><strong>Pause-and-resume discipline.</strong> When stepping away mid-task, write down resume state explicitly. Don't rely on memory of where you were.</li>
      </ul>

### Diagnostic flow — when something misbehaves {#diagnostic-flow} {toc:Diagnostic flow}

Knowing which layer to investigate saves more time than any single fix.

      <div class="diag" role="figure" aria-label="Diagnostic reference: symptom to layer to action">
        <div class="diag-header">
          <div class="diag-col-header">Symptom</div>
          <div class="diag-col-header">Layer to investigate</div>
          <div class="diag-col-header">First action</div>
        </div>
        <div class="diag-row">
          <div class="diag-symptom">Custom primitive not used</div>
          <div class="diag-layer">Harness · description</div>
          <div class="diag-action">Rewrite the description before the body</div>
        </div>
        <div class="diag-row">
          <div class="diag-symptom">Buggy code output</div>
          <div class="diag-layer">Model</div>
          <div class="diag-action">Different model, more context, sharper prompt</div>
        </div>
        <div class="diag-row">
          <div class="diag-symptom">Context filled up too fast</div>
          <div class="diag-layer">Structural · context</div>
          <div class="diag-action"><code>/context</code> → find heavy tool result → subagent, <code>/clear</code>, or memory</div>
        </div>
        <div class="diag-row">
          <div class="diag-symptom">Slow response after pause</div>
          <div class="diag-layer">Cache</div>
          <div class="diag-action">Cache cooled (&gt;5 min). Tolerate or avoid long pauses</div>
        </div>
        <div class="diag-row">
          <div class="diag-symptom">Hook not firing</div>
          <div class="diag-layer">Harness · config</div>
          <div class="diag-action">Check <code>settings.json</code> hook matcher</div>
        </div>
        <div class="diag-row">
          <div class="diag-symptom">Tool blocked or prompted</div>
          <div class="diag-layer">Harness · permissions</div>
          <div class="diag-action">Check allow/ask/deny patterns in <code>settings.json</code></div>
        </div>
      </div>

      <p class="caption">Diagnostic reference. Identify the symptom → know which layer to investigate → take the first action. The model vs. harness diagnostic, applied to common situations.</p>

### What to invest in over time {#compounding} {toc:Compounding investments}

Small effort now, big payoff later. These compound:

      <div class="invest" role="figure" aria-label="Compounding investments">
        <div class="invest-col invest-effort">
          <div class="invest-col-header">Effort now (small)</div>
          <div class="invest-item">Description engineering for skills + subagents</div>
          <div class="invest-item">Memory entries for cross-session facts</div>
          <div class="invest-item">Focused CLAUDE.md per project</div>
          <div class="invest-item">1–2 well-chosen hooks for safety</div>
          <div class="invest-item">Curated permissions allow/deny list</div>
        </div>
        <div class="invest-arrow" aria-hidden="true">⟶</div>
        <div class="invest-col invest-payoff">
          <div class="invest-col-header">Payoff over months (big)</div>
          <div class="invest-item">Skills fire reliably; no re-prompting</div>
          <div class="invest-item">Cross-session context for free</div>
          <div class="invest-item">Claude knows your project conventions</div>
          <div class="invest-item">Automated guardrails always on</div>
          <div class="invest-item">Friction-free common operations</div>
        </div>
      </div>

      <p class="caption">Compounding investments. Each is small effort now; each saves cognitive load on every future session. Six months in, the difference between "I built nothing" and "I tuned these" is orders of magnitude in iteration speed.</p>

      <ol>
        <li><strong>Description engineering</strong> for your skills and custom subagents. The single highest-leverage investment.</li>
        <li><strong>Memory entries</strong> for cross-session facts. Each one saves re-explanation in every future session.</li>
        <li><strong>A focused CLAUDE.md per project</strong>: project conventions Claude should always know.</li>
        <li><strong>One or two well-chosen hooks</strong> for safety automation (path guards, formatters, security scans).</li>
        <li><strong>A permissions allow/deny list</strong> that matches your real workflow. If you've chosen to keep prompts on as a learning posture, keep that; otherwise codify common-safe operations once you know them.</li>
      </ol>

### The unified lesson {#unified-lesson-final} {toc:The unified lesson}

Across everything covered:

      <ul>
        <li><strong>Model vs harness</strong>: different layers, different fixes</li>
        <li><strong>Descriptions are the universal discovery surface</strong>: across tools, skills, subagents, MCP</li>
        <li><strong>Tool results dominate context</strong>: be deliberate about Reads, Bash, WebFetch</li>
        <li><strong>Soft vs hard governance</strong>: match the mechanism to the stakes</li>
        <li><strong>Composition over piling on</strong>: pick the right primitive, don't reach for the same hammer</li>
      </ul>

The harness is a configurable system, whichever one you're using. Most "I'm fighting this tool" frustrations resolve once you know which knob to turn for which problem. The specifics differ across Claude Code, Cursor, Cline, Codex, Antigravity, and custom-built agents, but the mental model travels. Now you have it.
