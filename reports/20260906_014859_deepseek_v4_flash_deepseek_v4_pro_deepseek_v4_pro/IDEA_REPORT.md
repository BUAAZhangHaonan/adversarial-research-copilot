# IDEA_REPORT.md

## Framing used below

Stress-test attribution can be made directly measurable if we adopt **two spoilers**:

1. **Construction spoiler** — inspect the memory write at the moment it is produced (`t0`). A correct write followed by a later error means the loss occurred downstream of construction.
2. **Retrieval spoiler** — inspect retrieval output at the moment of recall (`t1`). A correct memory trace that is not selected / integrated correctly means retrieval loss.

The candidate ideas below all assume *inspected explicit memory* — e.g., agent writes structured/atomic records into an external store (dict, vector DB, notes file). This makes construction and retrieval observable, rather than treating memory as a hidden weight operation. If a project instead intends to study implicit/in-context memory, the attribution labels must be redefined, and most of these proposals become much harder.

---

## C1. Two-Spoiler Memory-Probe Battery (SIPS)

### 1. Hypothesis
An agent-memory failure can be assigned to construction or retrieval loss by comparing two within-run measurements: the quality of the memory record at write time and the success of retrieving/using that same record at query time. If the write is accurate but the query fails, that portion of the error is retrieval loss; if the write is inaccurate, that portion is construction loss — and this split is measurable, reproducible, and stress-sensitive.

### 2. Core mechanism
Treat explicit memory operations as observable stage logs:
- At step `k`, the agent reads evidence and writes one or more memory records.
- A **T0 auditor** compares the just-written record against the oracle ground truth of that evidence (facts, entities, timestamps, relations).
- Later, a **T1 auditor** runs a fixed, well-formed retrieval probe against the stored trace.
- An item that passes T0 and fails T1 is a retrieval loss. An item that fails T0 is a construction loss — regardless of T1.
This is the simplest operationalization of the construction/retrieval split, and every other candidate builds on it.

### 3. Why now
Existing benchmarks stress long-context understanding but never put a spoiler *inside the memory pipeline*. Agent scaffolding now routinely exposes write/read calls (Letta-style memory blocks, RAG stores, note-taking tools), making stage-level logging cheap and natural. The literature map’s own recommendation (§6.3) calls for this kind of stress matrix; nobody has published it for LLM agents.

### 4. Minimal experiment
Construct a synthetic long-horizon domain, e.g., 100 “cases” with ~40 events each: patients, deadlines, multi-step dependencies. Run an LLM agent with a simple external memory store.
- At each event, the agent writes memory entries.
- Immediately after write, evaluate T0: is the stored record faithful to the source event?
- At the end of an episode, evaluate T1: using the same stored record, can the agent answer direct factual probes?
- Stress by compression budget (summarize vs verbatim), instruction emphasis, delay length, and distractor count.
Report a 2×2 classification: `construction_ok ∧ retrieval_ok`, `construction_ok ∧ retrieval_fail`, `construction_fail ∧ retrieval_ok`, `construction_fail ∧ retrieval_fail`.

### 5. Main failure mode
If the T1 probe is badly worded, the experimenter labels natural language-ambiguity as memory failure. Fix by testing recoverability with several probe phrasings and by including a no-information control condition to disentangle “the agent guesses from priors” from “the agent actually retrieves.”

---

## C2. Fork-and-Fix Counterfactual Attribution (FFCA)

### 1. Hypothesis
End-task failure can be causally attributed to construction or retrieval by forking a failed episode and applying a **single-stage intervention**:
- **Construction-fix**: re-run from the failing point using a re-encoded (more faithful) memory trace, keeping retrieval unchanged.
- **Retrieval-fix**: re-run from the same failing point using the same stored trace, but with improved query/selection behavior.
If a construction-fix rescues the episode but a retrieval-fix does not, the root cause is construction; the opposite result implies retrieval.

### 2. Core mechanism
Modern agent runners allow checkpoints and replay: after an episode fails, create two counterfactual branches. On the **construction branch**, edit only the stored memory entries (e.g., replace a compressed summary with the ground-truth detailed entry) and then replay from some point before failure. On the **retrieval branch**, keep the memory store identical but change only the read step (e.g., provide better query phrasing, multi-hit retrieval, or a disambiguation instruction). The causal contrast is the difference in end-task success across branches.

