"""只读访问 ARC v2 的 SQLite 权威存储（arc.sqlite）。

ARC 0.2 起状态与预算的权威在 DATA_DIR/arc.sqlite（runs/campaigns/discovery_ideas/
cards 等表，内容均为 JSON 列）。web 层只读打开（mode=ro），不参与写入；
CLI 子进程写入 WAL 提交后这里立即可见。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# 与前端/任务层约定的模式（ARC 内部 develop/run 统一映射为 debate 语义的压力测试）
ARC_MODES = ("discover", "develop", "run")

# jobs 表里存的任务模式 -> ARC CLI mode
JOB_MODE_TO_ARC = {"discover": "discover", "develop": "develop", "debate": "run"}


class ArcStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    @contextmanager
    def _connect(self):
        if not self.available:
            yield None
            return
        try:
            conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro", uri=True, timeout=3)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error:
            yield None
            return
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------- runs
    def get_run(self, run_id: str) -> dict | None:
        """返回 RunRecord dict（含 status/stop_reason/assessment/state/config）。"""
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                row = conn.execute(
                    "SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
            except sqlite3.Error:
                return None
        if row is None:
            return None
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return None

    def get_task(self, task_id: str) -> dict | None:
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                row = conn.execute("SELECT data FROM tasks WHERE id=?", (task_id,)).fetchone()
                return json.loads(row["data"]) if row else None
            except (sqlite3.Error, json.JSONDecodeError):
                return None

    def _task_state(self, task: dict | None) -> dict | None:
        """Read only the referenced task snapshot, bounded and inside ARC artifacts."""
        artifact = (task or {}).get("response_artifact_path")
        if not isinstance(artifact, str) or not artifact:
            return None
        root = (self.db_path.parent / "artifacts").resolve()
        path = (root / artifact).resolve()
        if not path.is_relative_to(root):
            return None
        try:
            with path.open("rb") as stream:
                raw = stream.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                return None
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    def pending_draft_decision(self, run_id: str) -> str | None:
        run = self.get_run(run_id) or {}
        key = (run.get("state") or {}).get("pending_task")
        if not key:
            return None
        saved = self._task_state(self.get_task(f"{run_id}.{key}")) or {}
        try:
            content = ((saved.get("response") or {}).get("message") or {}).get("content") or ""
            envelope = json.loads(content)
            return (((envelope.get("result") or {}).get("note")) or {}).get("decision")
        except (ValueError, TypeError, AttributeError):
            return None

    def pause_recovery(self, run: dict) -> dict | None:
        """One recovery plan shared by submission and the run detail view."""
        status = run.get("status")
        if status == "PAUSED_BUDGET":
            return {"kind": "budget", "action": "resume", "actionable": True}
        if status not in ("PAUSED_PROTOCOL", "PAUSED_EXTERNAL"):
            return None
        run_id = run.get("run_id") or ""
        key = self.paused_task_key(run_id, run)
        if status == "PAUSED_PROTOCOL":
            if run.get("stop_reason") == "TOOL_CORRECTION_TARGET_CHANGED" and self._resumable_read_length_alias(run, key):
                return {"kind": "resume", "action": "resume", "task_key": key, "actionable": True,
                        "reason": "已保存的工具纠正仅将同值读取长度字段改为正确名称，来源、位置和长度均未改变。继续会复核并复用保存响应，保留原记录。"}
            if run.get("stop_reason") == "SUBJECT_OR_TASK_MISMATCH" and self._resumable_retry_identity(run, key):
                return {"kind": "resume", "action": "resume", "task_key": key, "actionable": True,
                        "reason": "已保存响应回显了显式前序任务编号，研究对象完全匹配。继续后会验证并复用这份响应，保留原始内容与审计记录。"}
            return {"kind": "retry", "action": "retry-task", "task_key": key,
                    "actionable": bool(key),
                    "reason": None if key else "未找到暂停任务，需先检查任务记录。"}
        if run.get("stop_reason") == "critical_source_unavailable":
            if run.get("mode") == "discover" and (run.get("state") or {}).get("discover_first"):
                # Current discovery handles its old pending CHECK itself, including
                # discuss drafts: write a new limited result or park this draw.
                return {"kind": "evidence", "action": "resume", "task_key": key, "actionable": True}
            allowed = bool(key) and self.pending_draft_decision(run_id) in ("lead", "drop")
            return {"kind": "defer", "action": "defer-evidence", "task_key": key,
                    "actionable": allowed,
                    "reason": None if allowed else "现有草稿不满足证据延期条件，需人工检查材料和恢复方式。"}
        return {"kind": "resume", "action": "resume", "task_key": key, "actionable": True}

    def pause_diagnostics(self, run: dict) -> dict | None:
        """Expose validation messages and evidence questions, never prompts or raw responses."""
        if not str(run.get("status") or "").startswith("PAUSED_"):
            return None
        run_id = run.get("run_id") or ""
        key = self.paused_task_key(run_id, run)
        task_id = f"{run_id}.{key}" if key else None
        task = self.get_task(task_id) if task_id else None
        saved = self._task_state(task)
        errors, truncated = [], False
        if (task or {}).get("status") == "PAUSED_PROTOCOL":
            raw_errors = (saved or {}).get("final_validation_errors",
                (saved or {}).get("repair_validation_errors", [])) or []
            if not isinstance(raw_errors, list):
                raw_errors = [raw_errors]
            truncated = len(raw_errors) > 10
            for error in raw_errors[:10]:
                if isinstance(error, dict):
                    # Pydantic diagnostics may contain the entire rejected input;
                    # publish only the location and message fields.
                    loc = error.get("loc") or []
                    where = ".".join(str(x) for x in loc[:20]) if isinstance(loc, list) else ""
                    message = str(error.get("msg") or error.get("message") or error.get("type") or "校验失败")
                    text = f"{where}: {message}" if where else message
                else:
                    text = str(error)
                truncated |= len(text) > 2000
                errors.append(text[:2000])
        if not errors and (task or {}).get("error"):
            errors.append(str(task["error"])[:2000])
        requests = (run.get("state") or {}).get("pending_evidence_requests") or []
        if not isinstance(requests, list):
            requests = []
        truncated |= len(requests) > 6
        evidence = []
        for request in requests[:6]:
            if not isinstance(request, dict):
                continue
            question = str(request.get("question") or "")
            sources = request.get("target_source_ids") or []
            sources = sources if isinstance(sources, list) else []
            truncated |= len(question) > 1200 or len(sources) > 12
            evidence.append({"question": question[:1200],
                             "source_ids": [str(x)[:120] for x in sources[:12]]})
        return {"task_id": task_id, "task_status": (task or {}).get("status"),
                "stop_reason": run.get("stop_reason"), "errors": errors,
                "evidence_requests": evidence, "truncated": truncated,
                "details_available": saved is not None}

    def _resumable_read_length_alias(self, run: dict, key: str | None) -> bool:
        """Prove the saved batch changed only read_paper.limit to equal limit_chars."""
        if not key:
            return False
        task = self.get_task(f"{run.get('run_id')}.{key}") or {}
        if (task.get("status") != "PAUSED_PROTOCOL" or task.get("accepted_result") is not None
                or task.get("error") != "TOOL_CORRECTION_TARGET_CHANGED"):
            return False
        saved = self._task_state(task) or {}
        if (saved.get("tool_correction_failure") != "TOOL_CORRECTION_TARGET_CHANGED"
                or "pending_model" not in saved or saved["pending_model"] is not None
                or "pending_tool" not in saved or saved["pending_tool"] is not None):
            return False
        correction = saved.get("tool_correction")
        response = saved.get("response")
        if not isinstance(correction, dict) or not isinstance(response, dict):
            return False
        if correction.get("phase") != "awaiting" or not response.get("completed_at"):
            return False
        failures = correction.get("failures")
        message = response.get("message")
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if (not isinstance(failures, list) or not isinstance(calls, list)
                or not failures or len(failures) != len(calls)):
            return False
        try:
            for original, call in zip(failures, calls):
                if not isinstance(original, dict) or not isinstance(call, dict):
                    return False
                function = call.get("function") or {}
                if (original.get("name") != "read_paper" or call.get("type") != "function"
                        or function.get("name") != "read_paper"):
                    return False
                before = original.get("arguments")
                after = json.loads(function.get("arguments") or "")
                errors = original.get("errors")
                properties = (original.get("parameters") or {}).get("properties") or {}
                if (not isinstance(before, dict) or not isinstance(after, dict)
                        or "limit" not in before or "limit_chars" in before
                        or type(before["limit"]) is not int or before["limit"] <= 0
                        or "limit_chars" not in properties or "limit" in properties
                        or not isinstance(errors, list) or not errors
                        or any(not isinstance(error, dict) or error.get("path") != ["limit"]
                               or error.get("validator") != "additionalProperties"
                               or error.get("expected") is not False for error in errors)):
                    return False
                expected = {k: v for k, v in before.items() if k != "limit"}
                expected["limit_chars"] = before["limit"]
                # Serialization compares JSON types too: True, 1 and 1.0 must not
                # silently compare equal when verifying unchanged arguments.
                if json.dumps(expected, sort_keys=True, allow_nan=False) != json.dumps(after, sort_keys=True, allow_nan=False):
                    return False
        except (ValueError, TypeError, AttributeError):
            return False
        return True

    def _resumable_retry_identity(self, run: dict, key: str | None) -> bool:
        """Only the explicit predecessor's task ID can be normalized on resume."""
        if not key:
            return False
        run_id = run.get("run_id") or ""
        task_id = f"{run_id}.{key}"
        task = self.get_task(task_id) or {}
        if (task.get("status") != "PAUSED_PROTOCOL" or task.get("accepted_result") is not None
                or task.get("error") != "SUBJECT_OR_TASK_MISMATCH"):
            return False
        inputs = (run.get("state") or {}).get("task_inputs", {}).get(key, {})
        expected = inputs.get("subject")
        previous = (inputs.get("payload", {}).get("protocol_retry") or {}).get("previous_task_id")
        if (not isinstance(expected, dict) or expected.get("run_id") != run_id
                or not isinstance(previous, str) or previous == task_id
                or not previous.startswith(run_id + ".")):
            return False
        saved = self._task_state(task) or {}
        try:
            raw = ((saved.get("response") or {}).get("message") or {}).get("content") or ""
            envelope = json.loads(raw)
            return (isinstance(envelope, dict) and envelope.get("task_id") == previous
                    and envelope.get("subject") == expected)
        except (ValueError, TypeError, AttributeError):
            return False

    def paused_task_key(self, run_id: str, run: dict | None = None) -> str | None:
        """Resolve pending tasks through recorded retries; exclude superseded failures."""
        run = run or self.get_run(run_id) or {}
        state = run.get("state") or {}
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                rows = conn.execute("SELECT id, data FROM tasks WHERE run_id=?", (run_id,)).fetchall()
            except sqlite3.Error:
                return None
        prefix = run_id + "."
        records = {}
        for row in rows:
            try:
                task = json.loads(row["data"])
            except (ValueError, TypeError):
                continue
            if isinstance(task, dict):
                key = row["id"][len(prefix):] if row["id"].startswith(prefix) else row["id"]
                records[key] = task

        def current(key):
            seen = set()
            while isinstance(key, str) and key not in seen:
                seen.add(key)
                history = (state.get("task_retries") or {}).get(key) or []
                replacement = history[-1].get("replacement_key") if history else None
                if not replacement or replacement not in records:
                    break
                key = replacement
            task = records.get(key) or {}
            if (task.get("status") in ("PAUSED_PROTOCOL", "PAUSED_EXTERNAL")
                    and task.get("accepted_result") is None and key not in state):
                return key
            return None

        pending = state.get("pending_task")
        if isinstance(pending, str) and pending:
            key = current(pending)
            if key:
                return key
        for key in sorted(records, key=lambda k: records[k].get("updated_at") or "", reverse=True):
            resolved = current(key)
            if resolved:
                return resolved
        return None

    def run_topic(self, run: dict) -> str:
        """run 的展示主题：discover 取 campaign.topic，其余按输入来源逐级回退。"""
        mode = run.get("mode")
        if mode == "discover" and run.get("campaign_id"):
            campaign = self.get_campaign(run["campaign_id"])
            if campaign:
                return campaign.get("topic") or ""
        state = run.get("state") or {}
        text = state.get("imported_input")
        if not text:
            idea = state.get("idea_input") or {}
            seed = idea.get("seed") or {}
            text = seed.get("title") or idea.get("original_question") or ""
        if not text and run.get("card_id"):
            card = self.get_card(run["card_id"], run.get("card_version"))
            text = ((card or {}).get("draft") or {}).get("title") or ""
        if isinstance(text, str):
            return text.strip().split("\n", 1)[0][:200]
        return ""

    def get_card(self, card_id: str, version: int | None = None) -> dict | None:
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                if version is None:
                    row = conn.execute(
                        "SELECT data FROM cards WHERE card_id=? ORDER BY version DESC LIMIT 1",
                        (card_id,)).fetchone()
                else:
                    row = conn.execute(
                        "SELECT data FROM cards WHERE card_id=? AND version=?",
                        (card_id, version)).fetchone()
            except sqlite3.Error:
                return None
        if row is None:
            return None
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return None

    def get_campaign(self, campaign_id: str) -> dict | None:
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                row = conn.execute(
                    "SELECT data FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
            except sqlite3.Error:
                return None
        if row is None:
            return None
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return None

    def budget_summary(self, account_id: str) -> dict | None:
        """只读复现 ARC BudgetLedger 的账户聚合，保留未计价和未结算边界。"""
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                conn.execute('BEGIN')
                account = conn.execute(
                    "SELECT limit_micro FROM budget_accounts WHERE account_id=?", (account_id,)
                ).fetchone()
                if account is None:
                    return None
                totals = conn.execute("""
                    WITH RECURSIVE descendants(id) AS (
                      SELECT ? UNION ALL SELECT a.account_id FROM budget_accounts a
                      JOIN descendants d ON a.parent_id=d.id)
                    SELECT
                      COALESCE(SUM(CASE WHEN state='SETTLED' THEN lower_micro ELSE 0 END),0) AS lower,
                      COALESCE(SUM(CASE WHEN state='SETTLED' THEN upper_micro ELSE 0 END),0) AS upper,
                      COALESCE(SUM(reserved_micro),0) AS reserved,
                      COALESCE(SUM(CASE WHEN state='UNKNOWN' THEN lower_micro ELSE 0 END),0) AS unsettled_lower,
                      COALESCE(SUM(CASE WHEN state='UNKNOWN' THEN 1 ELSE 0 END),0) AS unknown,
                      COALESCE(SUM(CASE WHEN cost_status='unmetered' AND state!='NOT_SENT' THEN 1 ELSE 0 END),0) AS unmetered,
                      COUNT(*) AS calls FROM budget_calls WHERE account_id IN (SELECT id FROM descendants)
                """, (account_id,)).fetchone()
            except sqlite3.Error:
                return None
        limit, upper, reserved = account['limit_micro'], totals['upper'], totals['reserved']
        return {
            'limit_cny': limit / 1_000_000,
            'spent_lower_cny': totals['lower'] / 1_000_000,
            'spent_upper_cny': upper / 1_000_000,
            'reserved_cny': reserved / 1_000_000,
            'remaining_cny': (limit - upper - reserved) / 1_000_000,
            'unsettled_lower_cny': totals['unsettled_lower'] / 1_000_000,
            'call_count': totals['calls'], 'unknown_calls': totals['unknown'],
            'unmetered_calls': totals['unmetered'],
            'total_cost_complete': not bool(totals['unknown'] or totals['unmetered'] or reserved),
            'cost_scope': 'metered_costs_only' if totals['unmetered'] else 'recorded_costs',
        }

    def list_runs(self, modes: tuple[str, ...] = ARC_MODES) -> list[dict]:
        """列出 ARC runs，按创建时间倒序；每项附 topic 摘要。"""
        out: list[dict] = []
        with self._connect() as conn:
            if conn is None:
                return out
            try:
                rows = conn.execute("SELECT id, data FROM runs").fetchall()
            except sqlite3.Error:
                return out
        for row in rows:
            try:
                run = json.loads(row["data"])
            except json.JSONDecodeError:
                continue
            if run.get("mode") not in modes:
                continue
            out.append(run)
        out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        for run in out:
            run["topic"] = self.run_topic(run)
        return out

    # ---------------------------------------------------- discovery ideas
    def discovery_ideas(self, run_id: str) -> list[dict]:
        """该 discover run 的全部灵感卡（seed/sketch/triage/note/status）。"""
        with self._connect() as conn:
            if conn is None:
                return []
            try:
                rows = conn.execute(
                    "SELECT data FROM discovery_ideas WHERE run_id=? "
                    "ORDER BY json_extract(data,'$.created_at')", (run_id,)).fetchall()
            except sqlite3.Error:
                return []
        ideas = []
        for row in rows:
            try:
                ideas.append(json.loads(row["data"]))
            except json.JSONDecodeError:
                continue
        return ideas

    def get_idea(self, idea_id: str) -> dict | None:
        with self._connect() as conn:
            if conn is None:
                return None
            try:
                row = conn.execute(
                    "SELECT data FROM discovery_ideas WHERE id=?", (idea_id,)).fetchone()
            except sqlite3.Error:
                return None
        if row is None:
            return None
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return None
