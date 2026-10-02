"""任务编排：spawn ARC v2 CLI 子进程 + SQLite/日志双通道进度 + 取消/续跑。

后端零改动约定：所有模式都以 `<backend_root>/.venv/bin/arc --data-dir <arc_data>
--env-file <backend_root>/.env ...` 子进程运行。ARC 0.2 的状态权威在
arc.sqlite（runs/campaigns/discovery_ideas），进度事件由 CLI 持续打印到
stdout（JSON 行，含 budget/draws/rounds/task 状态）。
"""
from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .arcstore import JOB_MODE_TO_ARC, ArcStore
from .config import Config
from .db import connect

def _child_env() -> dict[str, str]:
    """ARC 子进程环境：剥掉 SOCKS 型 ALL_PROXY。

    ARC 的 httpx 未装 socksio，读到 socks5h 的 ALL_PROXY 会在构造客户端时直接
    ImportError（任务秒失败）；同机的 http(s)_proxy 走同一个代理，剥掉即可。
    """
    env = os.environ.copy()
    for key in ("ALL_PROXY", "all_proxy"):
        val = env.get(key, "")
        if val.startswith(("socks5", "socks4", "socks://")):
            del env[key]
    return env

# ARC run 终态 -> job 展示状态
_RUN_FINAL_JOB_STATUS = {
    "COMPLETED": "completed",
    "PAUSED_BUDGET": "paused",
    "PAUSED_EXTERNAL": "paused",
    "PAUSED_PROTOCOL": "paused",
    "PAUSED_SCOPE_CHANGE": "paused",
    "ERROR": "failed",
    "CANCELLED": "cancelled",
}


class JobError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # kill(0) 对僵尸进程同样成功：父进程未 wait 时子进程以 Z 状态滞留，
    # 必须读 /proc 状态把它当作已退出，否则任务状态永远卡在 running
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            state = f.read().rsplit(") ", 1)[1].split()[0]
        return state != "Z"
    except (OSError, IndexError):
        return True