### 3. Why now
LLM calls are deterministic enough under temperature-0 that branch replay is now viable; scaffolding systems with checkpoints make forking possible. In the supplied literature, no one has used counterfactual re-runs to attribute memory failures, even though the same logic underlies intervention studies in causal inference.

### 4. Minimal experiment
Use 30–60 step tool-using or planning episodes, plus a failure-prone long-horizon domain (e.g., itinerary planning, clinical case accumulation). For every failed episode:
1. Record the trace of memory writes.
2. For the construction-fix arm: replace the last `k` memory writes with oracle-faithful equivalents, replay only those steps, and measure end-task success.
3. For the retrieval-fix arm: keep the stored trace unchanged, but improve the retrieval step (e.g., an explicit “list all candidate memories before answering” system message), replay from the same failure point, and measure success.
To avoid stochastic noise, run each branch over ≥20 seeds and pre-register a rescue threshold (e.g., “construction-loss is supported if construction-fix rescues >20% more episodes than retrieval-fix”).

### 5. Main failure mode
Stage interventions are not perfectly pure: improving construction can change the text that retrieval later has access to, and improving retrieval can make a bad trace temporarily look fine. Detection strategy: add the two-spoiler auditor from C1 to confirm that the intended stage actually changed and the unintended stage stayed constant.

---

## C3. Memory Stressor Double-Dissociation Map (MSDDM)

### 1. Hypothesis
Construction and retrieval losses respond to different stressor families:
- Construction loss rises when encoding pressure increases (compression, ambiguous relation binding, low write instruction, split attention).
- Retrieval loss rises when read-time interference increases (delay, number of stored items, similar distractors, query paraphrase distance).
Under orthogonal stressors, these two curves can be empirically separated, producing a “when to fix which stage” decision boundary for agent builders.

### 2. Core mechanism
Measure stage-level error using C1’s T0/T1 spoilers across a systematically varied grid: drive construction stress while holding retrieval stress constant, then drive retrieval stress while holding the stored trace constant. If stage-specific error tracks its own stressor more strongly than the other stage’s, a double dissociation is demonstrated. This would be the first evidence that “the agent forgot” can be decomposed into two different stress responses rather than one blanket failure.

### 3. Why now
The central empirical claim of the topic — *which stage dominates under what stress?* — is still unanswered. The supplied literature provides a cautionary precedent: multimodal hallucination benchmarks show that monolithic failure rates hide distinct sub-failures, but no equivalent map exists for agent-memory stages.

### 4. Minimal experiment
Run a small \(3 \times 3\) pilot factorial first:
- Construction stressors (low/high): verbatim memory writes vs aggressive summarization.
- Retrieval stressors (low/high): immediate recall with few distractors vs delayed recall with many highly similar distractors.
For each cell, run the C1 probe battery, compute construction-loss rate and retrieval-loss rate, and fit a mixed-effects model with the two stressor factors as predictors. If the interaction is large or if the stressors cannot be manipulated independently, the design fails early and cheaply.

### 5. Main failure mode
If stressors are confounded — e.g., “more summarization” also makes retrieval harder because summaries are semantically farther from queries — the dissociation collapses. The pilot must verify orthogonality by holding the retrieval probe fixed while checking construction stress.

---

## C4. Behavioral Signature Attribution Without Trace Access

### 1. Hypothesis
Even when no T0/T1 trace is available — because the agent scaffold or API hides its memory internals — an attribution classifier trained only on observable behavior (tool calls, retries, timing, partial outputs, refusal language) can recover construction-vs-retrieval labels at better than chance, with balanced accuracy ≥0.60 on held-out episodes.

### 2. Core mechanism
Stage losses leave different behavioral fingerprints:
- Construction loss: the agent may confidently produce an answer that is wrong *early*; later steps may appear internally coherent but built on faulty premises; immediate follow-up questions also fail.
- Retrieval loss: the agent often shows signs of searching/scrolling/retrying, emits “I can’t find it” behavior, or asks itself clarifying questions even though the memory exists.
Train a simple classifier (logistic regression or gradient-boosted trees) on features extracted from agent logs, using labels generated by C1/C2 on a white-box scaffold. Then test the classifier on a black-box scaffold that exposes no internal memory trace.

