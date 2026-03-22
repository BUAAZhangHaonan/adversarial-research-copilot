---
name: research-lit
description: Collect and prioritize literature evidence from local PDFs, notes, and web APIs to produce a claim-oriented evidence map.
argument-hint: [topic-or-question]
allowed-tools: Read, Grep, Glob, Bash(*), WebSearch, WebFetch, Write
---

# Research Literature Mapping

## Goal
Build a focused evidence set for a research question instead of a broad summary.

## Inputs
- User question
- Local PDFs (`papers/**/*.pdf`, `literature/**/*.pdf`)
- Existing notes (`notes/**/*.md`, `docs/**/*.md`)
- Optional web sources

## Output
Write `LITERATURE_MAP.md` with:
1. Core problem definition
2. Top 10 relevant papers with 1-line contribution
3. Open contradictions or gaps
4. Evidence confidence per claim (`high/medium/low`)
5. What must be validated experimentally

## Rules
- Prefer local evidence before web evidence.
- Every claim must cite at least one source line or URL.
- Mark unknowns explicitly instead of guessing.
