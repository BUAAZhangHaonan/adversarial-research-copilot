---
name: pipeline-arc
description: Execute ARC end-to-end chain from literature to decision memo.
argument-hint: "[research-topic]"
allowed-tools: Read, Write, Bash(*), Agent, Skill
---

# ARC End-to-End Pipeline

## Goal
Run a complete controlled adversarial research workflow.

## Stage Chain
1. research-lit
2. idea-creator
3. novelty-check
4. evidence-grounding
5. research-refine
6. experiment-bridge
7. debate-runner
8. auto-review-loop
9. memo-synthesis

## Required Outputs
- `LITERATURE_MAP.md`
- `IDEA_REPORT.md`
- `FINAL_PROPOSAL.md`
- `EVIDENCE_TABLE.md`
- `EXPERIMENT_PLAN.md`
- `RESEARCH_DECISION_MEMO.md`

## Rule
Do not skip novelty-check and debate-runner. They are mandatory gates.
