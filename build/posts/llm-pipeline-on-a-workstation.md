---
title: I built a full LLM pipeline on two desktop machines. The bottleneck was never the disk.
subtitle: Data prep, distillation, fine-tuning, eval, serving, all on workstation hardware. I measured every stage to find where the work is really slow, and where storage finally takes over.
byline: Kumar Nachiketa · AIHomeLab · Personal capacity
author: Kumar Nachiketa
authorsub: AIHomeLab · personal capacity
date: 2026-06-07
datesub: Living document
reading: ~12 min
readingsub: Numbers tucked in the toggles
scope: One AI pipeline, two desktops
scopesub: Plain-language; engineer depth on tap
slug: llm-pipeline-on-a-workstation
tags: Storage, AI infrastructure, LLM
description: A full LLM pipeline, data prep through serving, built on two desktop machines and measured at every step. As a storage practitioner I expected the disk to bind; it almost never did. Here is what the real bottleneck was at each stage, and where storage finally takes over.
summary: I built a recipe-writing LLM end to end on two desktop machines, data prep, teacher-student distillation, fine-tuning, eval, and serving, and measured where each stage actually got slow. The disk was almost never the bottleneck; the interesting part is what was, and where storage finally takes over. Measured numbers tucked into "for engineers" toggles.
sourcenote: <strong>A note on sources.</strong> Every number in this post comes from a real run on two NVIDIA DGX Spark workstations in my house; nothing is rounded into a new claim. Where I talk about enterprise scale, that is reasoned projection, labeled as such throughout. The full engineer writeup, with every measurement, the reproduce kits, and the <a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/storage-touchpoints-map/storage-touchpoints-map.md" target="_blank" rel="noopener">storage touch-points map</a> behind it, lives in the AIHomeLab artifact: <a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/llm-pipeline-on-a-workstation/llm-pipeline-on-a-workstation.md" target="_blank" rel="noopener">What I learned building an LLM pipeline on a workstation</a>.
---

My wife types "a vegan Punjabi curry with chickpeas and spinach, no coconut," and a model running on two machines in our house writes her the whole recipe. I built that, but the recipe was never the point. Storage and AI infrastructure is my craft, and I built the whole pipeline at desk scale for one reason: to instrument the I/O at every step, see where the work is actually slow, and reason about how that shifts at scale.

This is not the smart way to get vegan recipes; my wife's phone already writes a better curry. I picked it because it exercises every step of a real pipeline. There is a reflex in my field to blame storage first, with good reason: the worst outcome here is an expensive GPU idle, waiting on data the storage layer was too slow to deliver. For a workload this small, though, I expected the disk never to be the bottleneck, and it never was. So the real question was not whether storage would bind; it was finding what actually was slow at each step, and pinning the one thing that would hand the job back to storage as you scale. Keep that scorecard as we go.

What follows is the five steps in plain language, each with a small diagram. Want the measured numbers and the read on how each one scales up? Every section has a "for engineers" drawer; everyone else can glide right past.

      <div class="tryit">
        <div class="tryit-label">Try it yourself</div>
        <p>The whole pipeline ships as an <a href="https://github.com/knachiketa04/aihomelab/tree/main/artifacts/concepts/llm-pipeline-on-a-workstation/reproduce/" target="_blank" rel="noopener">end-to-end reproduce kit</a>: the as-run scripts for every stage (ingest and clean, synthetic generation, fine-tune, eval, serve), plus a run guide. Paths and hosts are parameterized, so it adapts to hardware beyond the DGX Spark I used.</p>
      </div>

## The five steps, at a glance {#the-five-steps} {toc:The five steps, at a glance}

Before the steps, here is the whole thing at a glance. This is all my wife ever sees:

      <div class="usecase">
        <div class="uc-node">
          <div class="uc-label">My wife types</div>
          <div class="uc-text">"a vegan Punjabi curry with chickpeas and spinach, no coconut"</div>
        </div>
        <div class="uc-arrow" aria-hidden="true">&#8594;</div>
        <div class="uc-node uc-model">
          <div class="uc-label">The model, on two machines at home</div>
          <div class="uc-text">reads the request, writes a recipe</div>
        </div>
        <div class="uc-arrow" aria-hidden="true">&#8594;</div>
        <div class="uc-node">
          <div class="uc-label">She gets back</div>
          <div class="uc-text">a full recipe: substitutions, steps, technique notes</div>
        </div>
      </div>

