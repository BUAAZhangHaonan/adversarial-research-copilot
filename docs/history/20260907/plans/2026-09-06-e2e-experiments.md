# E2E Experiment Log — 2026-09-06 (review-fix batches)

Real runs validating the R1-R9/D1-D8 fixes. All three modes use the DeepSeek
split (flash generates / pro judges). Environment: master @ post-2.8 commits.

## 1. chat-mode short run — PASSED, redesign validated end-to-end

Command: `arc chat-mode "stress test: failure attribution in long-horizon agent
memory — construction loss vs retrieval loss" --proposer deepseek-v4-flash
--skeptic deepseek-v4-pro --moderator deepseek-v4-pro --min-rounds-before-stop 2
--max-rounds 6 --max-review-cycles 1 --max-inner-rounds 6`

Run dir: `reports/20260906_014859_deepseek_v4_flash_deepseek_v4_pro_deepseek_v4_pro`

Observed:

- **3 rounds then stop** with `stop_reason=moderator_next_action_EXPERIMENT`.
  The real deepseek-v4-pro moderator emitted valid control YAML in every round
  (`structured_ok=True` for 3/3): assessment UNRESOLVED → UNRESOLVED →
  READY_FOR_PILOT; issue ledger grew 1 → 2 open issues; round 3 routed the
  unresolved questions to an experiment and ended the text debate.
- `pending_actions` persisted (type=experiment, serves O1+O2) and
  `PENDING_ACTIONS.md` rendered with the "stopping ≠ endorsement" framing.
- Reviewer did NOT reopen a text cycle (0 reviewer calls after the routing).
- `COST_REPORT.md`: flash 7 calls / 85,407 tokens; pro 10 calls / 89,840
  tokens; 0 usage-less reports. ~30 min wall time.
- Contrast with the pre-fix behavior on a comparable topic: the 2026-04-10
  run needed 166 rounds and 4 review cycles to reach a RESOLVED verdict while
  circling one evidence-only question. The redesign reaches an honest
  "needs an experiment" routing in 3 rounds.

Limitations recorded honestly: the per-round *prompts* are not persisted, so
research-object injection and ledger injection are verified by unit tests
(test_research_object_grounds_first_round, test_open_issues_ledger_flows_to_next_round,
test_reviewer_feedback_reaches_next_cycle_proposer) rather than by this live
run's artifacts. The run's inputs did include the pre-debate artifacts
(FINAL_PROPOSAL.md etc. existed before round 1), so the injection code path
was active.

## 2. formal debate short run — PASSED, protocol path validated

Command: `arc run examples/multimodal_research_idea.md --proposer
deepseek-v4-flash --skeptic deepseek-v4-pro --moderator deepseek-v4-pro`

Run dir: `reports/20260906_014859_..._01`

Observed:

- 6 rounds (bounded by debate.yaml max_rounds), every decision parsed from
  valid YAML: `protocol_errors=0`, `parse_degraded=False` in all rounds.
- Zero prose-guessed stops. Scores moved under adversarial pressure
  (avg 3.4 → 2.4 → 3.0; blockers 3 → 6 → 5) — the debate honestly CONTINUEd
  to the round limit instead of a fabricated convergence.
- `run_state.json` now carries the protocol_errors counter.

## 3. discover full-parameter run — see section below (filled after completion)

Command: `arc discover "memory architectures for LLM agents over long horizons:
what breaks after 100 turns" --papers 60 --deep-read 12 --ideas 8`

(Pending at time of writing; completed results appended below.)

### 3. discover full-parameter run — COMPLETED (2026-09-05 18:50 UTC)

Run dir: `reports/20260906_014858_deepseek_v4_flash_deepseek_v4_pro`, ~3h wall
(mostly server-side deep reads and dedup queries).

- Stages all completed. 60-paper pool → 12 deep-read attempts (1 paper
  2602.05665 failed server-side, logged and skipped — per-paper resilience
  worked) → **1 gap mined** (stale_premise, KEEP after audit) → 8 ideas →
  duplicate-check: 6 DISTINCT / 2 POSSIBLY_DUPLICATE → taste gate:
  **7 KEEP + 1 PIVOT, 0 KILL**.
- The PIVOT (I2) cites a real methodological defect ("the minimal test omits
  explicit state-update scoring, so the three-way decomposition is not
  separable") — exactly the kind of bound reasoning the new gate asks for.
- All KEEP reasons bind to specific prior work named by the dedup stage
  (TRAJDEBUG, Memory-R2/FLARE, MINTEval, 2604.11978), with delta types
  (new_boundary / new_mechanism / new_problem) and separates-alternatives flags.
- Top-ranked problem: "Which property of a long-horizon task — raw trajectory
  length, number of distinct subgoals, or the distance between an early fact
  and its late use — actually determines when a no-memory long-context
  baseline loses to a memory-augmented agent?" — a condition-level factorial
  question, not a method stack.
- 0 rejection-log entries (no KILL occurred — consistent with evidence-bound
  kills; nothing was killed on taste alone).
- COST_REPORT.md: flash 2 calls / 18,800 tok; pro 11 calls / 94,573 tok;
  MCP: scholartrace 24, scholaranalysis 13, webresearch 17 calls.

Honest observations:

- Gap mining returned only 1 gap from 12 deep reads — conservative under the
  comparability check; better than inventing conflicts, but the miner prompt
  may now be too strict. Left as tuning follow-up, not a code bug.
- Only 1 gap → audit budget (8) untested at scale in this run; covered by
  unit tests instead.
- Idea quality visibly shifted vs the 2026-09-05 pre-fix run on the same
  topic: then, 2 kept problems both about failure attribution framing; now,
  7 kept with factorial conditions, cost-matched interventions, planner-
  strength controls — more diverse and more falsifiable, matching the
  upgraded deep-read extraction (conditions/alternatives, not just
  limitations).

## Verdict

All three modes pass their E2E validation of the fix batches. No new code
defects surfaced during the runs. Tuning follow-ups (non-blocking): gap-miner
strictness; per-round prompt persistence for future live-trace verification.
