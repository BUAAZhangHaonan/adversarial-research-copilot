---
name: research-refine
description: Convert a vague or over-broad idea into a testable, resource-bounded proposal.
argument-hint: [idea-or-proposal]
allowed-tools: Read, Write, Edit, Grep, Agent
---

# Research Refine

## Goal
Produce a version of the proposal that can be executed this week, not a speculative narrative.

## Output
Write `FINAL_PROPOSAL.md` with fixed sections:
1. Problem and scope
2. Method specification
3. Evaluation protocol
4. Compute/data budget
5. Kill criteria
6. Fallback path

## Rules
- Ban ambiguous verbs: "improve", "optimize", "enhance" without measurable target.
- Include at least one negative control experiment.
