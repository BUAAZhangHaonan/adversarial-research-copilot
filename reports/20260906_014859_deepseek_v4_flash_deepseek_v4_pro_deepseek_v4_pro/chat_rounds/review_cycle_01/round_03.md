# Round 3 (cycle 1, inner 3)

time: 2026-09-05T18:13:04.627969+00:00 -> 2026-09-05T18:15:32.227252+00:00

decision(raw/effective): STOP_CONVERGED / STOP_CONVERGED

## Proposer
The core mechanism has been stable since round 1: attribute memory failures by causal divergence between construction and retrieval, made observable through fault injection rather than trace reading. The two open issues are definitional and sequential, and both yield to the same discipline — restrict automated attribution to cases where the counterfactual is actually observable, and make "unattributable" an explicit output class rather than force-fitting every failure into a binary.

On [O1], "had the needed fact" becomes "certified availability." A fact is certified available in working context if it appears explicitly in the window *or* if a probe model, shown only that window, recovers the decision-relevant value in a forced-choice cloze above a confidence threshold — this covers paraphrase, entailment, and distributed facts (e.g., "K⁺ 5.1" → the hyperkalemia state) under one operational rule. Facts that fail certification are marked unattributable. This is not an oracle smuggled back in; it is a conservative gate. The risk is asymmetric — false negatives only push cases to the unattributable bucket, while false positives pollute the label set — so before trusting the probe, validate it against human annotation on a ~100-slice sample. The open question about probe prompts leaking the answer is real, but the agreement check resolves it early; if agreement falls below ~90%, fall back to explicit-occurrence-only certification for pilot round one.

On [O2], first-divergence ordering is too weak because co-occurrence is two boolean events, not one. Replace ordering with sufficiency testing on the failure instance. Paired injection step 1: replace the agent's actual memory writes with gold writes at construction time — but the gold trace must be a projection of the observed working context at time *t*, never an enriched answer key, or we conflate "failed to persist" with "was handed extra evidence." If outcome flips to success, label construction-only: fixing construction suffices for this failure instance, regardless of latent retrieval bugs. If it still fails, step 2: also swap the retrieval read for a permissive top-k lookup over the gold memory. If that flips to success, label both, retrieval as the residual cause; if neither flips, attribute elsewhere. This converts the Skeptic's counterfactual into the decision procedure itself.

The fastest executable test is a three-condition microbenchmark on one long-horizon tool-use task: baseline, gold construction, gold construction plus gold retrieval. The delta between conditions 2 and 3 is the marginal retrieval fault rate; the delta between 1 and 2 is construction. That is roughly a day of scaffolding on an existing agent harness. The one edge I still need sharpened is not the mechanism but the certification probe's boundary conditions — specifically whether distributed facts require multi-hop cloze prompts, which risk becoming as complex as the task they diagnose. The 100-slice human-agreement check is the cheapest way to cut that knot before the pilot commits.

## Skeptic
The weakest link is no longer the first-divergence ordering, but the incomplete two-intervention design. You state step 2 swaps retrieval for “a permissive top-k lookup over the gold memory,” and the microbenchmark runs only baseline, gold construction, and gold construction + gold retrieval. That sequence identifies retrieval as a residual cause only after construction has been intervened on. It cannot distinguish “construction faulty and retrieval also faulty” from “retrieval solely faulty, actual memory already sufficient.” The failure mechanism is straightforward: if the agent wrote the needed fact but its read path is too selective, step 1 (gold writes, actual retrieval) still fails because the retrieval bug is untouched; step 2 (gold writes + permissive retrieval) then succeeds, and your rule labels both. Construction gets blamed for a failure it did not cause. This is not an edge case—it is the canonical retrieval-only failure.

Two concrete failures follow. (A) Memory contains K⁺ 5.1 with a high-confidence key, but top-k retrieval returns a later distracter; baseline fails. Gold construction normalizes the K⁺ fact; actual retrieval still misses due to the same threshold, so step 1 fails. Step 2 flips. Labeling “both” is wrong. Add a fourth arm: permissive retrieval over the agent’s actual memory, with no construction change. If that flips, label retrieval-only. Without it, construction fault rate is biased upward. (B) The O1 probe still has a response-format leak: forced-choice cloze can certify availability from parametric prior rather than context. A probe shown “K⁺ 5.1, peaked T waves” may answer “hyperkalemia” even if the agent never integrated those cues; human annotators may share the same prior, so the 100-slice agreement check will not detect it. Use query-blind generation/entailment scoring plus a small adversarial set where priors conflict with context. Minimum evidence: a 2×2 attribution matrix across the four arms, and probe entailment agreement rather than label agreement alone.

Before pilot investment, add the fourth arm and re-run the microbenchmark. This is low-cost and directly fixes the mislabeling. Also specify gold projection as query-blind, and emit “unattributable” when independent projections disagree. If retrieval-only failures are frequent in the 2×2 matrix, the current three-arm construction attribution is invalid. The core injection mechanism is sound; these two fixes are the remaining blockers.

## Moderator
**Current best judgment.** The core mechanism remains sound: causal attribution via fault injection is the right frame, and the Proposer’s shift from first-divergence ordering to sufficiency testing on the failure instance resolves the earlier co-occurrence ambiguity. The certification gate for [O1] is also defensible, with the 100-slice human-agreement check as a correct early stop. However, the Skeptic’s fourth-arm objection is decision-relevant and not a rehash. The proposed three-arm design (baseline, gold construction, gold construction + gold retrieval) cannot separate “construction faulty and retrieval faulty” from “retrieval solely faulty, memory already sufficient.” Without a permissive-retrieval-over-actual-memory arm, construction fault rates are biased upward, which would corrupt the pilot’s primary output. This is a real experimental-design flaw in the core attribution procedure, not an edge case.

**Why stopping.** The remaining issue is resolvable only by running the corrected experiment, not by further debate. There is no conceptual dispute left: both sides agree the injection mechanism is sound, and the Skeptic’s fix is concrete and low-cost. The single unresolved gap is whether retrieval-only failures are frequent enough to invalidate the three-arm attribution — and that is exactly what the fourth arm measures. I am therefore ending the text debate and moving to experiment. The next step must be a four-arm microbenchmark with a 2×2 attribution matrix, query-blind gold projection, and probe entailment/adversarial agreement rather than label agreement alone.

**Conclusion.** Proceed to pilot with the fourth arm added. The minimum discriminating run is: baseline; gold construction with actual retrieval; gold construction with permissive retrieval; actual construction with permissive retrieval. Report the 2×2 matrix and the probe’s adversarial agreement. The key risk is that retrieval-only failures dominate, in which case the original construction attribution pipeline is invalid and must be redesigned. Flag “unattributable” when independent projections disagree. Do not restart the theoretical debate unless the 2×2 matrix contradicts the assumed causal model.

```yaml
assessment: READY_FOR_PILOT
next_action: EXPERIMENT
stop_reason: REVIEW_COMPLETE
open_issues:
  - id: O1
    claim: Certified availability via query-blind probe/generation with adversarial agreement check, falling back to explicit occurrence below ~90% agreement.
    status: needs_experiment
    change_this_round: Skeptic adds query-blind and adversarial-set requirement; accepted as pilot gate.
  - id: O2
    claim: Sufficiency testing across four arms, including permissive retrieval over actual memory, yields unbiased construction/retrieval attribution.
    status: needs_experiment
    change_this_round: Fourth arm added; 2x2 attribution matrix now required to validate attribution.
```
[JUDGE_DECISION]: STOP_CONVERGED
