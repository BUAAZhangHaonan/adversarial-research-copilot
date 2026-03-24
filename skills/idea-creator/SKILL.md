---
name: idea-creator
description: Generate and rank candidate research ideas from a constrained problem frame.
argument-hint: "[problem-frame]"
allowed-tools: Read, Write, Grep, Agent
---

# Idea Creator

## Goal
Generate 8-12 candidate ideas, then rank down to top 3 based on feasibility and falsifiability.

## Output Files
- `IDEA_REPORT.md`

## Required Structure
For each candidate include:
1. Hypothesis
2. Core mechanism
3. Why now
4. Minimal experiment
5. Main failure mode

## Ranking Rubric
- novelty (1-5)
- feasibility (1-5)
- falsifiability (1-5)
- resource fit (1-5)

## Hard Rule
Discard ideas that cannot define a measurable failure criterion.