She types a request, the model writes the recipe. Everything else is the kitchen work behind that one interaction. Here is that kitchen work: the build, in five stages grouped into three phases.

      <div class="pipeline" role="img" aria-label="The build pipeline: five stages grouped into prep, train, and serve, all riding on shared storage that stays idle.">
        <div class="pipe-phases">
          <div class="pipe-phase">
            <div class="pipe-phase-label">Prep</div>
            <div class="pipe-stages">
              <div class="pipe-stage">
                <div class="ps-top"><span class="ps-num">1</span><span class="ps-name">Data prep</span></div>
                <div class="ps-desc">Gather &amp; clean the recipes</div>
                <div class="ps-bn">Slow part: <b>the cleaning logic</b></div>
              </div>
              <div class="pipe-stage">
                <div class="ps-top"><span class="ps-num">2</span><span class="ps-name">Synthetic gen</span></div>
                <div class="ps-desc">A big model writes the study guide</div>
                <div class="ps-bn">Slow part: <b>the memory wall</b></div>
              </div>
            </div>
          </div>
          <div class="pipe-phase">
            <div class="pipe-phase-label">Train</div>
            <div class="pipe-stages">
              <div class="pipe-stage">
                <div class="ps-top"><span class="ps-num">3</span><span class="ps-name">Fine-tune</span></div>
                <div class="ps-desc">Teach the small model</div>
                <div class="ps-bn">Slow part: <b>the writers</b></div>
              </div>
              <div class="pipe-stage">
                <div class="ps-top"><span class="ps-num">4</span><span class="ps-name">Eval</span></div>
                <div class="ps-desc">Grade the student</div>
                <div class="ps-bn">Slow part: <b>the grader's quality</b></div>
              </div>
            </div>
          </div>
          <div class="pipe-phase">
            <div class="pipe-phase-label">Serve</div>
            <div class="pipe-stages">
              <div class="pipe-stage">
                <div class="ps-top"><span class="ps-num">5</span><span class="ps-name">Serve</span></div>
                <div class="ps-desc">Put it online for my wife</div>
                <div class="ps-bn">Slow part: <b>one CPU core</b></div>
              </div>
            </div>
          </div>
        </div>
        <div class="pipe-substrate"><b>Shared storage</b> sits underneath all five stages, and stays idle the entire time at this scale. That is the puzzle this piece is about.</div>
      </div>

      <p class="caption">Left to right, 12.8 MiB of raw recipes become a cleaned corpus, then a study guide, then a trained model, then a grade, then a live endpoint. My wife only ever touches the last box. Each stage has a slow part, and across the five it is never the same layer twice.</p>

One piece of hardware you need in your head, and only one. Each machine puts the regular processor and the graphics chip on a single chip, sharing <strong>one pool of memory</strong> between them. There is no separate stash of "graphics memory" to copy things into; both sides read the same pool. The one number that matters all the way through this piece is how fast that pool can be read. Everything downstream eventually bumps into it.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p>The boxes are two NVIDIA DGX Spark nodes (Grace-class GB10, unified memory). One shared LPDDR5X pool, bandwidth about <strong>273 GB/s</strong>. A server-class H100 delivers roughly <strong>3,350 GB/s</strong> from HBM3, about <strong>12x</strong> more, and that single ratio explains most of what a workstation can and cannot do. Two consequences of one shared pool: "load the model" and "fill the page cache" compete for the same physical RAM, and the tools lie, <code>nvidia-smi</code> reports "Memory-Usage: Not Supported" because there is no distinct GPU pool to measure. Watch system memory and per-core CPU instead.</p>
        </div>
      </details>

## Step 1 — Cleaning the recipe box {#step-1-cleaning} {toc:Step 1 · Cleaning the recipe box}

