# ARC Repair Program Design

**Date:** 2026-03-24
**Scope:** Repair ARC's runtime contracts, prompt protocol, prompt quality, repo-facing docs/skills alignment, and test guards.
**Primary Goal:** Turn ARC from a promising experimental framework into a contract-consistent tool whose runtime behavior, prompts, skills, docs, and tests all agree.

---

## Why This Program Exists

The current codebase has three high-impact breakpoints:

1. Runtime promises are not trustworthy enough.
   `debate --resume` and `chat-mode --resume` do not actually recover prior progress in the way the repository claims.
2. Prompt protocol and runtime parsing are out of sync.
   The Moderator prompt has drifted away from the parser and convergence logic, which weakens ARC's core control loop.
3. Repo-facing contracts have drifted.
   `README.md`, `skills/*.md`, prompt structure, artifact naming, and defaults no longer consistently describe the implementation.

The repair program therefore treats ARC as a contract system, not just a codebase.

---

## Repair Principles

### 1. Contract First

Each repair package starts by defining the target contract:

- what the CLI promises
- what files are written
- what a prompt must emit
- what a parser must accept
- what docs and skills are allowed to claim

If a behavior is not encoded in tests or docs, it is not yet stable.

### 2. One Package, One Cohesive Outcome

Each repair package must be independently finishable in one pass:

- its own failing tests
- its own implementation
- its own verification
- its own commit

No package should require half-finished work from another package before it can be validated.

### 3. Runtime Truth Before Prompt Flourish

We first repair the mechanics of recovery and protocol parsing, then deepen prompt quality. Better prose is wasted if runtime semantics are still untrustworthy.

### 4. Borrow Design Discipline, Not Surface Copy

From `references/ARIS/skills`, ARC should borrow:

- explicit stage outputs and gates from `research-pipeline`
- persistent long-loop state discipline from `auto-review-loop`
- focused problem/mechanism/validation framing from `research-refine`
- stronger artifact and report structure from `idea-creator` and `novelty-check`

ARC should not blindly copy ARIS artifact names or workflow shape. ARC remains a three-role adversarial research copilot, not a paper-writing automation system.

### 5. Prompt Engineering Is Product Engineering

Prompt files are not filler text. They define:

- role boundary
- reasoning target
- structure and length
- machine-readable protocol
- fallback expectations
- how the model should behave under uncertainty

The prompt overhaul package must therefore be treated as a production interface upgrade.

---

## Package Breakdown

### Package 01: Runtime Contracts

Repair:

- `debate` resume behavior
- `chat-mode` resume behavior
- input persistence ordering
- run directory state consistency
- artifact naming normalization where runtime correctness depends on it

Output:

- working resume semantics
- regression tests for recovery behavior
- docs updated only where needed to stop false promises

### Package 02: Moderator Protocol

Repair:

- `prompts/moderator.md`
- `src/arc/scoring/rubric.py`
- `src/arc/orchestrator.py`
- parser/convergence tests

Output:

- one canonical Moderator YAML schema
- resilient parsing with explicit fallback behavior
- convergence logic reading the same semantics the prompt asks for

### Package 03: Prompt System Overhaul

Repair:

- `prompts/proposer.md`
- `prompts/skeptic.md`
- `prompts/moderator.md`
- `prompts/chat_mode/*.md`
- a prompt contract doc if needed

Output:

- deeper, tighter role prompts
- better structure and style constraints
- clearer machine-readable expectations
- compatibility with package 02 protocol

### Package 04: Skills and Docs Alignment

Repair:

- `README.md`
- `skills/*.md`
- `skills/README.md`
- artifact names, default behavior descriptions, project structure, version claims

Output:

- repo-facing contract consistency
- no contradictory file names, defaults, or flow descriptions

### Package 05: Contract Tests and Guards

Repair:

- missing test coverage for resume, prompt-parser alignment, doc/skill artifact naming
- lightweight repository guardrails if useful

Output:

- CI catches future contract drift instead of allowing it to accumulate silently

---

## Execution Order

The packages must run in this order:

1. `repair-01-runtime-contracts`
2. `repair-02-moderator-protocol`
3. `repair-03-prompt-system-overhaul`
4. `repair-04-skills-docs-alignment`
5. `repair-05-contract-tests-and-guards`

This ordering keeps the highest-risk correctness issues in front and lets the docs and test packages describe the repaired system rather than the broken one.

---

## Acceptance Criteria

The program is complete only when all of the following are true:

- `debate --resume`, `pipeline --resume`, and `chat-mode --resume` have explicit tested semantics.
- Moderator prompt and parser share one documented contract.
- All production prompts have clear role boundaries and output rules rather than vague stylistic suggestions.
- `README.md`, `skills/*.md`, runtime artifacts, and actual implementation use the same names and defaults.
- The repository includes tests or guards that detect the most likely future drift points.

---

## Risks To Watch During Execution

### Risk 1: Fixing Docs Too Early

If docs are rewritten before runtime semantics are repaired, they may need to be rewritten again and will likely drift a second time.

### Risk 2: Over-coupling Prompt Overhaul With Runtime Changes

Package 03 should deepen prompt quality, not quietly redefine parser semantics that belong to package 02.

### Risk 3: Treating Resume As “Re-use Directory”

Resume must mean recover state according to a tested contract, not simply write into an existing folder.

### Risk 4: Over-testing String Literals

Prompt and doc tests should assert stable contract markers, not freeze every sentence.

---

## ARIS-Informed Notes

Useful patterns observed from `references/ARIS/skills`:

- A long-running loop should persist compact resumable state after each meaningful round.
- Artifact contracts should be explicit and named in the workflow itself.
- Review loops should distinguish summary, raw reviewer content, and structured state.
- Research-oriented prompts work best when they enforce a problem anchor, concrete mechanism, and minimal validation plan.

ARC should reuse these principles to strengthen its debate, chat, and pipeline flows.

---

## Delivery Mode

Each package will be handled as:

1. write or update failing tests
2. verify failure
3. implement minimal cohesive fix
4. run targeted verification
5. run broader regression verification where appropriate
6. commit package changes separately

This keeps the history reviewable and avoids a single mixed repair branch.
