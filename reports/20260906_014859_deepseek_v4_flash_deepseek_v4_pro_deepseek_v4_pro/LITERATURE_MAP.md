# LITERATURE_MAP
## Stress-Test Failure Attribution: Construction Loss vs Retrieval Loss in Long-Horizon Agent Memory

> **Immediate scope warning.** The 20 supplied papers target multimodal/hallucination benchmarks and medical/document/vision-language tasks. *None directly study long-horizon agents, episodic/working memory architecture, or failure attribution between construction and retrieval.* This map therefore (a) rates each supplied paper for indirect relevance, (b) extracts transferable benchmark/evaluation methodology, and (c) spells out the unresolved gaps that your research would fill. Direct claims about the target topic are marked with **unknown / not covered**.

---

## 1. Core Problem Definition

| Element | Statement |
|---|---|
| **Task context** | Long-horizon agent tasks require accumulating evidence/state across many steps or episodes and acting correctly at a *distant future time*. |
| **Memory pipeline** | The agent's useful experience is decomposed into two lifecycle phases: **construction** (perception → encoding → storage → summarization/consolidation) and **retrieval** (query formation → search/selection → ranking → integration into current context). |
| **Construction loss** | Information is lost or corrupted *before storage/encoding completes*: dropped details, wrong binding to timestamps/episode IDs, over-compression, no memory write triggered. |
| **Retrieval loss** | Failure occurs *after* storage: query fails to match relevant memory, wrong item surfaces, relevant memory is overwritten/decayed, or selected memory dilutes the context rather than disambiguating it. |
| **Stress-test requirement** | A test that forces *isolatable* failures on each side — e.g., same stored memory under different retrieval demands, or different construction quality under an identical retrieval probe. |
| **Failure-attribution goal** | Given an end-task error at time *t*, determine whether the root cause is at construction time *t0 < t* or retrieval time *t* — not merely “the agent forgot.” |

---

## 2. Direct Relevance Matrix of Supplied References

Each of the 20 papers is scored for indirect utility to this research question. Direct utility = **none** for all 20. Indirect utility is what follows.

