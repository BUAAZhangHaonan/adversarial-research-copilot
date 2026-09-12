# ARC Repair 04 Skills Docs Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make README, skills, and repo-facing descriptions match actual ARC behavior, artifact names, defaults, and project structure.

**Architecture:** First codify the names and defaults that the implementation actually uses, then align docs and skill files to that source of truth. Do not invent new artifacts merely to satisfy stale documentation.

**Tech Stack:** Markdown docs, skills markdown, pytest/string checks where appropriate

---

### Task 1: Add Docs And Skills Contract Checks

**Files:**
- Create: `tests/test_repo_contracts.py`
- Modify: `README.md`
- Modify: `skills/README.md`
- Modify: `skills/*.md`

**Step 1: Write the failing test**

Add tests that verify:

- artifact names are consistent with implementation
- `LATEST_RUN` usage matches code
- default cross-model claim matches config
- version mentions do not contradict `pyproject.toml`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_repo_contracts.py -q`
Expected: FAIL because current docs and skills drift from implementation.

**Step 3: Write minimal implementation**

Align docs and skills:

- fix artifact names and casing
- fix runtime path wording
- fix default strategy claims
- refresh outdated structure sections

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_repo_contracts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_repo_contracts.py README.md skills/README.md skills/*.md
git commit -m "docs: align ARC skills and README with implementation"
```

### Task 2: Verify Docs Alignment Package

**Step 1: Run targeted verification**

Run: `pytest tests/test_repo_contracts.py -q`
Expected: PASS

**Step 2: Run broader verification**

Run: `pytest -q`
Expected: PASS
