---
title: The quiet bottleneck — when storage actually slows your AI down
subtitle: A field guide to when storage is innocent, and when it quietly stalls the most expensive hardware you own.
byline: Kumar Nachiketa · AIHomeLab · Personal capacity
author: Kumar Nachiketa
authorsub: AIHomeLab · personal capacity
date: 2026-06-07
datesub: Living document
reading: ~9 min
readingsub: Numbers tucked in the toggles
scope: Storage across the AI pipeline
scopesub: Plain-language; engineer depth on tap
slug: the-quiet-bottleneck
tags: Storage, AI infrastructure, LLM
description: Storage is usually not your AI bottleneck; the GPU or the network is. But when it does take over, you pay in idle accelerators. A plain-language field guide to when storage is innocent and when it is guilty, across data prep, training, and inference.
summary: Storage is usually quiet; the GPU or the network is your real bottleneck. But when storage does take over, it stalls the most expensive hardware you own. A field guide to when it is innocent and when it is guilty: one cool-to-hot gauge per pipeline stage, with the measured numbers tucked into "for engineers" toggles.
sourcenote: <strong>A note on sources.</strong> The measured figures here, the 14 to 36x loader speedup, the 6x page-cache variance, the 8B checkpoint size, come from real runs in my AIHomeLab. The broader framings are a storage practitioner's read, anchored to industry references (MLPerf Storage, NVIDIA's DGX SuperPOD architecture, Google Cloud's AI/ML storage guidance) rather than lab measurement alone, and each is labeled as such in the source. The full engineer map, every touch point, every citation, and the cold-vs-warm caveats, lives in the AIHomeLab artifact: <a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/storage-touchpoints-map/storage-touchpoints-map.md" target="_blank" rel="noopener">Storage Touch Points Across the AI Pipeline</a>.
---

Here is the uncomfortable thing about storage in an AI pipeline: most of the time, it is not your bottleneck. The graphics chips usually are, or the network. But the times storage does take over, it stalls the most expensive hardware you own, and you pay the bill in idle accelerators, the priciest line in any AI budget.

That asymmetry is the whole story. Get storage right and it stays invisible, which is exactly the goal. Get it wrong and the gap between the obvious choice and the right one runs from a few times to tens of times slower, with your accelerators sitting idle the entire time, waiting on data that is late.

So the useful question is not "is my storage fast enough," it is "when does storage actually matter, and when is it innocent." I will use one picture the whole way down: a gauge for how hard storage is working at each stage of building and running a model. Cool means storage is quiet and something else is the bottleneck. Hot means storage has taken over and your accelerators are idling. For each of the three stages, I will show where the needle usually sits, and exactly what pushes it into the red.

## Stage 1 — Data prep: getting the raw material ready {#data-prep} {toc:Data prep}

Before you cook, you wash, chop, and portion everything. Data prep is that step for a model: take raw web pages, logs, and files, and turn them into clean, uniform, bite-sized pieces the training loop can read in order. It moves more bytes than any other stage, and it is still usually not where storage becomes the bottleneck.

Here is why it moves so much. Every pass, clean it, filter it, label it, convert the format, tokenize it, reads the whole dataset and writes a fresh copy. A full pipeline rewrites the data five to ten times before the final version lands. That sounds like a storage problem, and at small scale it simply is not: the dataset fits in memory, or the cleaning logic works the processor harder than the disk.

{% flow %}
aria: Data prep flow: raw material is rewritten through several cleaning passes into a sharded dataset; the disk holds the copies, the real work is the logic, until petabyte scale.
node: Raw material | web pages, logs, files | many messy formats
node quiet: Storage | holds every intermediate copy | rewritten 5 to 10 times
node slow: Slow part | clean, label, tokenize | the logic, not the disk
node: Out | a sharded dataset | ready for training
legend: slow=the real slow part | model=the model doing AI work | quiet=storage, sitting quiet
caption: Storage moves the most bytes of any stage and is still rarely the bottleneck. It takes over only at **petabyte scale**, when the writes, the file count, and the storage bill become the constraint.
{% endflow %}

