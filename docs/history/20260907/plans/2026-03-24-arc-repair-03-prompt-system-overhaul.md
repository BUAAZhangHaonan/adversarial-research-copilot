# ARC Repair 03 Prompt System Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current shallow prompt set with role-tight, production-grade prompts that are structurally clear, operationally useful, and compatible with ARC's runtime contracts.

**Architecture:** Treat prompts as interfaces. For each role, define mission, boundaries, use of prior context, expected sections, failure behavior, and machine-readable protocol. Add prompt-focused tests that verify contract markers without freezing every sentence.

**Tech Stack:** Markdown prompt files, pytest, string contract checks

---

### Task 1: Write Prompt Quality Contract Tests

**Files:**
- Create: `tests/test_prompts.py`
- Modify: `prompts/proposer.md`
- Modify: `prompts/skeptic.md`
- Modify: `prompts/moderator.md`
- Modify: `prompts/chat_mode/proposer_chat.md`
- Modify: `prompts/chat_mode/skeptic_chat.md`
- Modify: `prompts/chat_mode/moderator_chat.md`

**Step 1: Write the failing test**

Add tests that assert each prompt contains its required contract markers, such as:

- explicit role boundary
- use of prior blockers/revisions when applicable
- output language requirement
- structure guidance
- machine-readable YAML section where required
- chat-mode length/paragraph discipline markers

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py -q`
Expected: FAIL because current prompts are too vague and inconsistent.

**Step 3: Write minimal implementation**

Rewrite all prompt files so they:

- preserve ARC's adversarial roles
- provide concrete behavioral guidance
- eliminate sloppy phrasing
- stay compatible with runtime expectations introduced in package 02

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_prompts.py prompts/proposer.md prompts/skeptic.md prompts/moderator.md prompts/chat_mode/proposer_chat.md prompts/chat_mode/skeptic_chat.md prompts/chat_mode/moderator_chat.md
git commit -m "feat: overhaul ARC prompt system contracts"
```

### Task 2: Add Prompt Design Documentation

**Files:**
- Create: `docs/prompt-contracts.md`
- Modify if needed: `README.md`

**Step 1: Write the failing test**

If useful, extend `tests/test_prompts.py` to assert the doc exists and names the key role contracts and YAML ownership.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py -q`
Expected: FAIL until the prompt contract doc is added.

**Step 3: Write minimal implementation**

Document:

- role purposes
- runtime-owned vs prompt-owned fields
- how chat prompts differ from debate prompts
- what is allowed to change safely

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/prompt-contracts.md README.md tests/test_prompts.py
git commit -m "docs: add ARC prompt contract guide"
```

### Task 3: Verify Prompt Package

**Step 1: Run targeted verification**

Run: `pytest tests/test_prompts.py tests/test_rubric.py -q`
Expected: PASS

**Step 2: Run broader verification**

Run: `pytest -q`
Expected: PASS