Picture three shoeboxes of recipe clippings from three different sources: a community cookbook, some old public-domain books, and a pile of encyclopedia food articles. Different handwriting, different formats, duplicates, a few cards filed under the wrong label. The job is to sort, read, and de-duplicate them into one tidy box. That is the kind of work this step is: reading and sorting, not heavy lifting.

{% flow %}
aria: Data prep flow: three messy sources land on the disk, three cleaning passes do the real work, out comes one clean corpus.
node: Three sources | Wikibooks, Gutenberg, Wikipedia | 12.8 MiB, three messy formats
node quiet: Storage | lands on the shared disk | 3% full, idle
node slow: Slow part | three cleaning passes | unify formats, tag vegan/veg, drop duplicates
node: Out | one clean corpus | ready to use
legend: slow=the real slow part | quiet=storage, sitting quiet
caption: The disk just holds the files. The real work, and where a bug like 23 "vegan" catfish recipes hides, is **the cleaning logic** in the middle.
{% endflow %}

I pulled in the three sources, then ran three quick cleaning passes: unify the formats, tag each recipe vegan or vegetarian, and drop the near-duplicates. Each pass finished in under a second, and the disk sat idle the whole time. The reflex says this is the classic "read a pile of files, write a pile of files" disk grind. At 12.8 MiB it is nothing of the sort, and that is no surprise: the corpus is tiny.

What I actually fought was the logic. Parsing three messy formats into one, and a classifier that confidently tagged 23 catfish recipes as vegan because the word "fish" did not match inside "catfish." That class of bug, a rule that is almost right, is the real work at this size. Not throughput. Correctness.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p>Raw corpus <strong>12.8 MiB</strong>. Three sequential passes (schema unify, rule-based vegan/veg tagging, MinHash near-dup removal), each reading and writing single-digit MiB in <strong>under a second</strong>; full clean under five minutes wall-clock; shared filesystem at <strong>3% of capacity</strong> throughout. At one-second sampling the storage telemetry produced no resolved signal at all; the numbers are sub-sampling-noise. Where it would flip: single-node cleaning scales roughly linearly, so a 1 GB corpus is still seconds-to-minutes of CPU with the disk asleep. Storage only becomes first-order at terabyte/petabyte-scale ingest, where sustained writes bind against shared-filesystem ceilings like the ~1.35 GB/s measured on this stack. <em>The 12.8 MiB figures are measured; the petabyte step is a projection, not data.</em></p>
        </div>
      </details>

## Step 2 — A big model tutors a small one {#step-2-tutor} {toc:Step 2 · A big model tutors a small one}

Now the cleverest trick in the whole build. To teach a small, fast model, you hire a big, brilliant, slow one as a tutor. The big model writes thousands of worked examples, question and ideal answer, and the small model learns from them. The industry calls it teacher-student distillation. Think of a professor writing out a study guide that a quick undergrad will then memorize.

{% flow %}
aria: Synthetic generation flow: the clean corpus grounds a big teacher model, which rereads its whole 61 GB brain for every word to write the study guide.
node: In | the clean corpus | recipes to ground on
node model: The tutor | a big 32B model, on both machines | ~61 GB brain
node slow: Slow part | rereads the entire 61 GB brain for every single word | the memory wall
node: Out | a study guide | 12,368 worked examples
caption: Speed is set by how fast the machine can reread that 61 GB brain, once per word. The disk hands the brain over once at the start and goes quiet, so it is **not** the bottleneck.
{% endflow %}

Here is the thing that governs everything from here on. To produce a single word, the model has to read its entire brain, start to finish. The tutor's brain is about 61 gigabytes. So it reads 61 GB to write one word, then reads all 61 GB again for the next word, and again, and again. The bottleneck is not how clever it is and it is not the disk; it is how fast you can read that pool of memory I mentioned earlier. That is the "memory wall," and it is the speed limit you cannot buy your way around with a faster drive.