It flips hot at scale. When hundreds of workers write at once, the limit is their combined write bandwidth, not any single stream. When the data becomes billions of tiny files, the part of the system that tracks where every file lives, the metadata service, gives out long before raw bandwidth does. And once you are storing petabytes, the bill itself becomes the constraint: cold storage and hot storage differ about tenfold in price, so the real work is choosing tiers, not chasing throughput.

The honest version: a dataset under about 100 GB runs entirely in memory and storage barely registers. Heavy text cleaning saturates the processor first. A rate-limited source feed caps the whole pipeline at the front door, no matter how fast your disk is. If you are spending more time in worker compute than waiting on storage, scale compute.

<details class="for-eng"><summary>For engineers</summary><div class="for-eng-body"><p>Write-heavy and multi-pass: each clean / enrich / format / tokenize / shard pass reads the prior zone and writes a new one, so a full pipeline rewrites the dataset <strong>5 to 10x</strong> before final shards land. The ceiling is aggregate write bandwidth across many workers, not single-stream peak. Budget three capacity numbers, not one: the within-run working set (2 to 10x the final dataset, intermediates kept for restart), the final output, and cumulative yearly growth, which is the one most often under-budgeted. At scale the spend is dominated by tiering: object tiers (hot / nearline / cold / archive) differ about <strong>10x</strong> in price, and cross-region egress can cost more than the storage itself. Metadata is the quiet wall: tokenized text and per-image annotations can mean billions of small files, so file-create/list/stat rate hits the metadata service before raw bandwidth does; container formats (TFRecord, webdataset) contain it. <em>Descriptive framing here, anchored to industry patterns rather than a single lab measurement.</em></p></div></details>

## Stage 2 — Training: the part that periodically hits save {#training} {toc:Training}

Training is a long, expensive computation that saves its progress to disk every so often, so a crash does not cost you days. Think of a video game autosaving, or hitting save on a document you have worked on all week. Most of the time the saving is a rounding error against the real work, which is the graphics chips crunching numbers. The disk waits its turn.

On healthy hardware the graphics chips are the bottleneck by design: the storage tier is over-provisioned so it never gets in the way. The dataset streams in, the model updates, a checkpoint gets written on a schedule, and storage keeps up without trying.

{% flow %}
aria: Training flow: the dataset streams into the model, which periodically saves a checkpoint to disk; the graphics chips are the bottleneck and the disk waits, until one of four conditions flips it.
node: Dataset | streams in each pass | sequential reads
node model: The model | graphics chips crunch numbers | the real work
node quiet: Storage | saves a checkpoint on a schedule | waits its turn
node: Out | updated weights | saved so a crash is cheap
legend: slow=the real slow part | model=the model doing AI work | quiet=storage, sitting quiet
caption: The graphics chips set the pace and the disk waits. Storage takes over only when memory is tight, you save too often, you train across machines, or your inputs get very long.
{% endflow %}

It flips hot in four situations. When the machine is memory-constrained, the kind where the processor and graphics chip share one pool of memory, the model's working data and the disk cache fight over the same RAM. When you save very often, the write rate, not the math, sets your pace. When you train across several machines, they have to agree on each save, and that coordination is a tax you pay per checkpoint. And when your inputs get very long, the data read each pass approaches the size of RAM, and every pass goes disk-bound.

There is one subtle trap worth knowing even if you never touch the infrastructure. After a save, the just-written file usually lingers in the machine's fast cache. Re-read it right away, to repackage the model for serving, and it is instant. Let the cache get evicted first and the identical job takes six times longer. Same machine, same file, six-fold difference, decided entirely by whether the data was still warm. The dashboard you would naturally check cannot see that. You have to look one layer down.

