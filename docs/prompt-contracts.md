# ARC Prompt Contracts

This document describes the stable contracts between ARC prompt files and ARC runtime code.

## Debate Prompts

`prompts/latest/default/proposer_en.md`, `prompts/latest/default/skeptic_en.md`, and `prompts/latest/default/moderator_en.md` define the default structured behavior for the debate loop.

Chinese variants are provided at:

- `prompts/latest/default/proposer_zh.md`
- `prompts/latest/default/skeptic_zh.md`
- `prompts/latest/default/moderator_zh.md`

Shared rules:

- Default debate prompts are English-first.
- Equivalent Chinese variants are maintained for runtime language switching.
- The prompt controls role boundary, reasoning focus, and narrative structure.
- The runtime controls what input context is injected into each round.

Role-specific notes:

- `proposer.md` must consume prior blockers and revisions and push one preferred path.
- `skeptic.md` must pressure-test the current proposer output and name evidence gaps.
- `moderator.md` must convert the round into control signals for convergence.

## Chat Mode Prompts

`prompts/latest/chat/*_en.md` define the default chat-mode prompt surface with hard brevity limits.

Chinese variants are provided at `prompts/latest/chat/*_zh.md`.

Shared rules:

- Chat mode responses must stay concise.
- Default chat-mode iteration is English.
- Chinese mode remains available via runtime language switch.
- Reference grounding matters, but the format is intentionally lighter than the main debate loop.
- `moderator_chat_*.md` must always end with the `[JUDGE_DECISION]:` marker consumed by chat-mode parsing.

## Discover Mode Prompts

`prompts/latest/discover/*.md` define the discover pipeline roles
(`theme_framer`, `gap_miner`, `saturation_auditor`, `idea_generator`,
`taste_judge`). They are language-neutral (suffixless) and currently
English-only.

Shared rules:

- Every discover prompt must end its response with a fenced ```yaml block
  containing its contract key.
- Discover prompts must distinguish the cognitive task from judgment
  anchors and anti-patterns (layered structure is part of the contract).

Runtime-owned contract fields (must not drift without updating
`src/arc/runners/discover_runner.py` and `tests/test_prompts.py`):

- `theme_framer`: `theme` → `field`, `subtopics`, `must_include`, `exclude`, `search_queries`
- `gap_miner`: `gaps` → `id`, `type`, `question`, `evidence_ids`, `why_unexplored`, `who_needs_it`, `confidence`
- `saturation_auditor`: `audits` → `gap_id`, `verdict` (KEEP | INSUFFICIENT_EVIDENCE | KILL), `evidence_basis` (real_world_failure | scientific_deficit | none), `evidence`, `missing_evidence`, `reason`
- `idea_generator`: `ideas` → `id`, `from_gaps`, `one_sentence_problem`, `gap_evidence`, `who_needs_it`, `why_now`, `minimal_falsifiable_test`, `anti_scope`
- `taste_judge`: `judgments` → `id`, `problem_novelty`, `incremental_risk`, `arrow_before_target`, `so_what`, `decisiveness`, `verdict`, `reason`

## Runtime-Owned Contract Fields

These fields are owned by runtime code and must not drift without updating both prompt and parser:

- Debate Moderator YAML:
  - `scorecard`
  - `unresolved_blockers`
  - `required_revisions`
  - `continue_or_stop`
  - `reason`

- Debate Proposer YAML:
  - `proposal_quality`
  - `top_next_actions`
  - `open_questions`

- Debate Skeptic YAML:
  - `risk_summary`
  - `next_round_focus`
  - `evidence_to_collect`

## Safe Changes

Safe prompt changes:

- tightening wording
- improving examples
- improving role guidance
- changing human-readable section names

Unsafe prompt changes unless runtime/tests are updated too:

- renaming machine-readable YAML fields
- changing the final chat judge marker
- removing required context assumptions
- changing output language expectations
