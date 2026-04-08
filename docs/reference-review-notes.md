# Reference Review Notes (ARIS + EvoScientist)

## Repositories Reviewed
- ARIS: https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
- EvoScientist: https://github.com/EvoScientist/EvoScientist

## ARIS: Key Takeaways
1. Cross-model review is first-class, not optional.
2. Multi-round loop must have hard cap (`MAX_ROUNDS`) and explicit stop thresholds.
3. Compact recovery state is critical for long runs (`REVIEW_STATE.json` pattern).
4. Human checkpoint should be optional and configurable.
5. Keep workflow lightweight and file-oriented for portability.

## EvoScientist: Key Takeaways
1. Multi-agent role separation improves accountability.
2. Persistent memory and long-horizon workflow matter.
3. Scientific process should be stage-based (intake/plan/execute/evaluate/write/verify).
4. Multi-provider model switching should be config-driven.

## What ARC Adopted Now
- `require_cross_model_adversary=true` in debate config.
- `run_state.json` persistence after each round.
- `--resume` option in CLI to recover interrupted runs.
- Stronger prompts for evidence thresholds and severity ranking.
- Moderator YAML payload for deterministic parsing.
- Unified internal literature provider shared by pipeline/chat (`arXiv -> Semantic Scholar -> DeepXiv supplement`).

## What ARC Intentionally Delays
- Heavy orchestration frameworks and many sub-agents.
- Full autonomous experiment execution stack.
