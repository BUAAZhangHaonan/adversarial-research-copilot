---
name: novelty-check
description: Stress-test whether the proposed idea is actually new or just renamed prior work.
argument-hint: "[idea-file]"
allowed-tools: Read, Grep, WebSearch, WebFetch, Write
---

# Novelty Check

## Goal
Answer one question: is this idea substantively novel under a strict baseline comparison?

## Output
Write `FINAL_PROPOSAL.md`:
1. Closest prior work (top 5)
2. Overlap matrix (mechanism, data, metric, claim)
3. True differentiators (if any)
4. Risk of pseudo-novelty
5. A proposal version that is safe to send into ARC debate

## Rules
- Novelty cannot be based on naming or packaging differences.
- If overlap > 70% on mechanism and evaluation, mark as high pseudo-novelty risk.