The honest version: most full-precision training on a healthy shared filesystem is graphics-bound, full stop. Storage is over-provisioned and stays quiet. If none of those four situations describe your run, storage is not your problem.

<details class="for-eng"><summary>For engineers</summary><div class="for-eng-body"><p>The four regimes where storage takes over: (a) memory-constrained platforms (unified-memory / UMA, undersized cloud VMs, noisy multi-tenant nodes), where the page cache competes with the model's working set; (b) high-cadence checkpointing, where sustained write rate caps training throughput; (c) multi-node training, where shared-filesystem sync taxes land per checkpoint; (d) large-context fine-tuning, where the dataset working set approaches RAM and the loader goes I/O-bound every epoch. Sizes: an 8B full-SFT checkpoint lands around <strong>62 GB</strong> (sharded distributed-checkpoint form, plus consolidated deploy format, plus optimizer state, several times the parameter-only size); 70B+ pre-training checkpoints run to multiple TB per save. The page-cache coupling is the most mis-modeled part: re-reading a just-saved checkpoint to export a deploy format shows up to <strong>6x</strong> wall-clock variance depending on whether the write is still resident (the lab's 8B worked example). Planning anchors at production scale: NVIDIA's DGX SuperPOD H100 targets a ~<strong>40 GB/s</strong> GPUDirect Storage read floor per node, ~<strong>80 GB/s</strong> for the most demanding workloads.</p><p>Measured in the lab: <a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/training/full-sft-storage-touchpoints/full-sft-storage-touchpoints.md" target="_blank" rel="noopener">full-SFT touch points</a> (the 62 GB and the 6x), with the <a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/training/multi-node-training-storage/multi-node-training-storage.md" target="_blank" rel="noopener">multi-node trade-off</a> alongside. The SuperPOD figures are NVIDIA's published targets.</p></div></details>

## Stage 3 — Inference: opening the doors for service {#inference} {toc:Inference}

Serving a model is like running a restaurant. Once the kitchen is hot and orders are flowing, the disk is irrelevant: the work is the cooks (the graphics chips) and getting plates to tables (the network). Storage only matters at one moment, when you unlock the doors and load everything in.

Steady state is quiet. A warm, loaded model answering requests is limited by how fast the chips generate words and how fast the network streams them out. The disk sits idle.

{% flow %}
aria: Inference flow: a one-time cold load brings the model into memory, then it serves requests; the start-up bottleneck is the loader, not the disk, and steady state is graphics-bound.
node slow: Cold start | load the model into memory | the loader, not the disk
node model: The model | answers each request | graphics-bound
node quiet: Storage | idle once the model is warm | until the cache spills
node: Out | the reply | streamed to the user
legend: slow=the real slow part | model=the model doing AI work | quiet=storage, sitting quiet
caption: Slow start-up is the **loader**, not the disk: a parallel loader cuts it 14 to 36 times with no storage change. After that, storage stays quiet until long conversations spill the cache to disk, or logging outgrows its tier.
{% endflow %}

It flips hot in three places, and the first one is the most counterintuitive. When a server is slow to start, the disk is usually not the culprit. The standard loader reads the model on a single processor thread, so a faster disk does nothing; switch to a loader that reads in parallel and start-up drops by 14 to 36 times, with no change to the storage at all. The catch is the tell: once the fast loader removes that bottleneck, it reads the disk at full speed, so now a slow disk really would be the next thing in line.

The second is the model's short-term memory. As a conversation gets long, the working memory for the current request grows and spills out of the fast graphics memory, down to ordinary RAM, then to disk, each tier roughly ten times bigger and ten times slower. The third is logging: at scale, recording every request and reply can write as much as the model itself weighs per million requests, and it is the tier teams most often size too small.

The honest version: steady-state serving of a hot model is graphics-and-network-bound. Storage is not slowing you down.