def _pid_start_ticks(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _budget_summary(budget: dict | None) -> dict | None:
    if not isinstance(budget, dict):
        return None
    def _num(key: str) -> float | None:
        v = budget.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None
    return {
        "limit_cny": _num("limit_cny"),
        "spent_lower_cny": _num("spent_lower_cny"),
        "spent_upper_cny": _num("spent_upper_cny"),
        "reserved_cny": _num("reserved_cny"),
        "remaining_cny": _num("remaining_cny"),
        "call_count": budget.get("call_count"),
        "unknown_calls": budget.get("unknown_calls"),
        "unmetered_calls": budget.get("unmetered_calls"),
        "total_cost_complete": budget.get("total_cost_complete"),
        "cost_scope": budget.get("cost_scope"),
        "unsettled_lower_cny": _num("unsettled_lower_cny"),
    }


class JobManager:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = ArcStore(cfg.arc_db)
        self._procs: dict[str, subprocess.Popen] = {}
        self._submit_lock = threading.Lock()

    def _job_process_alive(self, row) -> bool:
        """Never claim a reused PID as this job's subprocess."""
        job = dict(row)
        pid = job.get('pid')
        if not _pid_alive(pid):
            return False
        expected = job.get('pid_start_ticks')
        if expected is not None:
            return _pid_start_ticks(pid) == expected
        # Older rows predate start-time recording. Require the unique stdout
        # log as well as the executable, data directory and process group.
        try:
            args = Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')
            data_arg = args.index('--data-dir')
            return (str(self.cfg.arc_bin) in args
                    and args[data_arg + 1] == str(self.cfg.arc_data_dir)
                    and os.getpgid(pid) == pid
                    and Path(f'/proc/{pid}/cwd').resolve() == self.cfg.arc_data_dir.resolve()
                    and bool(job.get('log_path'))
                    and Path(f'/proc/{pid}/fd/1').resolve() == Path(job['log_path']).resolve())
        except (OSError, UnicodeError, ValueError, IndexError):
            return False

    # ------------------------------------------------------------- submit
    def _base_argv(self) -> list[str]:
        return [
            str(self.cfg.arc_bin),
            "--data-dir", str(self.cfg.arc_data_dir),
            "--env-file", str(self.cfg.arc_env_file),
        ]

    def _build_argv(self, mode: str, params: dict, job_id: str) -> list[str]:
        arc_mode = JOB_MODE_TO_ARC.get(mode)
        budget = params.get("budget_cny")
        if arc_mode == "discover":
            argv = self._base_argv() + ["discover", params["topic"]]
            if params.get("draws"):
                argv += ["--draws", str(int(params["draws"]))]
            if budget:
                argv += ["--budget-cny", str(budget)]
            return argv
        if arc_mode in ("develop", "run"):
            argv = self._base_argv() + [arc_mode]
            if params.get("idea_id"):
                argv += ["--idea", params["idea_id"]]
            elif params.get("card_id"):
                argv += ["--card", params["card_id"]]
                if params.get("card_version"):
                    argv += ["--version", str(int(params["card_version"]))]
            elif params.get("proposal"):
                proposal_file = self.cfg.uploads_dir / f"{job_id}_proposal.md"
                proposal_file.write_text(params["proposal"], encoding="utf-8")
                argv += ["--proposal", str(proposal_file)]
            elif params.get("question"):
                argv += ["--question", params["question"]]
            else:
                raise JobError("需要提供研究问题、提案或来源卡")
            if budget:
                argv += ["--budget-cny", str(budget)]
            return argv
        if mode == "resume":
            run_id = params["run_id"]
            run = self.store.get_run(run_id) or {}
            recovery = self.store.pause_recovery(run)
            if not recovery or not recovery["actionable"]:
                raise JobError((recovery or {}).get("reason") or "当前状态没有可用的恢复方式")
            if recovery["action"] in ("retry-task", "defer-evidence"):
                argv = self._base_argv() + [
                    "retry-task", run_id, "--task-key", recovery["task_key"],
                    "--reason", str(params.get("reason") or "web 端手动重试"),
                ]
                if recovery["action"] == "defer-evidence":
                    argv.append("--defer-evidence")
                return argv
            # discover_first handles unavailable evidence in its normal workflow:
            # a new limited conclusion, or a parked draw with the rest continuing.
            argv = self._base_argv() + ["resume", run_id]
            if params.get("add_budget_cny"):
                argv += ["--add-budget-cny", str(params["add_budget_cny"])]
            return argv
        raise JobError(f"unknown mode: {mode}")

    def validate_params(self, mode: str, params: dict) -> dict:
        try:
            return self._validate_params(mode, params)
        except (ValueError, TypeError, OverflowError) as exc:
            raise JobError('任务参数格式错误') from exc

    def _validate_params(self, mode: str, params: dict) -> dict:
        lim = self.cfg.limits
        if mode == "discover":
            topic = str(params.get("topic") or "").strip()
            if not topic:
                raise JobError("召唤主题不能为空")
            if len(topic) > 2000:
                raise JobError("主题过长（>2000 字符）")
            out = {"topic": topic}
            if params.get("draws") is not None:
                draws = int(params["draws"])
                if not (1 <= draws <= lim.discover_draws_max):
                    raise JobError(f"抽卡次数需在 1-{lim.discover_draws_max} 之间")
                out["draws"] = draws
            if params.get("budget_cny") is not None:
                budget = float(params["budget_cny"])
                if not (0 < budget <= lim.discover_budget_cny_max):
                    raise JobError(f"预算需在 0-{lim.discover_budget_cny_max} 元之间")
                out["budget_cny"] = budget
            return out
        if mode in ("develop", "debate"):
            max_chars = (lim.develop_question_max_chars if mode == "develop"
                         else lim.debate_proposal_max_chars)
            budget_cap = (lim.develop_budget_cny_max if mode == "develop"
                          else lim.debate_budget_cny_max)
            out: dict = {}
            inputs = [k for k in ("question", "proposal", "idea_id", "card_id")
                      if params.get(k)]
            if not inputs:
                raise JobError("需要提供研究问题、完整提案或来源卡")
            if "question" in inputs:
                question = str(params["question"]).strip()
                if not question:
                    raise JobError("研究问题不能为空")
                if len(question) > max_chars:
                    raise JobError(f"内容过长（>{max_chars} 字符）")
                out["question"] = question
            if "proposal" in inputs:
                if "question" in inputs:
                    raise JobError("研究问题与完整提案只能二选一")
                proposal = str(params["proposal"]).strip()
                if not proposal:
                    raise JobError("提案不能为空")
                if len(proposal) > lim.debate_proposal_max_chars:
                    raise JobError(f"提案过长（>{lim.debate_proposal_max_chars} 字符）")
                out["proposal"] = proposal
            if "idea_id" in inputs:
                if "question" in inputs or "proposal" in inputs:
                    raise JobError("来源灵感与研究问题/提案互斥")
                idea_id = str(params["idea_id"]).strip()
                if not idea_id:
                    raise JobError("idea_id 不能为空")
                out["idea_id"] = idea_id
            if "card_id" in inputs:
                if "question" in inputs or "proposal" in inputs or "idea_id" in inputs:
                    raise JobError("来源卡与其他输入互斥")
                out["card_id"] = str(params["card_id"]).strip()
                if params.get("card_version") is not None:
                    out["card_version"] = max(1, int(params["card_version"]))
            if params.get("budget_cny") is not None:
                budget = float(params["budget_cny"])
                if not (0 < budget <= budget_cap):
                    raise JobError(f"预算需在 0-{budget_cap} 元之间")
                out["budget_cny"] = budget
            return out
        if mode == "resume":
            run_id = str(params.get("run_id") or "").strip()
            if not run_id:
                raise JobError("run_id 不能为空")
            run = self.store.get_run(run_id)
            if run is None:
                raise JobError(f"ARC run 不存在: {run_id}")
            if run.get('status') == 'PAUSED_SCOPE_CHANGE':
                raise JobError('研究范围已变更，需要明确选择后创建新 run，不能直接续跑')
            if run.get("status") not in ("PAUSED_BUDGET", "PAUSED_EXTERNAL", "PAUSED_PROTOCOL"):
                raise JobError(f"该 run 当前状态为 {run.get('status')}，无需续跑")
            recovery = self.store.pause_recovery(run)
            if not recovery or not recovery["actionable"]:
                raise JobError((recovery or {}).get("reason") or "当前状态没有可用的恢复方式")
            out = {"run_id": run_id}
            if params.get("reason") is not None:
                reason = str(params["reason"]).strip()
                if len(reason) > 200:
                    raise JobError(f"重试原因过长（>200 字符）")
                if reason:
                    out["reason"] = reason
            if params.get("add_budget_cny") is not None:
                extra = float(params["add_budget_cny"])
                if not (0 < extra <= lim.resume_budget_cny_max):
                    raise JobError(f"追加预算需在 0-{lim.resume_budget_cny_max} 元之间")
                out["add_budget_cny"] = extra
            return out
        raise JobError(f"unknown mode: {mode}")

    def submit(self, mode: str, raw_params: dict, user) -> dict:
        params = self.validate_params(mode, raw_params)
        # Admission and spawn are serialized; BEGIN IMMEDIATE also protects
        # the shared database if more than one application worker is used.
        with self._submit_lock:
            return self._submit(mode, params, user)

    def _submit(self, mode: str, params: dict, user) -> dict:
        self.list_jobs()  # release slots whose child has already exited
        conn = connect(self.cfg.db_path)
        proc = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            if mode == "resume" and conn.execute(
                "SELECT 1 FROM jobs WHERE status='running' AND run_dir=?", (params['run_id'],)
            ).fetchone():
                raise JobError("该 run 已有恢复任务在运行", status=409)
            if mode == 'resume':
                # Recheck after taking the database admission lock: another
                # request may have changed ARC since initial validation.
                self.validate_params(mode, params)
            running = conn.execute(
                "SELECT COUNT(*) AS n FROM jobs WHERE status='running'"
            ).fetchone()["n"]
            if running >= self.cfg.max_concurrent_jobs:
                raise JobError(
                    f"卡池冷却中：已有 {running} 个任务在运行（上限 {self.cfg.max_concurrent_jobs}）",
                    status=429,
                )
            job_id = "j" + format(int(time.time() * 1000), "x") + format(random.getrandbits(16), "04x")
            log_path = self.cfg.jobs_log_dir / f"{job_id}.log"
            argv = self._build_argv(mode, params, job_id)
            with open(log_path, "wb") as log_f:
                proc = subprocess.Popen(
                    argv,
                    cwd=str(self.cfg.arc_data_dir),
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    env=_child_env(),
                )
            self._procs[job_id] = proc
            conn.execute(
                "INSERT INTO jobs(id, mode, params, user_id, username, status, pid, log_path, "
                "created_at, started_at, run_dir, pid_start_ticks) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, mode, json.dumps(params, ensure_ascii=False), user.id, user.username,
                 "running", proc.pid, str(log_path), _utcnow(), _utcnow(), params.get('run_id'),
                 _pid_start_ticks(proc.pid)),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                self._procs.pop(job_id, None)
            raise
        finally:
            conn.close()

        if mode == "resume":
            self._set_run_dir(job_id, params["run_id"])
        else:
            run_dir = self._detect_run_dir(job_id, mode, params, quick_seconds=5)
            if run_dir:
                self._set_run_dir(job_id, run_dir)
        return {"job_id": job_id}

    # ---------------------------------------------------- run dir 关联
    def _detect_run_dir(self, job_id: str, mode: str, params: dict,
                        quick_seconds: float = 0) -> str | None:
        """只认领该子进程自己的 stdout run_id；主题和时间不能标识一次执行。"""
        conn = connect(self.cfg.db_path)
        try:
            row = conn.execute(
                "SELECT log_path, run_dir FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None or row["run_dir"]:
            return row["run_dir"] if row else None

        deadline = time.monotonic() + quick_seconds
        while True:
            for event in self._log_events(row["log_path"]):
                found = event.get("run_id")
                run = self.store.get_run(found) if isinstance(found, str) else None
                if run and run.get("mode") == JOB_MODE_TO_ARC.get(mode):
                    self._set_run_dir(job_id, found)
                    return found
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.5)

    def _set_run_dir(self, job_id: str, run_dir: str) -> None:
        conn = connect(self.cfg.db_path)
        try:
            conn.execute(
                "UPDATE jobs SET run_dir=? WHERE id=? AND run_dir IS NULL", (run_dir, job_id)
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------- status
    def _log_tail(self, log_path: str | None, max_bytes: int = 6000) -> str:
        if not log_path:
            return ""
        p = Path(log_path)
        if not p.exists():
            return ""
        try:
            with open(p, "rb") as f:
                size = p.stat().st_size
                f.seek(max(0, size - max_bytes))
                return f.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    def _log_events(self, log_path: str | None, max_events: int = 60) -> list[dict]:
        """解析 CLI stdout 的 JSON 进度事件行（倒序取最近若干条，再正序返回）。"""
        if not log_path:
            return []
        p = Path(log_path)
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        events: list[dict] = []
        for line in data.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and ("task_id" in event or "run_id" in event):
                events.append(event)
        return events[-max_events:]

    def _progress(self, mode: str, run_dir: str | None, log_path: str | None) -> dict | None:
        run = self.store.get_run(run_dir) if run_dir else None
        events = self._log_events(log_path)
        if run is None and not events:
            return None

        prog: dict = {"run_id": run_dir}
        state = (run or {}).get("state") or {}
        if run:
            prog.update({
                "status": run.get("status"),
                "stop_reason": run.get("stop_reason"),
                "assessment": run.get("assessment"),
                "rounds_completed": state.get("rounds_completed"),
                "card_id": run.get("card_id"),
                "card_version": run.get("card_version"),
            })
            campaign = self.store.get_campaign(run["campaign_id"]) if run.get("campaign_id") else None
            if campaign:
                prog["draws"] = {"started": campaign.get("draws_started"),
                                 "max": campaign.get("max_draws")}

        last_budget = None
        tasks: list[dict] = []
        for event in events:
            if run_dir and event.get('run_id') != run_dir:
                continue
            if isinstance(event.get("budget"), dict):
                last_budget = event["budget"]
            if isinstance(event.get("cost"), dict):
                last_budget = event["cost"]
            if event.get("run_status"):
                prog.setdefault("status", event.get("run_status"))
            if event.get("draws_started") is not None:
                started = event.get("draws_started")
                # 日志事件比 SQLite campaign 更即时，取较大者
                cur = prog.get("draws") or {}
                if started is not None and started >= (cur.get("started") or 0):
                    prog["draws"] = {"started": started, "max": event.get("max_draws") or cur.get("max")}
            if event.get("rounds_completed") is not None:
                prog["rounds_completed"] = event["rounds_completed"]
            task_id = event.get("task_id")
            if task_id and event.get("status"):
                short = str(task_id)
                if run_dir and short.startswith(run_id_prefix(run_dir)):
                    short = short[len(run_dir):].lstrip(".")
                tasks.append({"task_id": short, "status": event["status"]})
        ledger = self.store.budget_summary((run or {}).get('budget_account_id') or run_dir) if run_dir else None
        prog["budget"] = _budget_summary(ledger or last_budget)
        # 去重保留每个任务最后状态
        dedup: dict[str, str] = {}
        for t in tasks:
            dedup[t["task_id"]] = t["status"]
        prog["tasks"] = [{"task_id": k, "status": v} for k, v in dedup.items()][-20:]
        # A candidate may advance to CHECK while its raw task remains external-paused.
        # Preserve the event status; annotate only an explicit unverified handoff.
        handoffs = {
            marker.get("source_task_id") for key, marker in state.items()
            if key.endswith("_provisional") and isinstance(marker, dict)
            and marker.get("result_status") == "needs_evidence"
            and marker.get("research_verified") is False
            and marker.get("handoff") == "candidate_prestudy"
            and isinstance(marker.get("source_task_id"), str)
        }
        for task in prog["tasks"]:
            if run_dir and f"{run_dir}.{task['task_id']}" in handoffs:
                task.update(handoff="candidate_prestudy", research_verified=False)
        if prog["tasks"]:
            prog["current"] = prog["tasks"][-1]["task_id"]
        return prog

    def _finalize_if_dead(self, job_id: str) -> dict | None:
        """进程已退出但状态还是 running：以 ARC run 终态为准收割。"""
        conn = connect(self.cfg.db_path)
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["status"] != "running":
                return dict(row) if row else None
        finally:
            conn.close()

        row = dict(row)
        if not row.get('run_dir'):
            row['run_dir'] = self._detect_run_dir(
                job_id, row['mode'], json.loads(row['params']), quick_seconds=0)
        proc = self._procs.get(job_id)
        if proc is not None:
            returncode = proc.wait()
            self._procs.pop(job_id, None)
        else:
            returncode = None  # A detached process has no recoverable exit code.

        run = self.store.get_run(row["run_dir"]) if row["run_dir"] else None
        arc_status = (run or {}).get("status")
        status = _RUN_FINAL_JOB_STATUS.get(arc_status or "")
        error = None
        if row["mode"] == "resume" and returncode not in (None, 0):
            # A rejected recovery leaves the old paused ARC checkpoint unchanged.
            # The command still failed, and its diagnostic must remain visible.
            status = "failed"
        if status is None:
            status = "completed" if returncode == 0 else "failed"
        if status == "failed":
            tail = self._log_tail(row["log_path"], 2500)
            error = f"exit code {returncode}\n{tail}" if returncode is not None else (tail or "process interrupted; exit code unavailable")
        elif run and run.get("stop_reason"):
            error = None  # stop_reason 属于正常停因，经由 run 详情展示
        conn = connect(self.cfg.db_path)
        try:
            conn.execute(
                "UPDATE jobs SET status=?, error=?, finished_at=? WHERE id=? AND status='running'",
                (status, error, _utcnow(), job_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        return dict(row)

    @staticmethod
    def effective_run_state(run: dict, job: dict | None) -> dict:
        """Display process interruption without writing a fictional ARC checkpoint."""
        original = run.get('status')
        state = {'status': original, 'arc_status': original}
        if job and job['status'] == 'cancelled' and original != 'COMPLETED':
            state.update(status='CANCELLED', interrupted=True,
                         stop_reason='user_cancelled_process', arc_stop_reason=run.get('stop_reason'))
        elif job and job['status'] == 'failed' and original == 'RUNNING':
            state.update(status='ERROR', interrupted=True,
                         stop_reason='process_interrupted', arc_stop_reason=run.get('stop_reason'))
        return state

    def run_lifecycle(self, run_id: str) -> dict | None:
        conn = connect(self.cfg.db_path)
        try:
            row = conn.execute(
                'SELECT * FROM jobs WHERE run_dir=? ORDER BY created_at DESC LIMIT 1', (run_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is not None and row['status'] == 'running' and not self._job_process_alive(row):
            return self._finalize_if_dead(row['id'])
        return dict(row) if row else None

    def status(self, job_id: str) -> dict:
        conn = connect(self.cfg.db_path)
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise JobError("no such job", status=404)
        job = dict(row)

        # A short-lived CLI can exit before the first status request. Bind its
        # final stdout before deciding the terminal job state.
        if not job.get("run_dir"):
            detected = self._detect_run_dir(
                job_id, job["mode"], json.loads(job["params"]), quick_seconds=0)
            if detected:
                job['run_dir'] = detected

        if job["status"] == "running":
            if self._job_process_alive(job):
                pass
            else:
                job = self._finalize_if_dead(job_id) or job
                if job["status"] == "running":
                    proc = self._procs.get(job_id)
                    if proc is not None and proc.poll() is not None:
                        job = self._finalize_if_dead(job_id) or job

        progress = self._progress(job["mode"], job.get("run_dir"), job.get("log_path"))
        if progress:
            progress.update(self.effective_run_state(progress, job))
        return {
            "job": {
                "id": job["id"], "mode": job["mode"], "params": json.loads(job["params"]),
                "username": job["username"], "status": job["status"],
                "run_dir": job.get("run_dir"), "error": job.get("error"),
                "created_at": job["created_at"], "finished_at": job.get("finished_at"),
            },
            "progress": progress,
            "log_tail": self._log_tail(job.get("log_path")),
        }

    def list_jobs(self, limit: int = 50) -> list[dict]:
        conn = connect(self.cfg.db_path)
        try:
            rows = conn.execute(
                "SELECT id, mode, username, status, pid, pid_start_ticks, log_path, run_dir, created_at, finished_at, params "
                "FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
        # 大厅轮询走的是列表接口：running 行若进程已死（含僵尸态）就地收口，
        # 否则会出现「大厅永远正在跑、收藏里早已暂停」的不一致
        stale = [r["id"] for r in rows
                 if r["status"] == "running" and not self._job_process_alive(r)]
        for job_id in stale:
            self._finalize_if_dead(job_id)
        if stale:
            conn = connect(self.cfg.db_path)
            try:
                rows = conn.execute(
                    "SELECT id, mode, username, status, pid, pid_start_ticks, log_path, run_dir, created_at, finished_at, params "
                    "FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            finally:
                conn.close()
        out = []
        for r in rows:
            out.append({
                "id": r["id"], "mode": r["mode"], "username": r["username"],
                "status": r["status"], "run_dir": r["run_dir"],
                "created_at": r["created_at"], "finished_at": r["finished_at"],
                "params": json.loads(r["params"]),
            })
        return out

    # ------------------------------------------------------------- cancel
    def cancel(self, job_id: str, user) -> dict:
        conn = connect(self.cfg.db_path)
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise JobError("no such job", status=404)
        if row["status"] != "running":
            raise JobError(f"任务已结束（{row['status']}）", status=409)
        if not user.is_admin and row["user_id"] != user.id:
            raise JobError("只能取消自己的任务", status=403)

        if not self._job_process_alive(row):
            finished = self._finalize_if_dead(job_id)
            raise JobError(f"任务已结束（{(finished or row)['status']}）", status=409)
        if not row['run_dir']:
            self._detect_run_dir(job_id, row['mode'], json.loads(row['params']))

        pid = row["pid"]
        killed = False
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            killed = True
        except ProcessLookupError:
            self._finalize_if_dead(job_id)
            raise JobError("任务已结束", status=409)
        except PermissionError as exc:
            raise JobError("无法向任务进程发送取消信号", status=409) from exc
        for _ in range(20):
            if not self._job_process_alive(row):
                break
            time.sleep(0.25)
        if self._job_process_alive(row):
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                raise JobError("任务进程仍在运行，无法终止", status=409) from exc
        proc = self._procs.pop(job_id, None)
        if proc is not None:
            proc.wait(timeout=5)
        conn = connect(self.cfg.db_path)
        try:
            conn.execute(
                "UPDATE jobs SET status='cancelled', finished_at=?, error='user cancelled' "
                "WHERE id=? AND status='running'",
                (_utcnow(), job_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {"id": job_id, "status": "cancelled", "signalled": killed}

    # ------------------------------------------------------------ recover
    def recover(self) -> None:
        """服务启动时调用：pid 还活的 running 任务重新挂载，否则按 ARC run 终态收尾。"""
        conn = connect(self.cfg.db_path)
        try:
            rows = conn.execute(
                "SELECT id, pid, pid_start_ticks, log_path, mode, run_dir, params FROM jobs WHERE status='running'"
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            if self._job_process_alive(r):
                continue  # 子进程因 start_new_session 存活，状态轮询会重新收割
            run_dir = r['run_dir'] or self._detect_run_dir(r['id'], r['mode'], json.loads(r['params']))
            run = self.store.get_run(run_dir) if run_dir else None
            arc_status = (run or {}).get("status")
            status = _RUN_FINAL_JOB_STATUS.get(arc_status or "", "failed")
            if arc_status == "RUNNING":
                status = "failed"  # ARC run 未落终态即中断
            conn = connect(self.cfg.db_path)
            try:
                conn.execute(
                    "UPDATE jobs SET status=?, error=?, finished_at=? "
                    "WHERE id=? AND status='running'",
                    (status,
                     None if status in ("completed", "paused") else "interrupted (server restart)",
                     _utcnow(), r["id"]),
                )
                conn.commit()
            finally:
                conn.close()


def run_id_prefix(run_dir: str) -> str:
    return run_dir