What about my storage worry, loading that 61 GB tutor off disk in the first place? It was slow, but not because of the disk. The giveaway: loading it from a cold start and loading it from a warm cache took the same amount of time. If the disk were the bottleneck, warming it up first would help. It did not, because the time was going into the processor unpacking the file, not the disk reading it. The disk just handed over the bytes and went back to sleep. The model's answers, meanwhile, trickled out to disk at a few kilobytes a second.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p>32B teacher (Qwen3-32B), ~61 GiB of weights, run data-parallel across both nodes to generate the instruction-tuning set. The memory-wall floor on decode:</p>
          <div class="formula">seconds per token &ge; model bytes / memory bandwidth<br>61 GiB &asymp; 65.5 GB ; &nbsp;65.5 GB / 273 GB/s &asymp; <strong>0.24 s/token</strong></div>
          <p>That 0.24 is a derived ceiling, not a captured single-stream latency; batching rescues throughput, not latency. Measured aggregate ~<strong>0.6 requests/sec/node</strong> at batch size 32. Cold-load of the teacher from Lustre took <strong>419 to 432 s</strong> (~149 MiB/s effective), and cold vs warm landed within <strong>3%</strong> of each other, the tell that the load is CPU-bound deserialization, not disk. Prefix cache hit <strong>94%</strong>; output JSONL wrote at ~<strong>3 KB/s</strong>. A separate, harder ceiling: the UMA GPU allocator accumulated pressure across dozens of reloads and eventually wedged the node, capping the run at <strong>12,368 rows</strong>. That is a reliability limit, not a storage one. <em>The cold/warm spread is measured; the 0.24 ceiling is arithmetic the run never reached.</em></p>
        </div>
      </details>

## Step 3 — Saving the model, the fairest test for storage {#step-3-save} {toc:Step 3 · Saving the model}

Step 3 is where the small model actually learns, training on that study guide from Step 2. It is also the one stage that is unambiguously a storage write, because teaching a model means periodically saving its progress, and saving a multi-gigabyte model is exactly the "write a big file to disk" job the storage reflex points at. So if storage is going to bind anywhere in this pipeline, it should be here. I ran it two ways.

      <div class="flow" role="img" aria-label="Fine-tune flow: the student model is saved two ways. A tiny LoRA save is too small to matter; a 46 GB full save is paced by the writers, not the disk, which loafs.">
        <div class="flow-row">
          <div class="flow-node fn-model">
            <div class="fn-label">Training</div>
            <div class="fn-text">the student model learns</div>
            <div class="fn-sub">then saves its progress</div>
          </div>
          <div class="flow-arrow" aria-hidden="true">&#8594;</div>
          <div class="flow-branch">
            <div class="flow-node">
              <div class="fn-label">Tiny save (LoRA)</div>
              <div class="fn-text">97 MB sticky-note, gone in 1 to 3 s</div>
              <div class="fn-sub">too small to even see</div>
            </div>
            <div class="flow-node fn-slow">
              <div class="fn-label">Big save (full retrain)</div>
              <div class="fn-text">46 GB every save, paced by the writers</div>
              <div class="fn-sub">the slow part, but still not the disk</div>
            </div>
          </div>
          <div class="flow-arrow" aria-hidden="true">&#8594;</div>
          <div class="flow-node fn-quiet">
            <div class="fn-label">Storage</div>
            <div class="fn-text">takes the writes</div>
            <div class="fn-sub">loafs at under half busy</div>
          </div>
        </div>
        <p class="flow-caption">The big 46 GB save is a real write, but the disk has headroom to spare. What sets the pace is <b>how many writers feed it</b>, not the disk.</p>
      </div>

### The tiny save {#step-3-lora} {toc:The tiny save}

The first way is the lightweight one. Instead of rewriting the entire cookbook, you clip a few sticky notes onto it: a small set of adjustments that nudge the model's behavior. The save is tiny, about 97 megabytes, written in one to three seconds, too small for the disk to even notice. Over a 70-minute training run, all the saving combined came to about 12 seconds. The actual cost of this approach was compute, the model crunching numbers, with the disk a rounding error.

### The big save {#step-3-full} {toc:The big save}

The second way rewrites the whole cookbook. Every save is the full model, about 46 gigabytes, written across both machines at once. This is a real write, the most storage-like workload in the pipeline.