### 3. Why now
Production agent APIs increasingly expose tool calls but not memory state. Benchmarks like HalluScope and PerceptionBench show that fine-grained failure labels improve over monolithic error rates; the same is true here. A behavioral-only attribution layer would be immediately useful to any team debugging memory failures inside a closed agent.

### 4. Minimal experiment
Generate 200 episodes from a white-box agent whose memory logs give ground truth (via C1 label definitions). Extract 15–30 behavioral features per episode (tool-call sequence, number of repeated reads, answer latency, token-level uncertainty words, final abstention vs wrong-confident answer). Train and 5-fold cross-validate. Then generate 100 episodes from a second, black-box scaffold and see whether the classifier transfers or needs domain adaptation.

### 5. Main failure mode
The classifier may learn scaffold-specific artifacts rather than true stage-loss signals — especially if the white-box and black-box agents have very different tool-call patterns. Detection: report transfer accuracy separately and include an ablation that removes scaffold-identity features.

---

## C5. Abstention-Adjusted Attribution Metric

### 1. Hypothesis
Standard end-task accuracy conflates true memory improvement with “playing it safe”: an agent that abstains more often may appear to have fewer memory failures without actually retrieving better. A stage-attribution protocol that does not separate wrong-confident from abstained answers will mislabel retrieval interventions as successful.

### 2. Core mechanism
Augment every stage probe with a confidence/abstention channel:
- Wrong-confident errors are counted as failure.
- Abstentions are counted separately, not as success.
Define an *honest rescue fraction*: the improvement in success rate among non-abstained answers, measured while matching the abstention rate across compared conditions. Use this metric to decide whether a construction or retrieval intervention truly helped or only made the policy risk-averse.

### 3. Why now
The literature map identifies this exact trap in the LVLM hallucination literature (“Playing It Safe vs Faithfulness”). Agent-memory papers will inherit the same confound unless the evaluation protocol is designed around it from the start.

### 4. Minimal experiment
Take a retrieval intervention that improves end-task accuracy. Compute (a) raw error rate, (b) abstention rate, (c) wrong-confident error rate. If the intervention reduces (a) primarily by increasing (b), classify it as an abstention artifact rather than retrieval improvement. Show that the artifact appears across at least two scaffolds.

### 5. Main failure mode
Abstention is sometimes legitimate: an agent may correctly refuse because the evidence is genuinely insufficient. The metric must therefore distinguish abstention with a good explanation from abstention as a dodge. This requires a secondary faithfulness check on the abstained utterances.

---

## C6. Delayed-Recall Failure Curve Decomposition

### 1. Hypothesis
If the stored trace is fixed, retrieval failure should increase with delay and memory-store size; if the trace itself is lost, retrieval failure should be high immediately after write. By fitting a delay curve, we can separate failure that exists at \(t=0\) (construction loss) from failure that grows over time (retrieval loss).

### 2. Core mechanism
Memory stores in LLM agents are usually external and unchanging — a summary written at step \(t\) does not physically decay. Therefore any *increase* in failure as the delay grows must come from the read side: more memories accumulate, interference increases, and the query must dig through a larger candidate set. If failure is already present at the first delayed probe and stays flat, the loss was baked into the stored trace at write time.

### 3. Why now
Cognitive-science forgetting curves are well established, but no one has mapped them onto the externally inspectable memory stores used by LLM agents. This is a low-cost way to make the construction/retrieval split dynamic rather than binary.

### 4. Minimal experiment
Create a corpus of 50 memory items. Store each as an identical atomic record, then probe retrieval at delays of 0, 1, 4, 8, 16, 32 intervening events. Hold the query formulation fixed and measure the probability of correct retrieval at each delay. Fit a monotone hazard model. A flat/high start implies construction loss; an upward slope implies retrieval interference.

### 5. Main failure mode
Delay is confounded with memory-store size: longer delays mean more competing memories. The model must explicitly include candidate-set size as a covariate or use a design where the store size is fixed while delay varies by shuffling non-memory filler steps.

---

