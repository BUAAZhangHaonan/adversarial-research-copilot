---
name: experiment-bridge
description: Turn a proposal into executable experiment tasks and runbook scripts.
argument-hint: [proposal-file]
allowed-tools: Read, Write, Edit, Bash(*), Grep
---

# Experiment Bridge

## Goal
Translate research design into runnable task graph.

## Outputs
- `EXPERIMENT_PLAN.md`
- `RUNBOOK.md`
- `TASKS.md`

## Required Fields per Experiment
1. objective
2. input data
3. baseline
4. metrics
5. expected failure mode
6. wall-clock estimate

## Rules
- Separate must-run vs optional experiments.
- Flag compute-heavy experiments (>24h single GPU) explicitly.