Even here, the disk is not the constraint. I measured one writer pushing the save, then two. Two writers got the job done noticeably faster, which already tells you something: if the disk were maxed out, a second writer could not have helped. And the whole time, the disk sat under half busy. It had plenty of headroom. The thing setting the pace was not the disk at all; it was how many writers were feeding it and how long each one spent waiting for an acknowledgment before sending more.

This is the most transferable lesson in the project, so let me say it plainly: the obvious dashboard lied. The standard "how busy is the disk" meter looked the same whether the disk was the bottleneck or just patiently waiting for work. To tell the difference I had to stop trusting the obvious gauge and read the layer underneath, the one that actually knew whether the disk was straining or coasting. It was coasting.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p>Lightweight arm: LoRA adapter, <strong>97 MB</strong> per checkpoint, flat <strong>1 to 3 s</strong>, page-cache resident; ~12 s of saving across a 70-minute run; real cost ~<strong>5.7 s per training step</strong> of compute. Full arm: full-parameter SFT, <strong>46 GB</strong> per checkpoint (16 GB model + 30 GB optimizer state), DCP-sharded across both nodes over RoCE to Lustre-on-ZFS:</p>
          <table>
            <thead><tr><th>Pattern</th><th>Throughput</th><th>Per ckpt</th><th>Disk busy</th><th>Bound by</th></tr></thead>
            <tbody>
              <tr><td>Write, 1 writer</td><td>0.78 GB/s</td><td>59 s</td><td>&lt;55%</td><td>client latency</td></tr>
              <tr><td>Write, 2 writers</td><td>1.32 GB/s (1.69x)</td><td>35 s</td><td>~42%</td><td>writer concurrency</td></tr>
              <tr><td>Restore read</td><td>1.37 GB/s</td><td>n/a</td><td>~20%</td><td>client (pipelined)</td></tr>
            </tbody>
          </table>
          <p>Why the obvious dashboard is useless here: single-writer 0.78 GB/s sits inside this stack's own delivered band (~0.5 to 0.8 GB/s), so <code>iostat %util</code> is degenerate, "client is the cap" and "disk is the cap" look identical. What settles it: ZFS transaction-group stats show dirty data at a few percent of cap with sync times far under timeout (pool has headroom), and per-thread CPU shows the writer parked off-CPU <strong>70 to 95%</strong> of the write (waiting on completions, not burning a core). Two writers land on the ~1.35 GB/s concurrent ceiling an independent test measured on this stack, disk to spare. <em>The 1.69x scaling and substrate-idle attribution are measured; the 3-plus-writer wall is a projection, untestable on two nodes.</em></p>
        </div>
      </details>

## Step 4 — Grading the student {#step-4-grading} {toc:Step 4 · Grading the student}

Now you check the student's work. Easy to give the test: replay a few hundred held-out recipe requests and collect the answers. Hard to grade fairly, and that is the entire story of this step.

{% flow %}
aria: Eval flow: test prompts hit the model, a keyword filter mislabels correct substitutions, and an LLM judge does the real grading.
node: Test | 579 held-out requests | replayed at the model
node: Cheap check | a keyword filter | trips on "replace the fish with tofu"
node slow: Slow part | an LLM judge tells a real violation from a correct swap | the actual grading
node: Out | a grade you can trust
caption: A keyword filter cannot tell a broken rule from a followed one, so the real work is **the judge**. The audit log writing underneath is trivial.
{% endflow %}

The cheap way to grade is a keyword filter: scan for animal-product words and flag any recipe that contains them. It falls apart immediately. It flags "replace the fish with tofu" as a meat violation, when that is exactly the correct vegan substitution. A keyword cannot tell a rule being broken from a rule being followed.

And the model's mistakes are subtler than a filter can catch. Sometimes it slips a dairy ingredient into a "vegan" dish by name, a vocabulary slip. Sometimes it genuinely believes seafood counts as vegetarian, which is a belief problem, not a wording problem, and the two need different fixes. Telling a real violation apart from a correct substitution takes a second model acting as a judge. That judging, the thinking, is the actual work of this step. The disk was never in the conversation.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p><strong>579</strong> held-out prompts at concurrency 64. Storage picture was uneventful and that is the finding: prefix cache <strong>83%</strong> hit, KV cache peaking at <strong>single-digit percent</strong> of budget (~5.5%), audit logging at <strong>4 KB/s</strong> at full fidelity. Nothing near a storage constraint. The real serving ceiling is the KV-cache budget, which is a memory question, not a storage one. Where it flips: audit volume grows linearly and stays trivial well past home scale; at compliance scale the storage angle is durability and retention (versioned, immutable, content-addressed eval sets and retained traces), not bandwidth. <em>Measured at home-scale traffic; production-rate audit volume is a projection from the linear write rate.</em></p>
        </div>
      </details>