## C7. Attribution-Truth Injection Test (Meta-Benchmark)

### 1. Hypothesis
Attribution protocols can be validated by injecting known single-stage faults: if the induction of a pure construction fault is not recovered as construction loss (and vice versa for retrieval), the protocol is invalid. Current attribution methods — including human read-throughs — will fail this oracle test substantially more often than their authors expect.

### 2. Core mechanism
Build episodes that are otherwise correct, then **inject one stage-specific fault**:
- Construction fault: delete/rewrite one memory record so that the stored trace no longer matches experienced evidence.
- Retrieval fault: change the retrieval query or the ranking step so that a correct record is not selected.
Because the injected fault is known exactly, it creates a gold label for the full episode’s failure cause. Run attribution methods (C1, C2, human audit, LLM judge) and measure their precision/recall against the gold label.

### 3. Why now
No standard exists for evaluating attribution itself. The supplied literature maps out failure taxonomies but never checks whether the taxonomies are recoverable by independent observers. This meta-benchmark is the missing validation layer for the whole research program.

### 4. Minimal experiment
Take 100 correct episodes from a synthetic long-horizon domain. Inject a construction fault in 50 and a retrieval fault in 50. Run three attribution approaches: two-spoiler logging (C1), counterfactual fork (C2), and a human/LLM audit of the final episode. Compute confusion matrices for each. Pre-register a detection criterion: any method must exceed 70% balanced accuracy on both fault classes.

### 5. Main failure mode
Injected faults may change the episode in ways that cascade into the “other” stage — e.g., deleting a relation record may make the agent start searching differently and thus also look like retrieval failure. Guard by checking that the injection only mutates the intended stage and by using the C1 auditor to verify cleanliness.

---

## C8. Relation-Binding Stress Test

### 1. Hypothesis
Relation memory — “A happened before B”, “X is the owner of Y” — is disproportionately lost at construction, while single-entity fact memory survives. A large fraction of long-horizon agent failures is not forgetting a fact but **breaking the binding** between facts during encoding.

### 2. Core mechanism
Separate memory items into:
- Fact-only items: “Alice is a patient.”
- Relation items: “Alice’s medication was started after Bob’s surgery.”
Probe fact recovery and relation recovery separately at T0 and T1. If relation items fail at T0 (write time) more sharply than fact items, construction is the binding bottleneck. Then stress the system by compressing memory or by adding more co-occurring relations; the construction loss should rise fastest for relation items. A natural follow-up intervention is to force the agent to write each relation as an explicit triple/edge rather than in prose.

### 3. Why now
The literature map explicitly flags cross-input binding as a construction-like failure source in multi-image tasks. Long-horizon agent research has yet to isolate binding failure inside memory pipelines. Because relational state is ubiquitous in domain tasks (patient timelines, file dependencies, multi-step plans), this stress test has high practical relevance.

### 4. Minimal experiment
Use a domain with 30 binary relations and 30 isolated facts. At write time, audit claim-by-claim: is the fact present? is the relation present? is the relation direction correct? Then at retrieval time, explicitly query both fact and relation. Statistically compare construction loss between item types under compression budgets of 10%, 30%, and 60%.

### 5. Main failure mode
Retrieval may also fail relation questions because the model does not know how to *query* a stored relation — e.g., it writes the right triple but asks a prose question that does not match. The T1 probes must be tested in multiple phrasings before concluding that construction is the locus.

---

## C9. Cross-Modal Memory Pipeline Attribution

### 1. Hypothesis
When the agent accumulates evidence from mixed modalities (text, tables, images, screenshots), construction loss will dominate over retrieval loss, because the frontier failure is modality-to-language encoding, not query-side access. Conversely, if the same evidence is provided as clean text, retrieval loss becomes the dominant term.

### 2. Core mechanism
Perception failure in multimodal agents — an image caption that misses a number, an OCR-ish transcription error, a chart whose axes are misread — happens early, before memory write. Once the wrong representation is stored, no retrieval improvement can fix it. Thus the measurable construction-loss rate should jump when the task becomes multimodal. This provides a clean bridge from the supplied multimodal-hallucination corpus into agent-memory research.

