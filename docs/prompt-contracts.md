# ARC Prompt Contracts

This document describes the stable contracts between ARC prompt files and ARC runtime code.

## Debate Prompts

`prompts/proposer.md`, `prompts/skeptic.md`, and `prompts/moderator.md` define the structured behavior for the debate loop.

Shared rules:

- Debate prompts are written for Chinese final output.
- The prompt controls role boundary, reasoning focus, and narrative structure.
- The runtime controls what input context is injected into each round.

Role-specific notes:

- `proposer.md` must consume prior blockers and revisions and push one preferred path.
- `skeptic.md` must pressure-test the current proposer output and name evidence gaps.
- `moderator.md` must convert the round into control signals for convergence.

## Chat Mode Prompts

`prompts/chat_mode/*.md` define a lighter debate surface with hard brevity limits.

Shared rules:

- Chat mode responses must stay concise.
- Each agent should speak in natural Chinese.
- Reference grounding matters, but the format is intentionally lighter than the main debate loop.
- `moderator_chat.md` must always end with the `[JUDGE_DECISION]:` marker consumed by chat-mode parsing.

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