| # | Paper (short) | Vehicle | Why it is (or is not) useful | Indirect relevance |
|---|---|---|---|---|
| [1] | BEAR-Bench | Enterprise/academic doc reasoning | Long, text-dense professional documents stress long-context reasoning; close to “retrieval over internally encoded documents,” but no agent memory loop, no attribution. | **Low** |
| [2] | HalluScope | Multimodal hallucination | Fine-grained hallucination diagnosis decomposes *where* a false output originates — an analogous attribution ambition, but within vision-language generation, not memory stages. | **Medium — methodological analogue** |
| [3] | PerceptionBench | Atomic visual perception | Isolates atomic capability failures; shows a decomposition strategy you can reuse for isolating memory subskills. | **Low-medium** |
| [4] | RESPClinBench | Clinical longitudinal decision-making | Longitudinal disease management requires accumulating patient history across encounters — conceptually nearest to “memory over time.” Yet no explicit construction/retrieval split. | **Medium** |
| [5] | Pathology VLM benchmark | WSI report generation | Whole-slide reasoning = long-context image understanding; shares the “information too large for one pass” problem underlying agent memory, but no memory stage separation. | **Low** |
| [6] | Per-Instance Disentangled Subspaces | Hallucination mitigation | Disentangling failure factors per instance is directly analogous to attributing a failure to one pipeline stage. | **Low-medium** |
| [7] | BioMed-Agent-RL | Clinical agents | An agentic RL approach to biomedical tasks: relevant to “agent” side but focuses on RL, not construction-vs-retrieval ablation. | **Low** |
| [8] | CARE | Medical VQA + CoT | Confidence-aware reasoning: when models reason about uncertainty, it may improve component-attribution, but no memory stress test. | **Low** |
| [9] | Context Blindness in DPO | Object hallucination | “Context blindness” is conceptually adjacent to retrieval loss — the model has context but fails to use it at generation time. | **Medium — conceptual bridge** |
| [10] | Disentangling Semantic Attention from Structural Bias | Attention manifold | Separates semantic vs structural failure influence on attention; a prescription for decomposing failures rather than an implementation. | **Low-medium** |
| [11] | Playing It Safe vs Faithfulness | LVLM hallucination mitigation | Warns that mitigation may reduce false positives without true faithfulness; alerts you to a pitfall if your retrieval intervention only makes the agent answer “I don’t know” more often. | **Medium — evaluation caution** |
| [12] | Dual-Stream Cross-Anchor Correction | Long-form captions, anchor limits | Long-form multi-object generation ties to “keeping multiple facts alive over time.” Weak tie to memory but useful for constructing long-horizon multimodal stress material. | **Low** |
| [13] | Multi-Turn Multimodal Diagnostic Reasoning | Progressive clinical reasoning | Multi-turn longitudinal integration — closest realistic setting for long-horizon agents failing from accumulation gaps, though not framed as construction/retrieval. | **Medium** |
| [14] | Fine-Grained Multi-Image Object Hallucination | Multi-image benchmark | Cross-image reasoning requires integrating facts across images — the *construction* analogue of binding information across inputs. | **Medium** |
| [15] | KnowHal | Knowledge-driven hallucination | Tests knowledge-driven errors: whether false output comes from missing knowledge vs misretrieved knowledge — same construction-vs-retrieval dialectic transposed to hallucinations. | **Medium** |
| [16] | LAVA | Financial doc auditing | Long document validation with high precision requirement; good example of a downstream task where construction loss vs retrieval loss would create distinct audit failures. | **Low** |
| [17] | Lost in Speech | Spoken hallucination | Multilingual, multi-channel input introduces a *modality-pair* that can dissociate memory trace quality from access; not agent-memory per se. | **Low** |
| [18] | MS-MFAD | Face anti-spoofing | Unrelated content-wise; benchmark design only. | **Very low** |
| [19] | OmniHandwritingOCR | Handwritten OCR pipelines | Document pipelines where poor encoding at OCR stage creates persistent, later “memory” errors — a toy analogue of construction loss upstream of retrieval. | **Low-medium** |
| [20] | Partition-Aware Unlearning | Spurious correlations in LVLMs | Removing spurious correlations via selective edits resembles memory surgery of agent scaffolds; but target is model weights not stored traces. | **Low** |

**Bottom line:** The current corpus is a multimodal-hallucination corpus. It can supply **stress-testing methodology, failure-mode decomposition, and evaluation cautions**, but supplies **zero direct evidence** on long-horizon agent memory construction-vs-retrieval attribution.

---

## 3. Evidence Synthesis: What the Supplied Papers Transfer to Your Research

Even without direct memory papers, you can appropriate several concrete ideas.

### 3.1. Decomposition of failure modes (from [2], [3], [10], [14])
- **HalluScope** ([2]) makes failure diagnosis fine-grained rather than binary. For your setting: attribution labels should be fine-grained — e.g., `construction_drop` vs `construction_probe_miss` vs `retrieval_miss_relevant` vs `retrieval_dilute_context`.
- **PerceptionBench** ([3]) isolates *atomic* capabilities. Analogy: build atomic memory micro-benchmarks rather than monolithic agent tasks:
  1. Write-then-answer-instant (isolates construction quality).
  2. Read-then-write-then-answer-delayed (isolates retrieval quality with identical stored trace).
- **Attention manifold disentangling** ([10]) — beware confounds between what a human judges as “retrieved fact salience” and what the model’s structural bias computes as salient.

### 3.2. Distinguish “safe abstention” from real fidelity (from [11])
This is the single most important caution for your evaluation:
- If a memory intervention reduces downstream error only by making the agent more conservative (saying “I don’t know,” refusing to act), it may look like retrieval improvement without any real memory change. 
- You therefore need a **failure-attribution metric that includes a false-negative vs false-positive classification** for retrieved memory use, not merely end-task accuracy.

