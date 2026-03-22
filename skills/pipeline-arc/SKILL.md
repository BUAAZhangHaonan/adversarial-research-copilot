---
name: pipeline-arc
description: Execute ARC end-to-end chain from literature to decision memo.
argument-hint: [research-topic]
allowed-tools: Read, Write, Bash(*), Agent, Skill
---

# ARC End-to-End Pipeline

## Goal
Run a complete controlled adversarial research workflow.

## Stage Chain
1. research-lit
2. idea-creator
3. novelty-check
4. research-refine
5. experiment-bridge
6. debate-runner
7. auto-review-loop
8. memo-synthesis

## Required Outputs
- `LITERATURE_MAP.md`
- `IDEA_REPORT.md`
- `FINAL_PROPOSAL.md`
- `EXPERIMENT_PLAN.md`
- `RESEARCH_DECISION_MEMO.md`

## Rule
Do not skip novelty-check and debate-runner. They are mandatory gates.