### 3. Why now
All 20 supplied papers are multimodal/vision-heavy; most agent-memory research still uses text-only synthetic tasks. There is an opportunity to be the first long-horizon memory benchmark that systematically manipulates modality at the construction boundary. Existing VLM hallucination taxonomies can be reused to label the perception errors that cause construction failures.

### 4. Minimal experiment
Run the same 50-episode long-horizon task in two conditions:
- Text-condition: all evidence delivered as clean text records.
- Mixed-condition: the same evidence delivered as screenshots, tables, and diagrams plus minimal text.
Audit T0 construction quality after each step. Hypothesis predicts a significant construction-loss gap between conditions, while T1 retrieval loss stays comparable when matched for content.

### 5. Main failure mode
Multimodal errors may not be memory errors at all — the model may simply be unable to perceive the image, and there is no “memory” yet. To make attribution meaningful, separate perception errors (no representation formed) from construction errors (representation formed but corrupted on writing) by requiring the agent to state its extracted evidence before writing to memory.

---

## C10. Prior-Knowledge Confound Control

### 1. Hypothesis
Some apparent memory construction losses are actually **prior-knowledge contaminations**: the model answers correctly from parametric prior knowledge, not from the stored trace — or answers incorrectly despite a correct memory because its prior conflicts with the evidence. Without controlling for priors, construction and retrieval loss rates are systematically mismeasured.

### 2. Core mechanism
Create memory items whose ground truth contradicts common sense or common benchmarks (“the capital of France is declared to be Lyon in this fictional world”). Run identical probes with and without any stored trace. If a fact is answered correctly when no memory exists, the model was not relying on the memory; if it is answered incorrectly even when the trace is present, the priors may have overridden retrieval. This gives a per-item “memory reliance” weight that can clean all downstream attribution estimates.

### 3. Why now
LLM agents are increasingly evaluated on tasks where their pretraining already knows much of the content. The construction/retrieval distinction becomes uninterpretable unless the benchmark controls for prior leakage. Existing hallucination papers isolate knowledge-driven failures, but no one has imported that control into agent-memory attribution.

### 4. Minimal experiment
Add 20 counterfactual/fictional facts to a long-horizon task. For each fact, run three conditions:
- No-memory probe (does the agent know the fact from priors?).
- Correct-trace probe (does the agent use the memory when it is present?).
- Wrong-trace probe (does a conflicting memory harm the answer?).
This produces an adjusted attribution matrix that separates true memory utilization from prior guessing.

### 5. Main failure mode
Fictional/counterfactual facts may make the task unrealistically adversarial — no real agent would need to remember “a fictional France”. Mitigate by choosing facts that are plausible but not in pretraining, e.g., synthetic names, novel relational rules, and fresh temporal schedules.

---

## Ranking

Scores reflect novelty, feasibility, falsifiability, and resource fit for an early-stage research effort within a moderately equipped LLM-agent lab.

| Candidate | novelty (1–5) | feasibility (1–5) | falsifiability (1–5) | resource fit (1–5) | total |
|---|---:|---:|---:|---:|---:|
| C1 — Two-Spoiler Probe Battery (SIPS) | 3 | 5 | 5 | 5 | 18 |
| C2 — Fork-and-Fix Counterfactual Attribution | 5 | 4 | 4 | 4 | 17 |
| C3 — Stressor Double-Dissociation Map | 4 | 4 | 5 | 4 | 17 |
| C4 — Behavioral Signature Attribution | 4 | 3 | 3 | 3 | 13 |
| C5 — Abstention-Adjusted Metric | 2 | 5 | 4 | 5 | 16 |
| C6 — Delayed-Recall Curve Decomposition | 4 | 4 | 4 | 4 | 16 |
| C7 — Attribution-Truth Injection Test | 4 | 3 | 5 | 3 | 15 |
| C8 — Relation-Binding Stress Test | 3 | 5 | 4 | 4 | 16 |
| C9 — Cross-Modal Pipeline Attribution | 3 | 3 | 4 | 3 | 13 |
| C10 — Prior-Knowledge Confound Control | 3 | 5 | 4 | 5 | 17 |

---

## Top Three Recommendations

### Top 3 rationale
The top three are not just the highest-scoring ideas; they form a **coherent research stack**:
