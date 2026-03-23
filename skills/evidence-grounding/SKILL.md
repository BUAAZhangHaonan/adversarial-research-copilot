---
name: evidence-grounding
description: Attach concrete evidence to skeptic criticisms and proposer claims.
argument-hint: "[debate-round-or-memo]"
allowed-tools: Read, Grep, WebSearch, WebFetch, Write
---

# Evidence Grounding

## Goal
Reduce unsupported arguments by forcing source-backed claims.

## Output
Write `EVIDENCE_TABLE.md`:
- claim
- supporting evidence
- contradicting evidence
- confidence
- next verification action

## Rule
Claims without evidence must be marked `unsupported`.
