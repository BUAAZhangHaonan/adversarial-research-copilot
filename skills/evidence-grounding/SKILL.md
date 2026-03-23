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

Also append an `ARXIV_REFERENCES` section with:
- arxiv_id
- title
- relevance_to_claim
- status (`verified` | `candidate` | `unverified`)

## Rule
Claims without evidence must be marked `unsupported`.

Reference policy:
- Prefer arXiv sources for technical claims.
- Never fabricate arXiv IDs. If unsure, mark as `candidate` or `unverified` and provide a concrete search query.
