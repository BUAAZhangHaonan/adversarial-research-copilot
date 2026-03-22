---
name: memo-synthesis
description: Convert debate artifacts into a concise research decision memo with explicit go/no-go decision.
argument-hint: [reports-dir]
allowed-tools: Read, Write, Grep
---

# Memo Synthesis

## Goal
Produce decision-ready output, not a transcript dump.

## Output
Write `RESEARCH_DECISION_MEMO.md` with:
1. Primary plan
2. Alternative plan
3. Blockers resolved
4. Blockers unresolved
5. Minimum validation experiments
6. Resource budget
7. Final decision (GO / HOLD / KILL)

## Rule
Every decision line must reference evidence from debate rounds.