### 3.3. Full-trace audit before final answer (from [2], [8], [15])
- Confidence-aware reasoning ([8]) and fine-grained hallucination audits ([2], [15]) suggest that instead of one end-to-end classifier on final output, log **intermediate memory traces** and audit them at two checkpoints:
  - **T0** right after memory construction (spoiler: inspect what is stored).
  - **T1** directly after retrieval but before final reasoning (spoiler: inspect what was surfaced).
- This two-spoiler design is the minimal architecture that lets you **attribute failure as construction vs retrieval**.

### 3.4. Longitudinal task scaffolding (from [4], [13])
RespClinBench ([4]) and multi-turn diagnostic reasoning ([13]) both demonstrate scoring schemes where correctness accumulates over turns. Adopt:
- **Cumulative state tracking score** that counts how much of a patient/main-agent “case” is correctly carried at any turn.
- This gives a natural longitudinal stress-test wrapper for constructing long-horizon memory tasks.

### 3.5. Multi-input binding (from [14])
Fine-grained multi-image object hallucination shows that false output arises when facts come from multiple inputs/objects. In long-horizon memory, construction loss often means the *cross-input binding* is missing — where an agent has memory of A and B but never creates the relation A→B. Your construction-loss stress tests should explicitly probe **relation memory**, not only fact memory.

---

## 4. Open Contradictions / Gaps in the Supplied Literature Relevant to Your Question

| Gap | Why it matters for your topic | Evidence status |
|---|---|---|
| No operational definition of “construction loss” vs “retrieval loss” in agent memory exists in [1]–[20] (or their abstracts). | You need to formalize this; the closest analogue is hallucination source diagnosis ([2], [15]), but it is not memory-stage attribution. | **Unknown / not covered** |
| No benchmark isolates construction from retrieval in a long-horizon task. | The corpus’s stress-test designs ([1], [3], [4], [14], [19]) stress models under input/context load, but never split the failure point by pipeline stage. | **Unknown / not covered** |
| No evidence on which stage **dominates** under stress. | The central empirical question is unanswered. | **Unknown / not covered** |
| Contradiction between “more memory always helps” and “context blindness” ([9]) | [9] shows context can exist yet be unusable at inference time — a retrieval-stage failure whose prevalence vs construction-level failures is unmeasured. This is a direct open contradiction your research can test. | **Medium-adjacent support** |
| Abstention masquerading as retrieval improvement ([11]) | If your future interventions have the “playing it safe” failure mode, any attribution you compute will be biased unless you add faithfulness-aware retrieval metrics. | **High-adjacent support** |

---

## 5. Evidence Confidence per Claim

| Claim | Confidence | Source basis |
|---|---|---|
| Supplied papers do not directly study long-horizon agent memory construction/retrieval loss. | **High** (from abstracts) | [1]–[20] |
| Stress-test benchmark design can be transferred from multimodal hallucination benchmarks. | **High** | [2], [3], [11] |
| Diagnostic-failure abstraction (fine-grained, per-instance) is a transferable methodology. | **High** | [2], [3], [10] |
| Context blindness in [9] is an existence proof that information placed in-context can still fail to be used — a form of retrieval-stage failure in a non-agent setting. | **Medium** | [9] |
| Construction is likely (but not proven here) the dominant source of loss at high input sparsity; retrieval likely dominates under memory scale/interference. | **Unknown — no evidence in corpus** | None |
| A model’s reduction of failure by abstention could confound retrieval-loss measurement. | **Medium-high** | [11] |
| Longitudinal medical benchmarks are proper stress containers for building long-horizon tasks. | **Medium** | [4], [13] |

---

## 6. What Must Be Validated Experimentally (Next Steps Design)

There is no existing evidence in your reference set for the following; each item is a required experiment for your research to make a claim.

### 6.1. Probe construction loss independently
- **Design:** At step *k*, after observing evidence E_k, force an immediate recall probe on E_k (zero delay). Any error is attributable to construction loss, since no retrieval from long-term memory is required.
- **Hypothesis:** Construction loss increases when (a) input is abstract/numeric, (b) input competes with adjacent items, or (c) instructions do not demand a memory write.

