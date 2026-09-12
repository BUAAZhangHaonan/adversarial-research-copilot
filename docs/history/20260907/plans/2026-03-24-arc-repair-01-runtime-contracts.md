# ARC Repair 01 Runtime Contracts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `debate`, `pipeline`, and `chat-mode` recovery semantics trustworthy and testable, and remove input/state mixing during resume.

**Architecture:** Persist resumable state at the same granularity the runtime claims to recover, then make `resolve_run_dir` and each runner restore from that state rather than merely reusing a directory. Normalize input persistence so resumed runs do not overwrite the lineage before recovery decisions are made.

**Tech Stack:** Python 3.11, pytest, Typer, Pydantic, filesystem-based state artifacts

---

### Task 1: Define Resume Contract Tests For Debate

**Files:**
- Modify: `tests/test_state.py`
- Create or Modify: `tests/test_debate_runtime.py`
- Modify: `src/arc/orchestrator.py`

**Step 1: Write the failing test**

Add tests that verify:

- after one completed round but before final completion, debate state is resumable
- resume starts at the next round instead of resetting to round 1
- previous blockers and required revisions are recovered from persisted state

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_debate_runtime.py -q`
Expected: FAIL because debate recovery still depends on `final_state.json` written only at the end.

**Step 3: Write minimal implementation**

Update debate runtime so each round persists a resumable state snapshot, for example:

- write `final_state.json` or a dedicated resumable state file after each round
- `_prepare_state()` reads the latest resumable snapshot when `run_state.json` says `in_progress`
- recovery keeps round number, blockers, and previous revisions aligned

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_debate_runtime.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_debate_runtime.py src/arc/orchestrator.py
git commit -m "fix: make debate resume state recoverable"
```

### Task 2: Define Resume Contract Tests For Chat Mode

**Files:**
- Create or Modify: `tests/test_chat_mode_runner.py`
- Modify: `src/arc/runners/chat_mode_runner.py`

**Step 1: Write the failing test**

Add tests that verify:

- `resume=True` restores prior completed rounds from `chat_mode_state.json`
- resumed execution continues from the next round
- prior transcript artifacts are extended rather than silently restarted from round 1

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_mode_runner.py -q`
Expected: FAIL because `run_chat_mode()` always initializes `rounds = []` and restarts the loop.

**Step 3: Write minimal implementation**

Implement a compact chat resume loader:

- read `chat_mode_state.json` when present and fresh
- restore `rounds`, `prior_summary`, and next round index
- keep artifact writing consistent with resumed history

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_mode_runner.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_chat_mode_runner.py src/arc/runners/chat_mode_runner.py
git commit -m "fix: make chat mode resume recover prior rounds"
```

### Task 3: Protect Input Lineage During Resume

**Files:**
- Modify: `tests/test_pipeline_runner.py`
- Modify: `tests/test_debate_runtime.py`
- Modify: `src/arc/orchestrator.py`
- Modify: `src/arc/runners/pipeline_runner.py`

**Step 1: Write the failing test**

Add tests that verify resumed runs do not overwrite `INPUT_IDEA.txt` or `TOPIC.txt` before the runtime decides whether recovery is valid.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_debate_runtime.py tests/test_pipeline_runner.py -q`
Expected: FAIL because input files are written before resume validation.

**Step 3: Write minimal implementation**

Reorder runtime flow:

- resolve recovery first
- if resuming an existing in-progress run, validate that the incoming idea/topic matches persisted input
- only write input artifacts after the runtime chooses new-run vs resume path

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_debate_runtime.py tests/test_pipeline_runner.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_debate_runtime.py tests/test_pipeline_runner.py src/arc/orchestrator.py src/arc/runners/pipeline_runner.py
git commit -m "fix: preserve input lineage during resume"
```

### Task 4: Verify Runtime Contract Package

**Files:**
- Modify if needed: `README.md`

**Step 1: Run targeted verification**

Run: `pytest tests/test_debate_runtime.py tests/test_chat_mode_runner.py tests/test_pipeline_runner.py -q`
Expected: PASS

**Step 2: Run broader regression verification**

Run: `pytest -q`
Expected: PASS

**Step 3: Commit final package polish if docs changed**

```bash
git add README.md
git commit -m "docs: clarify runtime resume behavior"
```