## Step 5 — The 106-second start-up that wasn't the disk {#step-5-startup} {toc:Step 5 · The 106-second start-up}

Last step: put the model online. This stage holds the most useful practical lever in the whole project. Starting the server took 106 seconds, and the natural assumption is that it spent that time reading the model off disk. Picture a moving truck full of boxes with twenty movers standing around, and one of them carrying the boxes inside, one at a time, while the other nineteen watch. That is what was happening.

{% flow %}
aria: Serving flow: a one-time cold load that is the whole story, then per request the model writes the recipe token by token.
node slow: Once, at start-up | cold load: 106 s by default, 3 s with a parallel loader | one CPU core vs. all of them
node: Per request | the request comes in | tokenize, read the prompt
node model: Per request | writes the recipe, one token at a time | the memory wall again
node: Out | the recipe | ~269 tokens
caption: Almost all the cost that matters is in the first box: a one-time start-up that was **one core doing a parallel job alone**. After that, steady-state speed is the memory wall again.
{% endflow %}

During that 106-second start-up, exactly one processor core was pinned at full tilt while nineteen others sat idle, and the disk barely ticked over. The default loader unpacks the model one piece at a time on a single thread. I changed one setting to a loader that unpacks all the pieces in parallel, and the start-up dropped from 106 seconds to about 6, then to about 3 with a different one. Same model, same bytes, same disk. A 14-to-36-times speedup, and I never touched storage. The proof it was never the disk: warming the cache first changed nothing at all.

But this step is also where the disk finally gets its moment, and it is worth seeing why. "The disk did not matter" was true only because the slow loader was too slow to stress it. The instant you put in a fast loader, it reads the disk at nearly full speed, and now the disk is the next thing in line to be the bottleneck. Put the model on a slower networked drive and that fast loader would feel it immediately, while the old slow loader never would have noticed. The disk was not innocent by law. It was innocent because nothing was asking enough of it yet.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p>Cold-loading the <strong>15.27 GiB</strong> base weights with vLLM's default loader: ~<strong>106 s</strong>. A one-line <code>--load-format</code> change, same bytes, byte-identical output:</p>
          <table>
            <thead><tr><th>Loader</th><th>Cold load</th><th>vs default</th></tr></thead>
            <tbody>
              <tr><td><code>auto</code> (default)</td><td>~106 s</td><td>1x</td></tr>
              <tr><td><code>fastsafetensors</code></td><td>~6 s</td><td>18x</td></tr>
              <tr><td><code>runai_streamer</code></td><td>~3 s</td><td>36x</td></tr>
            </tbody>
          </table>
          <p>An independent reproduction, where the default loader landed faster at about 88 seconds, read 14 to 28x; the order-of-magnitude gap held.</p>
          <p>During the default load, one core pinned near 100% while the other 19 sat idle, and the NVMe peaked around <strong>0.5 GB/s</strong>, a few percent of a Gen5 drive (~0.14 GiB/s effective). Dropping the page cache first changed nothing: warm equals cold means the work is per-tensor materialization in Python, not disk reads. Once the CPU wall is gone, RunAI hit ~<strong>9.2 GB/s</strong> on a ~10 GB/s drive, and the storage tier re-enters as the next ceiling: a source slower than local NVMe would throttle the fast loaders, while the default loader is too slow to feel the disk at all. <em>The 18-36x and one-core signature are measured; the networked-source consequence follows from this lab's measured ceilings but was not run here.</em></p>
        </div>
      </details>

