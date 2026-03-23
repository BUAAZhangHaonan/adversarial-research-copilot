---
name: debate-runner
description: Run ARC adversarial debate loop with proposer, skeptic, moderator and produce round-wise adjudication.
argument-hint: "[idea-file]"
allowed-tools: Read, Write, Bash(*), Agent
---

# Debate Runner

## Goal
Force the proposal through adversarial scrutiny until convergence or hard-stop.

## Protocol
- Proposer: strongest feasible version
- Skeptic: ranked blockers (P0/P1/P2)
- Moderator: scorecard + blocker gate + continue/stop

## Required Outputs
- `DEBATE_LOG.md`
- `reports/latest/debate_log.jsonl`
- `reports/latest/research_decision_memo.md`

## Stop Conditions
1. No unresolved blockers for two consecutive rounds
2. Average score >= configured threshold
3. Hard max rounds reached -> output best-so-far with unresolved risks
