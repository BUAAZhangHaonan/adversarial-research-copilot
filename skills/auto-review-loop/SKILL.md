---
name: auto-review-loop
description: Iterate review-fix-rerun cycles on ARC outputs and keep state for long-running sessions.
argument-hint: "[scope]"
allowed-tools: Read, Write, Edit, Bash(*), Agent
---

# Auto Review Loop

## Goal
Repeat review and correction without losing state when sessions are interrupted.

## Constants
- MAX_ROUNDS = 4
- POSITIVE_THRESHOLD = 7/10
- STATE_FILE = `reports/latest/run_state.json`
- LOG_FILE = `AUTO_REVIEW.md`

## Required Round Steps
1. Review current memo and logs
2. List top blockers with severity
3. Apply fixes (prompt, config, implementation)
4. Re-run focused validation
5. Append round summary and update state file

## Resume Policy
- If state is `in_progress` and not stale, continue from next round.
- If state is stale, archive and restart fresh.