<div class="payoff">
  <div class="payoff-label">What she actually gets</div>

  <p>Back to the request at the very top. Here is the recipe the finished model wrote for my wife's exact words, "a vegan Punjabi curry with chickpeas and spinach, no coconut," served off the two machines in our house:</p>

  <div class="recipe-card">
    <h4>Vegan Punjabi Chickpea and Spinach Curry <span class="recipe-note">(it labeled this "Gobi Aloo Sabzi-style")</span></h4>
    <p><strong>Serves 2 to 3.</strong> 1 cup cooked chickpeas, 2 cups fresh spinach, 1 onion, 2 to 3 garlic cloves, 1 to 2 green chilies, 1 tbsp tomato paste, 1 tsp turmeric, 1 tsp garam masala, 1 tsp cumin seeds, 1 tbsp oil (sunflower or avocado), salt.</p>
    <ol>
      <li>Heat the oil, add cumin seeds, let them sizzle for ten seconds.</li>
      <li>Sauté the onion until golden, then add the garlic and green chilies for a minute.</li>
      <li>Stir in the tomato paste and cook two to three minutes until it thickens.</li>
      <li>Add the chickpeas, turmeric, and a splash of water; simmer five minutes.</li>
      <li>Add the spinach and cook until wilted, three to four minutes; stir in the garam masala and salt.</li>
      <li>Serve hot with rice or flatbread.</li>
    </ol>
  </div>

  <p>That is a real, servable curry: vegan, no coconut, chickpeas and spinach as asked. It is also where the honest part lives. Look at the title. "Gobi Aloo" is a cauliflower-and-potato dish, and this one has neither. That was not a fluke. Across five tries the student stamped a "Gobi Aloo" or "Gobi Palak" label on four of them, every time confident, every time wrong. It learned the house style of its training set, the habit of giving each dish a regional name, without learning the accuracy to make the name fit. The plain base model never did this; it just called the dish what it was. That is Step 4 again: the slow part was never the disk, it was the data and the judgment baked into it.</p>

  <p>The same shape shows up on the one rule I actually trained for. Tell the base model "no coconut" and it still reaches for coconut oil as a default cooking fat in four of five tries. The fine-tuned student is better, two of five, but better is not fixed. So the fine-tune did not buy me a better cook, my wife's phone still wins, and it did not buy me a reliable one either. What it bought was a partial improvement on the constraint, four in five down to two in five, plus the kitchen's house voice. That is the honest size of what a fine-tune onto an 8B student moves, worth knowing before you spend the GPUs.</p>

  <details class="for-eng">
    <summary>For engineers</summary>
    <div class="for-eng-body">
      <p>One prompt, one system message, temperature 0.7, seed 42, thinking disabled. Served as base Qwen3-8B plus the vegan LoRA adapter on a single vLLM server, where the request's <code>model</code> field selects base or fine-tuned. This is an illustrative sample, not a benchmark; the quantitative quality numbers belong to the eval, not to one generation.</p>
      <table>
        <thead><tr><th></th><th>Fine-tuned (LoRA)</th><th>Base Qwen3-8B</th></tr></thead>
        <tbody>
          <tr><td>Offered coconut oil despite "no coconut"</td><td>2 of 5 samples</td><td>4 of 5 samples</td></tr>
          <tr><td>Invented an inaccurate "Gobi" dish label</td><td>4 of 5 samples</td><td>never</td></tr>
          <tr><td>Register</td><td>plain recipe voice</td><td>generic assistant, emoji</td></tr>
          <tr><td>Length</td><td>~350 tokens</td><td>~580 tokens</td></tr>
        </tbody>
      </table>
      <p>Five seeds at temperature 0.7, hand-checked against the raw generations. The base offered coconut oil as a cooking fat in 4 of 5 (a fifth named coconut milk only to tell you to skip it, so it does not count); the fine-tune in 2 of 5. The fine-tune invented an inaccurate "Gobi" label in 4 of 5; the base never did. Small n, illustrative and hand-verified, not a benchmark.</p>
      <p>The serve command and the request driver ship in the pipeline's <a href="https://github.com/knachiketa04/aihomelab/tree/main/artifacts/concepts/llm-pipeline-on-a-workstation/reproduce/serve/" target="_blank" rel="noopener">serve kit</a>.</p>
    </div>
  </details>