<details class="for-eng"><summary>For engineers</summary><div class="for-eng-body"><p>Cold start is loader-bound, not tier-bound. The default safetensors loader moves weights sequentially on a single CPU thread (read to host, then copy to GPU), so a faster disk does not help; a streaming loader that parallelizes reads and overlaps the host-to-GPU copy does. Swapping to one (Run:ai Model Streamer, fastsafetensors) cut cold load <strong>14 to 36x</strong> with no tier change. The caveat: once the fast loader removes the CPU wall it reads near the NVMe ceiling, so on a slower source the tier becomes the next bottleneck. The KV cache (the model's per-request working memory) tiers across GPU memory, CPU RAM (~10x more capacity, ~10x lower bandwidth), and local NVMe (another ~10x), with hit rate at each tier setting GPU utilization. Audit logging at full fidelity can match or exceed the model's weight footprint per million requests for chatty workloads; it is the most-frequently-undersized serving tier. Steady-state serving of a hot model is GPU- and network-bound; storage is quiet.</p><p>Measured in the lab: <a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/inference/vllm-cold-load-loader-bound/vllm-cold-load-loader-bound.md" target="_blank" rel="noopener">vLLM cold load is loader-bound</a> (the 14 to 36x). The KV-tier and audit-log framings are descriptive, anchored to industry patterns.</p></div></details>

## So when does storage actually matter? {#when-it-matters} {toc:When it actually matters}

Step back and the three stages rhyme. Storage sits cool until a specific, knowable condition flips it hot: real scale (petabytes, fleets), constrained memory, saving too often, very long inputs, cold starts that happen a lot. None of those are mysteries. You can look at your workload and tell which apply before you ever buy a tier.

Two habits separate a real number from a marketing one. The first is to always ask: was the cache warm? The same operation measured cold and measured warm can differ five to twenty times, so a number without that context is not a number, it is a mood. The second is to remember that every storage tier has four different speeds: the datasheet, the sixty-second benchmark, the sustained rate, and what your actual workload gets, and the gaps stack. One measurement in my lab found a twenty-two-fold spread between the headline and the effective number. The obvious choice is not always the right one either: in one test, the "faster" network protocol came out 13 percent slower than the plain one for the specific write pattern. Measure your workload; do not inherit defaults.

And when storage is wrong, you rarely get a clean error. You get idle accelerators, the most expensive thing you own, quietly burning money while they wait. That is the asymmetry worth planning around: invisible when it is right, very expensive when it is wrong. The cheapest time to think about the data path is before it is the thing on fire.

If you want to watch this play out concretely, I built a full pipeline on two desktop machines and measured storage at every step. It went exactly as the map predicts: never the disk, right up until the one place it finally was. That story is [Storage stayed invisible the whole pipeline](llm-pipeline-on-a-workstation.html).

<details class="for-eng"><summary>For engineers</summary><div class="for-eng-body"><p>Cold vs warm is the single most useful framing question for any storage number: will the page cache, prefix cache, or GPU cache already be populated when the work happens? Mixing the two inflates published numbers <strong>5 to 20x</strong>. Spec-sheet vs ML-effective: every tier has a datasheet number, a 60-second synthetic-burst number, a sustained number (post-SLC for NVMe, post-cache for shared FS), and an ML-effective number (what the workload's access pattern actually gets); the gaps stack multiplicatively, with one lab decomposition landing a <strong>22x</strong> total gap across three components. The obvious choice is not always right: in one measured case, NFS-over-RDMA was <strong>13% slower</strong> than NFS-over-TCP for writes in the sync-export regime. GPUDirect Storage, where supported, removes the CPU bounce buffer and changes the "what dominates" answer for dataset streaming, cold load, and checkpoint restore. <em>Cold/warm and the 22x are measured (<a href="https://github.com/knachiketa04/aihomelab/blob/main/artifacts/concepts/data-prep/spark-nvme-fio-baseline/spark-nvme-fio-baseline.md" target="_blank" rel="noopener">NVMe baseline</a>); the RDMA result is from the multi-node artifact; GDS is descriptive.</em></p></div></details>