### 6.2. Probe retrieval loss independently
- **Design:** Fix the stored memory trace (so construction is held constant across conditions) and vary the query context, delay, and distractor suite at recall time. Any accuracy difference across query conditions at fixed trace quality is attributable to retrieval loss.
- **Hypothesis:** Retrieval loss rises disproportionately with (a) distractor similarity and (b) delay when overlap between memories is high, but **not** when memories are factually orthogonal.

### 6.3. Failure-attribution stress matrix
- Cross the two design dimensions:
  - **Stressors for construction:** compression budget, modality fragments, split attention, no explicit “memorize” prompt.
  - **Stressors for retrieval:** delay length, cue/word mismatch, scalar vs exact match, prefix-with-distractor, reward that discourages over-retrieval.
- Measure end-goal accuracy + stage-specific probes + faithfulness check. Use the two-spoiler audit described in §3.3.

### 6.4. Guard against the [11] confound
- Re-analyze errors that end with an abstention/“I don’t know” answer separately from “wrong confident answer” errors. Build the final attribution report treating these as distinct failure classes.

### 6.5. Add relation-memory probes (from [14])
- Include memory items that require *binding* A and B (e.g., “A arrived before B”) to separate relation-construction failures from pure fact drop.

### 6.6. Interventions that reverse-loss type at test time
Field | Constructed interventions | Evidence claim to support after running
|---|---|---
Construction-loss intervention | Re-ask the agent to re-encode compressed memories, add an “extra memory budget for relations”. | If performance improves after re-construction but same retrieval, validates construction-loss attribution.
Retrieval-loss intervention | Change retrieval query formulation, add multi-hop retrieval, reduce distractors at probe time, or combine memories before probing. | If performance improves after retrieval change but same stored trace, validates retrieval-loss attribution.

---

## 7. Recommended Short Supplement Reading List (Not in Supplied Set)
To directly ground the research question, before experimentation you will need literature on:
1. **Agent memory architectures** (e.g., MemGPT/Letta-style paging memory, generative agents, RAG-augmented controllers).
2. **RAG failure attribution** — has literature distinguishing retriever vs generator failure, though not long-horizon episodic memory.
3. **Prospective vs retrospective memory tasks** — classic cognitive-science analog that separates “forgot-to-do” from “forgot-information.”
4. **Temporal/memory interference in continual learning** — relevant to the construction-retrieval boundary.
5. **Stress-testing methodologies for agents** (StateFlow / SWE-bench-style long-task suites), since the corpus in hand is multimodal benchmark-centric.

---

## 8. Final Summary Map

```
Core question
   └─ Do long-horizon agent failures trace to storing information (construction) or to accessing stored information (retrieval)?
        └─ Current provided literature ([1]–[20]): NOT DIRECTLY ADDRESSED.

Adjacent evidence base
   ├─ Fine-grained failure decomposition for hallucinations → methodology (HalluScope [2], PerceptionBench [3])
   ├─ Context blindness → retrieval-stage failure analogue (Context Blindness in DPO [9])
   ├─ Longitudinal clinical multi-turn tasks → good stress containers (RESPClinBench [4], Multi-turn diagnostics [13])
   ├─ Evaluation caution: “plays it safe” can fake retrieved-fidelity gains (Reassessing LVLM Mitigation [11])
   └─ Multi-input binding benchmarks → construction probe ideas (Fine-Grained Multi-Image [14])

Missing evidence
   ├─ Direct benchmark for construction vs retrieval isolation in agents → must be designed
   ├─ Prevalence numbers for each loss type under various stress conditions → must be measured
   └─ Robust attribution metric that discounts abstention-style false gains → must be developed and validated
```

---

## 9. Provenance Note

All statements about the 20 supplied papers are derived from the abstracts given in the request. No full-text inspection was performed for this map, and none of the sources was retrieved via web. Statements about your research question, hypotheses, or the absence of evidence should be treated accordingly. Where evidence is absent, it is explicitly marked **Unknown / not covered** rather than inferred.
