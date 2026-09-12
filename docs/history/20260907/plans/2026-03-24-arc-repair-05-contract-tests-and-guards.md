# ARC Repair 05 Contract Tests And Guards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add durable tests and lightweight guards that prevent future drift across runtime, prompts, skills, and docs.

**Architecture:** Reuse the contract tests introduced in earlier packages, then add guard helpers only where they reduce drift without becoming brittle. The emphasis is on catching the high-value regressions the current suite misses.

**Tech Stack:** pytest, lightweight repository validation helpers, markdown/text contract assertions

---

### Task 1: Consolidate Missing Contract Coverage

**Files:**
- Modify: `tests/test_debate_runtime.py`
- Modify: `tests/test_chat_mode_runner.py`
- Modify: `tests/test_prompts.py`
- Modify: `tests/test_repo_contracts.py`

**Step 1: Write the failing test**

Add any still-missing regression checks for:

- stale resume state handling
- malformed or partial moderator YAML
- prompt contract markers that must never disappear
- repo artifact naming consistency

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_debate_runtime.py tests/test_chat_mode_runner.py tests/test_prompts.py tests/test_repo_contracts.py -q`
Expected: FAIL until remaining gaps are covered.

**Step 3: Write minimal implementation**

Implement only the smallest code or helper changes needed to satisfy the newly added contract checks.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_debate_runtime.py tests/test_chat_mode_runner.py tests/test_prompts.py tests/test_repo_contracts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_debate_runtime.py tests/test_chat_mode_runner.py tests/test_prompts.py tests/test_repo_contracts.py
git commit -m "test: expand ARC contract regression coverage"
```

### Task 2: Add Lightweight Guard Helpers If Needed

**Files:**
- Create if needed: `tests/helpers/repo_contracts.py`
- Modify if needed: `tests/test_repo_contracts.py`

**Step 1: Write the failing test**

Only if text assertions become repetitive, add helper-driven tests and verify they fail before helper implementation.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_repo_contracts.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

Factor repetitive assertions into helpers without introducing a custom framework.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_repo_contracts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/helpers/repo_contracts.py tests/test_repo_contracts.py
git commit -m "test: add ARC repo contract helpers"
```

### Task 3: Final Verification For Entire Repair Program

**Step 1: Run full verification**

Run: `pytest -q`
Expected: PASS

**Step 2: Run a repository status check**

Run: `git status --short`
Expected: clean working tree except for any intentional final changes
