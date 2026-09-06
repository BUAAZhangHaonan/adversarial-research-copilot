# Auto Review — Round 4

## 1. Review current memo and logs

Reviewed `BEST_CONSENSUS` at `latest_round: 3` with `STOP_CONVERGED`.  
The conceptual resolution is accepted: the fourth arm is required, and no further text debate is needed on the three-arm vs four-arm question.

However, the memo as written is **not yet execution-ready** as `READY_FOR_PILOT`. The remaining blockers are operational/specification gaps, not a reason to reopen the theoretical debate.

---

## 2. Top blockers

| Severity | Blocker | Why it matters |
|---|---|---|
| **P0** | Permissive-retrieval arm is not operationalized | If permissive retrieval leaks gold memory or answer information, construction-only failures will be misestimated. If it returns noisy context, it may harm success and violate the no-harm assumption. |
| **P0** | 100-slice human-agreement gate is underpowered | For observed 90% agreement, N=100 gives a 95% CI of about ±9.8 percentage points. That cannot certify a ~90% adversarial agreement threshold reliably. |
| **P1** | 2×2 attribution estimators are not pre-registered | Without explicit formulas, the pilot cannot consistently separate construction fault rate, retrieval fault rate, and both-fault/unattributable cases. |
| **P1** | “Independent projections disagree” is not operationalized | The memo flags unattributable cases by projection disagreement, but does not define the projections, agreement metric, threshold, or tie-break. |
| **P2** | “Unbiased” is too strong in O2 | The four-arm design can produce identifiable attribution under no-harm and gold-sufficiency assumptions, but not unconditional unbiasedness. |

---

## 3. Fixes applied

### Minimal memo corrections

1. **Replace the 100-slice early-stop claim**  
   Current:  
   > “100-slice human-agreement check as a correct early stop”  
   Correction:  
   Use an adjudicated adversarial agreement gate with sequential sampling. Start at N=100; if the lower bound of the 95% CI is below 0.90, expand to N=200/400. Report exact/entailment agreement and Cohen’s kappa.

2. **Lock arm definitions**

| Arm | Construction | Retrieval |
|---|---|---|
| Baseline | actual | actual |
| A | gold | actual |
| B | gold | permissive |
| C | actual | permissive |

Permissive retrieval must be:
- query-blind;
- denied access to gold memory;
- denied answer-derived queries;
- allowed to retrieve all relevant chunks within a fixed context budget;
- validated with a no-harm check: `fail(gold, permissive) <= fail(gold, actual) + epsilon`.

3. **Pre-register attribution estimators**

Let:
- `b = fail(gold, permissive)`
- `retrieval_fault = fail(gold, actual) - b`
- `construction_fault = fail(actual, permissive) - b`
- `both_fault = max(0, retrieval_fault + construction_fault - (fail(actual, actual) - b))`

Report the full 2×2 matrix. Flag `unattributable` when `both_fault > epsilon` or independent probe projections disagree beyond the pre-registered threshold.

4. **Soften O2 wording**  
   Change “yields unbiased construction/retrieval attribution” to:  
   “yields identifiable construction/retrieval attribution under the pre-registered no-harm, gold-sufficiency, and no-leakage assumptions.”

---

## 4. Focused validation

Dry-run with synthetic independent fault rates:  
`P(construction_fault)=0.20`, `P(retrieval_fault)=0.30`, baseline `0`.

Expected matrix:

| Condition | Failure rate |
|---|---|
| actual C + actual R | 0.44 |
| gold C + actual R | 0.30 |
| actual C + permissive R | 0.20 |
| gold C + permissive R | 0.00 |

Recovered estimates:
- construction fault rate = 0.20
- retrieval fault rate = 0.30
- both-fault rate = 0.06

This confirms the four-arm matrix can separate construction, retrieval, and both-fault cases **only if** permissive retrieval does not leak and does not harm. The previously missing `actual C + permissive R` arm is essential.

---

## 5. Round summary and state update

**Decision:** `STOP_CONVERGED` stands for the theoretical debate.  
**Effective status:** `CONDITIONAL_READY_FOR_PILOT`.

Do not restart the theoretical debate. Apply the P0/P1 corrections above, then start the pilot.

### Proposed state update

```json
{
  "topic": "failure attribution in long-horizon agent memory — construction loss vs retrieval loss",
  "latest_round": 4,
  "state": "in_progress",
  "decision": {
    "raw": "STOP_CONVERGED",
    "effective": "CONDITIONAL_READY_FOR_PILOT"
  },
  "next_round": 5,
  "timestamp": "2026-09-05T18:45:00Z",
  "blockers": [
    "P0: operationalize permissive retrieval and no-harm check",
    "P0: replace fixed 100-slice agreement gate with sequential powered gate",
    "P1: pre-register 2x2 attribution estimators and unattributable rule",
    "P1: operationalize independent projections/adversarial agreement"
  ],
  "open_issues": ["O1", "O2"]
}
```

### AUTO_REVIEW.md entry

```markdown
### Round 4
- Theoretical STOP_CONVERGED upheld.
- READY_FOR_PILOT rejected as-is due to P0/P1 execution blockers.
- Added required arm definitions, attribution estimators, and sequential agreement gate.
- Effective status: CONDITIONAL_READY_FOR_PILOT.
```
