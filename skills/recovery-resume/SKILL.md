---
name: recovery-resume
description: Recover interrupted ARC runs from run_state and final_state snapshots.
argument-hint: [reports-dir]
allowed-tools: Read, Write, Bash(*), Grep
---

# Recovery Resume

## Goal
Continue long-running loops safely after crashes or context compaction.

## Steps
1. Validate `run_state.json` exists and is not stale.
2. Validate `final_state.json` integrity.
3. Recover round index and pending blockers.
4. Resume with `arc run ... --resume`.
5. Record recovery event in `AUTO_REVIEW.md`.

## Rule
If integrity check fails, start a fresh run and preserve corrupted snapshot as backup.
