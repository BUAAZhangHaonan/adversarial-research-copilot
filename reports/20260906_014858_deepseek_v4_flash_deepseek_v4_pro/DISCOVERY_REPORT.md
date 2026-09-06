# DISCOVERY_REPORT

topic: memory architectures for LLM agents over long horizons: what breaks after 100 turns
field: memory mechanisms and failure modes in long-horizon LLM agent systems
generated_at: 2026-09-05T18:50:33.569432+00:00
models: {'generator': 'deepseek-v4-flash', 'judge': 'deepseek-v4-pro'}
pool: 1 gaps -> 1 kept -> 8 ideas -> 7 KEEP

## Verdicts

| id | dedup | delta type | incr.risk | separates alt.? | priority | verdict | kill evidence | reason |
|---|---|---|---|---|---|---|---|---|
| I3 | DISTINCT | new_boundary | 2 | True | 5 | **KEEP** | - | Factorial design cleanly separates horizon properties that existing work (2604.11978, 2606
...[clipped] |
| I1 | DISTINCT | new_boundary | 2 | True | 5 | **KEEP** | - | Adds the missing causal counterfactual to attribution work; TRAJDEBUG/Seeing the Whole Ele
...[clipped] |
| I5 | DISTINCT | new_boundary | 1 | True | 4 | **KEEP** | - | Cheap reminder baseline cleanly separates storage from attention; Memory-R2/FLARE lack thi
...[clipped] |
| I6 | DISTINCT | new_boundary | 3 | True | 4 | **KEEP** | - | Planner-strength control addresses a hidden variable in 2604.11978's attribution conclusio
...[clipped] |
| I8 | POSSIBLY_DUPLICATE | new_mechanism | 3 | True | 3 | **KEEP** | - | Three-arm budget test separates information availability from learned selection; MemDelta 
...[clipped] |
| I2 | DISTINCT | new_mechanism | 3 | False | 3 | **PIVOT** | - | The minimal test omits explicit state-update scoring, so the three-way decomposition is no
...[clipped] |
| I4 | POSSIBLY_DUPLICATE | new_boundary | 4 | True | 2 | **KEEP** | - | Useful moderation but close to MINTEval's existing gradient; risk of collapse into adaptat
...[clipped] |
| I7 | DISTINCT | new_problem | 5 | False | 1 | **KEEP** | - | Decision-relevant but likely collapses into representative-dependent bake-off; not mechani
...[clipped] |

## Kept problems (ranked, 7)

### #1 — Which property of a long-horizon task — raw trajectory length, number of distinct subgoals, or the distance between an early fact and its late use — actually determines when a no-memory long-context baseline loses to a memory-augmented agent?


- **id**: I3 | taste score: 5.0 | delta type: new_boundary
- **knowledge gain**: If only cross-referential distance causes the memory/no-memory crossover, long-horizon is an ill-posed target; if no factor crosses, the no-memory advantage is structural under current baselines.
- **decision changed**: Memory/context teams would target specific task factors instead of treating long-horizon as a coherent regime.
- **dedup verdict**: DISTINCT | delta: Work in arXiv:2604.11978 established memory limitation is only a minority of long-horizon failures under existing benchmarks; the candidate examines whether factorially varying trajectory length, number of subgoals, and cross-referential distance changes that conclusion; the added value is a control
...[clipped]
- **gap evidence**: [2606.24775] finds a no-memory long-context baseline wins DB-Bench EM; [2604.11978] reports memory limitation is only a minority of long-horizon failures; no pool paper orthogonally varies these horizon properties.

- **who needs it**: Memory-research agenda setters and context-engineering teams deciding whether "long horizon" is even a coherent target for memory systems.

- **why now**: Long-context windows only recently became large enough to serve as viable no-memory baselines, so the crossover between context availability and task structure is now experimentally reachable.

- **minimal falsifiable test**: On a synthetic long-horizon task family, factorially vary total length,
number of subgoals, and cross-referential distance while holding semantics
fixed; compare one memory agent against one no-memory long-context baseline.
Only a factor that produces a reliable crossover licenses calling that factor
a "memory-needed" regime.

- **anti-scope**: Not a proposal for a hybrid context-memory system and not a large model-family sweep; not a new long-horizon benchmark.

- **judge reason**: Factorial design cleanly separates horizon properties that existing work (2604.11978, 2606.24775) conflates.

### #2 — When end-to-end failure attribution says planning and instruction errors dominate, what fraction of those errors would disappear if an otherwise identical agent had oracle-perfect memory at every decision point?


- **id**: I1 | taste score: 5.0 | delta type: new_boundary
- **knowledge gain**: If oracle memory leaves attributed planning/instruction failures unchanged, memory misses are causally irrelevant to planning-dominant taxonomies; if failures shift, those taxonomies overstate planning and understate memory.
- **decision changed**: Failure-attribution tools would add memory-oracle counterfactuals before quoting planning-dominant shares as evidence against memory investment.
- **dedup verdict**: DISTINCT | delta: Failure-attribution work such as TRAJDEBUG, Seeing the Whole Elephant, and Semantic Cooperative Games established how to locate responsible steps/agents under the agents' natural memory conditions; the candidate examines whether replacing memory with an oracle at every decision point changes the att
...[clipped]
- **gap evidence**: [2604.11978] attributes most long-horizon failures to planning, with memory limitation a minority; [2608.15008] finds memory retrieval quality does not transfer to ALFWorld planning success; [2606.24775] finds a no-memory long-context baseline wins DB-Bench EM.

- **who needs it**: Failure-attribution tool builders and research agenda setters who currently quote planning-dominant taxonomies as evidence against memory investment.

- **why now**: Failure-diagnosis suites now produce replayable trajectories with state annotations, making oracle-injection counterfactuals cheap on hundreds of tasks instead of a manual case study.

- **minimal falsifiable test**: Replay 100 failed trajectories from a long-horizon diagnosis suite with the
same LLM/planner, but inject ground-truth task-relevant facts wherever the
agent would consult memory. If the success rate and error mix barely change,
attributed planning/instruction failures are not downstream of memory misses;
if failures shift to memory errors, the original attribution overstated planning.

- **anti-scope**: Not a new memory architecture or a full failure taxonomy; not a deployment study of any memory system.

- **judge reason**: Adds the missing causal counterfactual to attribution work; TRAJDEBUG/Seeing the Whole Elephant do not inject oracle memory.

### #3 — In long-horizon agents that fail to obey early instructions, is the failure a memory-storage deficit, or is it a context-attention deficit that a trivial stepwise instruction-reminder baseline eliminates without any memory architecture change?


- **id**: I5 | taste score: 4.0 | delta type: new_boundary
- **knowledge gain**: If stepwise reminders erase instruction errors, the deficit is attention/context, not storage; if the memory system is necessary, storage remains involved.
- **decision changed**: Memory-architecture pitches would have to distinguish storage deficits from attention deficits before claiming the agent forgot instructions.
- **dedup verdict**: DISTINCT | delta: Memory-R2 and adjacent memory-augmented agent work established that long-horizon instruction adherence can be improved by storing and reusing information in memory; FLARE established that some long-horizon planning failures are non-memory reasoning failures. The candidate examines whether a no-memor
...[clipped]
- **gap evidence**: [2604.11978] attributes many long-horizon failures to instruction-following and planning errors rather than memory; memory papers in the pool (e.g., [2606.06448], [2601.09913]) treat holding instructions across long horizons as a memory problem.

- **who needs it**: Memory-architecture teams whose pitch includes "the agent forgot its instructions" and instruction-following evaluators who score adherence as if it measured memory.

- **why now**: Today's large context windows make a stepwise reminder baseline cheap to run on complete trajectories, cleanly separating storage from attention for the first time.

- **minimal falsifiable test**: Compare on a long-horizon suite whose failures include instruction violation:
(a) the same agent plus an external memory system, and (b) the same agent plus
a one-line re-statement of the original instruction every K steps, with no memory
change. If (b) closes most instruction-related errors, those failures were not
memory-storage failures.

- **anti-scope**: Not a prompt-engineering paper and not a deployment recommendation for reminders; not a test of memory capacity in general.

- **judge reason**: Cheap reminder baseline cleanly separates storage from attention; Memory-R2/FLARE lack this ablation.

### #4 — If planning capability is sharply increased via a reasoning-tuned LLM, does the remaining long-horizon failure mix shift toward memory errors — making memory the true bottleneck only after planning is solved?


- **id**: I6 | taste score: 4.0 | delta type: new_boundary
- **knowledge gain**: If stronger planning does not make memory-error share dominant, memory is not automatically the next bottleneck; if it does, the planning-dominant attribution is planner-dependent.
- **decision changed**: Agenda setters would prioritize memory based on planner strength rather than current failure shares.
- **dedup verdict**: DISTINCT | delta: [2604.11978] established that planning errors dominate long-horizon failures under current planners, and DeepSeek-R1 showed RL reasoning training improves planning; the candidate examines whether upgrading the planner to a reasoning-tuned LLM changes that failure-attribution conclusion; the added va
...[clipped]
- **gap evidence**: [2604.11978] reports planning errors dominate long-horizon failures; [2501.12948] shows RL reasoning training can improve planning/reasoning; no pool paper asks whether the memory-vs-planning failure share changes after such a planner upgrade.

- **who needs it**: Research agenda setters deciding whether to invest in memory now, or to wait until stronger planners expose memory as the next bottleneck.

- **why now**: Reasoning-tuned LLMs (R1-style) are now public and cheap enough to drop into the same agent/memory stack, making planner strength a controlled variable instead of a fixed property of the field.

- **minimal falsifiable test**: Run the failure-attribution protocol of [2604.11978] with the same memory system
under two LLMs matched except for RL reasoning training. If the memory-error share
stays below the planning share under the stronger planner, memory is not the next
bottleneck; if it becomes dominant, the stale-premise diagnosis is planner-dependent.

- **anti-scope**: Not a claim that planning is solved and not a new planner or training run; not a full diagnosis-taxonomy redesign.

- **judge reason**: Planner-strength control addresses a hidden variable in 2604.11978's attribution conclusion.

### #5 — When a full-transcript no-memory long-context baseline already beats memory agents, is the active ingredient full information-in-context, and under hard context limits does selective memory outperform a random-truncation baseline?


- **id**: I8 | taste score: 3.0 | delta type: new_mechanism
- **knowledge gain**: If random truncation matches learned selective memory, learned selection is not the active ingredient; if learned matches oracle summary, the active ingredient is placing right items in context, not the memory mechanism.
- **decision changed**: Selective-memory papers would report random-truncation and oracle-summary arms before claiming learned-policy value.
- **dedup verdict**: POSSIBLY_DUPLICATE | delta: Work MemDelta established that agent-memory evaluation gains often mix memory-method changes with LM/embedding/retrieval changes, and Engram established learned memory can beat full-context under some conditions; the candidate examines whether a hard context budget changes that conclusion by compari
...[clipped]
- **gap evidence**: [2606.24775] finds no-memory long-context wins DB-Bench EM; [2605.30785] learns context management; [2601.09913] and [2601.06377] propose memory architectures; no pool ablation separates the value of information availability from the value of learned selection.

- **who needs it**: Selective-memory and context-management researchers deciding whether their learned selection policy is the active ingredient or a costly artifact.

- **why now**: No-memory full-transcript baselines and learned context-management systems are both mature enough to compare head-to-head under the same context-budget constraint, which was not possible when context windows could not hold full transcripts.

- **minimal falsifiable test**: On a DB-Bench-like suite where full-transcript long-context already wins, impose a
context budget smaller than the transcript and compare: (a) a selective/learned
memory agent, (b) a random-truncation long-context baseline, and (c) the same budget
with an oracle one-line summary. If (b) approximates (a), learned selection is not
the active ingredient; if (a) approximates (c), the active ingredient is placing the
right items in context, not the memory mechanism.

- **anti-scope**: Not a new summarizer or learned memory policy and not a new long-context model; not a full evaluation of memory architectures.
- **judge reason**: Three-arm budget test separates information availability from learned selection; MemDelta only partially overlaps.

### #6 — Is the advantage of a memory architecture over a full-transcript no-memory agent concentrated in multi-target interference settings, rather than in long-horizon tasks generally?


- **id**: I4 | taste score: 2.0 | delta type: new_boundary
- **knowledge gain**: If memory advantage is flat across an interference gradient, multi-target interference is not the trigger for memory intervention; if it grows, memory investment can be justified on interference grounds.
- **decision changed**: Benchmark designers would stop citing multi-target interference as a generic memory motivation and condition on interference level.
- **dedup verdict**: POSSIBLY_DUPLICATE | delta: MINTEval established multi-target interference as a memory stressor, while DB-Bench and ALFWorld evidence suggests memory advantage is not universal in long-horizon or planning settings; the candidate examines whether varying the number of interleaved goals from 1 to 8 changes the selective-memory v
...[clipped]
- **gap evidence**: [2605.18565] constructs MINTEval around multi-target interference as the memory stressor; [2606.24775] finds no-memory long-context beats memory on DB-Bench; [2608.15008] finds retrieval gains do not transfer to ALFWorld planning success.

- **who needs it**: Benchmark designers and memory teams who cite multi-target interference as the primary motivation for memory architectures.

- **why now**: Multi-target interference is now an isolable, manipulable variable in released suites, whereas earlier long-horizon benchmarks conflated interference with elapsed time and goal count.

- **minimal falsifiable test**: On an adapted MINTEval-style suite, hold the base model fixed and vary only the
number of interleaved goals per session (1 to 8); compare a selective-memory
agent against a full-transcript no-memory baseline. If the memory advantage is
flat or absent across the interference gradient, interference is not the trigger
that makes memory the right intervention.

- **anti-scope**: Not a new multi-target benchmark and not a general memory-vs-replanning contest; not an architecture proposal.

- **judge reason**: Useful moderation but close to MINTEval's existing gradient; risk of collapse into adaptation.

### #7 — At equal added inference cost, which intervention cluster buys the largest end-to-end success gain on the same long-horizon suite: a memory substrate, a planning wrapper, or instruction/context engineering?


- **id**: I7 | taste score: 1.0 | delta type: new_problem
- **knowledge gain**: If one intervention cluster dominates at equal cost, allocation gets an empirical effect-size ordering; if none does, no cluster is privileged under current canonical choices.
- **decision changed**: Funders and lab leads would switch from cluster-faith prioritization to cost-matched effect sizes.
- **dedup verdict**: DISTINCT | delta: MemBoost and budget-control work established that memory reuse and explicit budget allocation each affect cost-limited performance under serving/search workloads; the candidate examines whether holding added inference cost equal across a memory substrate, a planning wrapper, and instruction/context 
...[clipped]
- **gap evidence**: [2608.15008] memory-substrate gains do not propagate to ALFWorld planning success; [2606.24775] a no-memory long-context baseline wins DB-Bench EM; [2604.11978] planning errors dominate; the pool lacks any matched-cost comparison across clusters.

- **who needs it**: Lab leads, funders, and platform teams allocating research effort across memory, planning, and instruction-following lines of work.

- **why now**: Each cluster now has canonical, off-the-shelf interventions (existing memory substrates, self-consistency/backtracking wrappers, instruction anchoring), so a matched-cost effect-size comparison no longer requires building three research systems.

- **minimal falsifiable test**: On one long-horizon agent suite with one base model, apply one pre-registered
canonical intervention from each cluster at a similar added token/latency budget
and measure end-to-end success. If a planning or instruction intervention delivers
more than half the memory gain at less than half the cost, agenda spend should shift.

- **anti-scope**: Not a benchmark bake-off of three new systems and not an LLM-systems cost study; the three interventions must already exist before the test starts.

- **judge reason**: Decision-relevant but likely collapses into representative-dependent bake-off; not mechanism-revealing.


## Killed / pivoted

- **I2** (PIVOT): When retrieval quality improves without improving end-to-end success, at which subgoal does good recall fail to change behavior — recalling the fact, using it to update state, or selecting the next action?
 — The minimal test omits explicit state-update scoring, so the three-way decomposition is not actually falsified.

## Evidence base

deep-read papers: 12
- [2604.11978] The Long-Horizon Task Mirage? Diagnosing Where and Why Agentic Systems Break (None, 2026)
- [2605.18565] MINTEval: Evaluating Memory under Multi-Target Interference in Long-Horizon Agent Systems (None, 2026)
- [2602.16901] AgentLAB: Benchmarking LLM Agents against Long-Horizon Attacks (None, 2026)
- [2501.12948] DeepSeek-R1 incentivizes reasoning in LLMs through reinforcement learning (Nature, 2025)
- [2606.24775] Are We Ready For An Agent-Native Memory System? (arXiv.org, 2026)
- [2606.06448] Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads (CoRR, 2026)
- [2605.30785] Learning Agent-Compatible Context Management for Long-Horizon Tasks (None, 2026)
- [2608.15008] Harness the Memory: A Holistic Evaluation of Memory Substrates in Memory Agents (None, 2026)
- [2604.26622] OCR-Memory: Optical Context Retrieval for Long-Horizon Agent Memory (Annual Meeting of the Association for Computational Linguistics, 2026)
- [2602.06052] A Survey of Agent Memory in the Second Half: Towards Self-Evolving and Long-Horizon Agents (arXiv.org, 2026)
- [2601.09913] Continuum Memory Architectures for Long-Horizon LLM Agents (None, 2026)
- [2601.06377] HiMem: Hierarchical Long-Term Memory for LLM Long-Horizon Agents (None, 2026)