</div>

## So was it ever storage? {#was-it-storage} {toc:So was it ever storage?}

Five steps, and the disk was idle at every single one. That idleness was the expected result, not a shock, and if you stopped there you would draw the wrong lesson from it: "storage does not matter." Two things are true at once. Every step <em>did</em> have a real bottleneck, it just lived in a different layer each time: the cleaning logic, the memory wall, the writers, the grader, one lonely CPU core. And there is a clear point where the disk does take over.

The disk flips from innocent to guilty in two ways. The first is configuration, and this part I measured directly: standing up the shared filesystem in my lab, the out-of-the-box settings were genuinely unusable until one knob fixed them. Default does not mean safe. The second is scale: at petabytes of data and production traffic, the disk becomes the line item that everything else waits on, and the project budget follows. That part I did not run, so I am calling it what it is, a reasoned projection, not data.

One meta-lesson sits underneath all five steps. A slow job that pins one processor core looks exactly like a disk problem from across the room, and twice here it was not: the model loader and the data cleaning made the same mistake look the same way. The dashboard you would naturally reach for, "how busy is the disk," could not tell a maxed-out disk from a coasting one. So the reusable result of the whole exercise is not "storage matters" or "storage does not." It is knowing <em>where</em> each layer flips, and reading the signal that actually knows instead of the one that is handy.

      <details class="for-eng">
        <summary>For engineers</summary>
        <div class="for-eng-body">
          <p>The whole pipeline, in one table:</p>
          <table>
            <thead><tr><th>Stage</th><th>Real bottleneck here</th><th>Measured / projected</th></tr></thead>
            <tbody>
              <tr><td>Data prep</td><td>application-layer ETL</td><td>flip projected</td></tr>
              <tr><td>Synthetic gen</td><td>GPU memory bandwidth, then the UMA allocator wedge</td><td>tier-independence measured</td></tr>
              <tr><td>Fine-tune (LoRA)</td><td>compute; adapter below the cache-eviction floor</td><td>flip projected</td></tr>
              <tr><td>Fine-tune (full-SFT)</td><td>writer concurrency and client latency; substrate idle</td><td>scaling measured, wall projected</td></tr>
              <tr><td>Eval</td><td>data quality and judge quality</td><td>measured at home scale</td></tr>
              <tr><td>Serve</td><td>single-thread CPU loader</td><td>loader measured, flips projected</td></tr>
            </tbody>
          </table>
          <p>The configuration flip is measured: default, untuned Lustre on this hardware was unusable until one knob recovered it. The scale flips draw on this lab's per-stage measurements plus the storage touch-points map, and are strictly qualitative projection. Sizing storage from <code>iostat %util</code> on a UMA, file-backed Lustre stack would lead you to buy bandwidth you do not need while the real bottleneck sits one layer up.</p>
        </div>
      </details>

## The invisibility trap — plan storage before it's the thing on fire {#invisibility-trap} {toc:The invisibility trap}

That idleness is also a trap. At prove-it-works scale, storage is invisible not because it is unimportant, but because the workload is <strong>too small to make it move</strong>. A 12.8 MiB corpus with 8B and 32B models cannot saturate a modern disk, so the defaults just work and storage never enters the conversation. That is exactly when teams decide it does not matter.

Storage being quiet did not mean storage was handled. It meant I had not reached the scale where it speaks up.

I did not run petabyte datasets or a serving fleet, so I will say it plainly: storage becoming the constraint at scale is the informed read from those per-stage flip points plus how these systems behave at volume, not something this home run proved. But the read is not subtle. The 46 GB save the writers paced becomes a synchronous-versus-asynchronous cadence question; the 4 KB/s audit stream becomes a retention line item; petabyte ingest waits on the filesystem ceiling. The layer that sat idle on my desk is where the budget goes.

So for any sizable build, treat storage as a <strong>first-class concern from day one</strong>. The cheapest time to design the data path is before you need it. The most expensive time is in production, under load, with it on fire.

The teams that get burned are not the ones who measured storage and got it wrong. They are the ones who never looked, because at the start it was invisible.
