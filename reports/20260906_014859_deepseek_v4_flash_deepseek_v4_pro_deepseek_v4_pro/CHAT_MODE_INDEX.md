# CHAT_MODE_INDEX

This run uses the full chat-mode pipeline (9 stages) with nested review cycles.

- min_rounds_before_stop: 2
- max_rounds_soft_target: 6
- drift_check_interval: 5
- max_review_cycles: 1
- max_inner_debate_rounds: 6
- prompt_language: en
- stop_reason: moderator_next_action_EXPERIMENT

| file | purpose |
|---|---|
| TOPIC_CHAT.txt | Topic input |
| REFERENCES.md | Reference list with abstracts (DeepXiv primary) |
| LITERATURE_MAP.md | Literature mapping |
| IDEA_REPORT.md | Candidate ideas |
| FINAL_PROPOSAL.md | Final proposal |
| EVIDENCE_TABLE.md | Claim-evidence table |
| EXPERIMENT_PLAN.md | Experiment plan |
| CHAT_TRANSCRIPT.md | Full conversation transcript |
| BEST_CONSENSUS.md | Condensed best consensus |
| RESEARCH_DECISION_MEMO.md | Final research decision memo |
| AUTO_REVIEW.md | Auto-review logs |
| REVIEW_CYCLES.md | Review cycles report |
| PENDING_ACTIONS.md | External work (retrieve/experiment) requested by the judge |
| chat_mode_state.json | Structured state with timestamps |
| chat_rounds/ | Per-cycle folders (review_cycle_XX/) with per-round artifacts and reviewer output |

completed_debate_rounds: 3
completed_review_cycles: 0
