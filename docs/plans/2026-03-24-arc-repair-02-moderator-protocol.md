# ARC Repair 02 Moderator Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Re-establish one canonical Moderator protocol shared by prompt, parser, orchestration, and convergence logic.

**Architecture:** Define a single YAML contract in the Moderator prompt, teach the parser to read it reliably, and let orchestration consume only that contract plus a documented fallback path when YAML is absent or malformed.

**Tech Stack:** Python 3.11, pytest, regex/yaml parsing, markdown prompt files

---

### Task 1: Freeze The Canonical Moderator Schema In Tests

**Files:**
- Modify: `tests/test_rubric.py`
- Modify: `tests/test_convergence.py`
- Modify: `prompts/moderator.md`

**Step 1: Write the failing test**

Add tests that verify the canonical YAML fields, for example:

- `scorecard`
- `unresolved_blockers`
- `required_revisions`
- `continue_or_stop`
- optional `reason`

Also add a test that the prompt itself includes those exact field names.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rubric.py tests/test_convergence.py -q`
Expected: FAIL because the current prompt advertises a different schema.

**Step 3: Write minimal implementation**

Rewrite `prompts/moderator.md` so the machine-readable section matches the parser's intended control fields.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rubric.py tests/test_convergence.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_rubric.py tests/test_convergence.py prompts/moderator.md
git commit -m "fix: align moderator prompt schema with runtime contract"
```

### Task 2: Harden Parser Behavior Around The Canonical Schema

**Files:**
- Modify: `src/arc/scoring/rubric.py`
- Modify: `tests/test_rubric.py`

**Step 1: Write the failing test**

Add tests for:

- canonical YAML parsing
- malformed YAML fallback
- missing fields falling back to documented defaults
- bullet fallback for blockers and revisions

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rubric.py -q`
Expected: FAIL on the new fallback cases.

**Step 3: Write minimal implementation**

Adjust `rubric.py` so:

- canonical YAML is preferred
- fallback behavior is explicit and stable
- score fallback uses the intended default semantics rather than accidental parser drift

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rubric.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/arc/scoring/rubric.py tests/test_rubric.py
git commit -m "fix: harden moderator parser fallback behavior"
```

### Task 3: Verify Orchestrator Uses The Same Semantics

**Files:**
- Modify: `src/arc/orchestrator.py`
- Modify: `tests/test_debate_runtime.py`

**Step 1: Write the failing test**

Add a debate loop test that proves parsed scorecard, blockers, revisions, and decision flow into round records and future rounds as expected.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_debate_runtime.py -q`
Expected: FAIL if orchestration still assumes a different shape or loses prior revisions.

**Step 3: Write minimal implementation**

Adjust orchestration only as needed so it consumes the canonical parsed payload and persists the same semantics round-to-round.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_debate_runtime.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/arc/orchestrator.py tests/test_debate_runtime.py
git commit -m "fix: route moderator protocol through debate orchestration"
```

### Task 4: Verify Moderator Protocol Package

**Step 1: Run targeted verification**

Run: `pytest tests/test_rubric.py tests/test_convergence.py tests/test_debate_runtime.py -q`
Expected: PASS

**Step 2: Run broader verification**

Run: `pytest -q`
Expected: PASS
