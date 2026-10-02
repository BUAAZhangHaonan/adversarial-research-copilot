"""用假 ARC v2 CLI 测试任务编排：spawn / SQLite run 关联 / 进度事件 / 取消 / 续跑。

fake arc 模拟 adversarial-research-copilot 的行为合同：
- 接受 --data-dir/--env-file 全局参数
- discover: 在 arc.sqlite 写 runs/campaigns 并向 stdout 打 JSON 进度事件
- 结束时 run 状态落 COMPLETED 并打印结果 JSON 行
"""
import json
import os
import signal
import stat
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arc_arena.auth import User
from arc_arena.config import Config
from arc_arena.jobs import JobError, JobManager

FAKE_ARC = r'''#!/usr/bin/env python3
import json, sqlite3, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

args = sys.argv[1:]
data_dir = Path(args[args.index("--data-dir") + 1])
cmd = args[args.index("--data-dir") - 1] if "--data-dir" in args and args.index("--data-dir") > 0 else None
# 全局参数在子命令之前：arc --data-dir D --env-file E <cmd> ...
i = 0
cmd = None
while i < len(args):
    if args[i] in ("--data-dir", "--env-file"):
        i += 2
        continue
    cmd = args[i]
    rest = args[i + 1:]
    break

def now():
    return datetime.now(timezone.utc).isoformat()

db = data_dir / "arc.sqlite"
conn = sqlite3.connect(str(db))
conn.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
conn.execute("CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
conn.execute("CREATE TABLE IF NOT EXISTS discovery_ideas(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, draw_id TEXT NOT NULL, data TEXT NOT NULL)")

def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)

def budget(spent):
    return {"limit_cny": 20, "spent_lower_cny": spent, "spent_upper_cny": spent,
            "reserved_cny": 0, "remaining_cny": 20 - spent, "call_count": int(spent * 10),
            "unknown_calls": 0, "currency": "CNY"}

def save_run(run_id, run):
    conn.execute("INSERT OR REPLACE INTO runs VALUES(?,?)", (run_id, json.dumps(run, ensure_ascii=False)))
    conn.commit()

if cmd == "discover":
    topic = rest[0]
    run_id = "run_" + uuid.uuid4().hex[:12]
    campaign_id = "campaign_" + uuid.uuid4().hex[:12]
    conn.execute("INSERT INTO campaigns VALUES(?,?)", (campaign_id, json.dumps(
        {"campaign_id": campaign_id, "topic": topic, "max_draws": 2, "draws_started": 0}, ensure_ascii=False)))
    save_run(run_id, {"run_id": run_id, "mode": "discover", "campaign_id": campaign_id,
                      "status": "RUNNING", "stop_reason": None, "assessment": None,
                      "state": {}, "created_at": now(), "updated_at": now()})
    emit({"task_id": run_id + ".survey", "run_id": run_id, "status": "ACCEPTED",
          "budget": budget(1.5), "run_status": "RUNNING", "draws_started": 1, "max_draws": 2})
    (data_dir / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (data_dir / "reports" / run_id / "REPORT.md").write_text("# fake report\n", encoding="utf-8")
    emit({"task_id": run_id + ".idea1.sketch", "run_id": run_id, "status": "ACCEPTED",
          "budget": budget(3.2), "run_status": "RUNNING", "draws_started": 2, "max_draws": 2})
    time.sleep(20)
    save_run(run_id, {"run_id": run_id, "mode": "discover", "campaign_id": campaign_id,
                      "status": "COMPLETED", "stop_reason": "discover_draws_finished_human_selection",
                      "assessment": None, "state": {}, "created_at": run_id and save_run.created,
                      "updated_at": now()} if False else {"run_id": run_id, "mode": "discover",
                      "campaign_id": campaign_id, "status": "COMPLETED",
                      "stop_reason": "discover_draws_finished_human_selection",
                      "assessment": None, "state": {}, "created_at": now(), "updated_at": now()})
    emit({"run_id": run_id, "status": "COMPLETED", "assessment": None,
          "stop_reason": "discover_draws_finished_human_selection", "cost": budget(5.0)})
elif cmd in ("develop", "run"):
    question = proposal_text = idea_id = card_id = None
    j = 0
    while j < len(rest):
        if rest[j] == "--question":
            question = rest[j + 1]; j += 2
        elif rest[j] == "--proposal":
            proposal_text = Path(rest[j + 1]).read_text(encoding="utf-8"); j += 2
        elif rest[j] == "--idea":
            idea_id = rest[j + 1]; j += 2
        elif rest[j] == "--card":
            card_id = rest[j + 1]; j += 2
        else:
            j += 1
    run_id = "run_" + uuid.uuid4().hex[:12]
    state = {}
    if question:
        state["imported_input"] = question
    if proposal_text is not None:
        state["imported_input"] = proposal_text
    if idea_id:
        state["idea_input"] = {"idea_id": idea_id}
    run = {"run_id": run_id, "mode": cmd, "campaign_id": None, "status": "RUNNING",
           "stop_reason": None, "assessment": None, "card_id": card_id, "card_version": 1,
           "state": state, "created_at": now(), "updated_at": now()}
    save_run(run_id, run)
    emit({"task_id": run_id + ".development", "run_id": run_id, "status": "ACCEPTED",
          "budget": budget(2.0), "run_status": "RUNNING", "rounds_completed": 1})
    (data_dir / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (data_dir / "reports" / run_id / "REPORT.md").write_text("# fake stage report\n", encoding="utf-8")
    time.sleep(20)
    run.update({"status": "COMPLETED", "stop_reason": "experiment_required",
                "assessment": "PROMISING", "state": {"rounds_completed": 2}})
    save_run(run_id, run)
    emit({"run_id": run_id, "status": "COMPLETED", "assessment": "PROMISING",
          "stop_reason": "experiment_required", "cost": budget(8.0)})
elif cmd == "resume":
    run_id = rest[0]
    row = conn.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
    run = json.loads(row[0])
    run.update({"status": "COMPLETED", "stop_reason": "experiment_required", "assessment": "PROMISING"})
    save_run(run_id, run)
    emit({"run_id": run_id, "status": "COMPLETED", "assessment": "PROMISING",
          "stop_reason": "experiment_required", "cost": budget(9.0)})
elif cmd == "retry-task":
    run_id = rest[0]
    j = 0
    task_key = reason = None
    while j < len(rest):
        if rest[j] == "--task-key":
            task_key = rest[j + 1]; j += 2
        elif rest[j] == "--reason":
            reason = rest[j + 1]; j += 2
        else:
            j += 1
    row = conn.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
    run = json.loads(row[0])
    run.update({"status": "COMPLETED", "stop_reason": "retry:" + str(task_key),
                "assessment": "PROMISING", "state": {"retry_reason": reason}})
    save_run(run_id, run)
    emit({"task_id": run_id + "." + str(task_key), "run_id": run_id, "status": "ACCEPTED",
          "budget": budget(3.0), "run_status": "RUNNING"})
    emit({"run_id": run_id, "status": "COMPLETED", "assessment": "PROMISING",
          "stop_reason": "retry:" + str(task_key), "cost": budget(3.0)})
conn.close()
'''

USER = User(id=1, username="tester", is_admin=False)


def make_manager(tmp_path: Path, max_jobs: int = 2) -> tuple[JobManager, Config]:
    backend = tmp_path / "backend"
    bin_dir = backend / ".venv" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    arc = bin_dir / "arc"
    arc.write_text(FAKE_ARC)
    arc.chmod(arc.stat().st_mode | stat.S_IEXEC)
    (backend / ".env").write_text("DEEPSEEK_API_KEY=x\n", encoding="utf-8")
    cfg = Config(backend_root=backend, data_dir=tmp_path / "data")
    cfg.max_concurrent_jobs = max_jobs
    for d in (cfg.data_dir, cfg.uploads_dir, cfg.jobs_log_dir, cfg.arc_data_dir):
        d.mkdir(parents=True, exist_ok=True)
    from arc_arena.db import init_db
    init_db(cfg.db_path)
    return JobManager(cfg), cfg


def _wait(cond, timeout=15.0, interval=0.3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        v = cond()
        if v:
            return v
        time.sleep(interval)
    raise AssertionError("condition timeout")


def _wait_run_dir(mgr, job_id):
    return _wait(lambda: (lambda st: st if st["job"]["run_dir"] else None)(mgr.status(job_id)))


def _kill(mgr, cfg, job_id):
    from arc_arena.db import connect
    conn = connect(cfg.db_path)
    try:
        pid = conn.execute("SELECT pid FROM jobs WHERE id=?", (job_id,)).fetchone()["pid"]
    finally:
        conn.close()
    os.killpg(os.getpgid(pid), signal.SIGKILL)


# ------------------------------------------------------------- lifecycle
def test_discover_job_lifecycle(tmp_path: Path):
    mgr, cfg = make_manager(tmp_path)
    topic = "memory architectures for LLM agents"
    out = mgr.submit("discover", {"topic": topic, "draws": 2, "budget_cny": 20}, USER)
    job_id = out["job_id"]

    st = _wait_run_dir(mgr, job_id)
    assert st["job"]["status"] == "running"
    run_id = st["job"]["run_dir"]
    assert run_id.startswith("run_")

    # run 记录确实属于该主题（SQLite 强匹配）
    run = mgr.store.get_run(run_id)
    campaign = mgr.store.get_campaign(run["campaign_id"])
    assert campaign["topic"] == topic

    prog = st["progress"]
    assert prog["status"] == "RUNNING"
    assert prog["draws"] == {"started": 2, "max": 2}
    assert prog["budget"]["spent_upper_cny"] == pytest.approx(3.2)
    assert any(t["task_id"] == "idea1.sketch" for t in prog["tasks"])

    assert (cfg.arc_reports / run_id / "REPORT.md").exists()
    assert mgr.cancel(job_id, USER)["status"] == "cancelled"


def test_develop_question_progress(tmp_path: Path):
    mgr, _ = make_manager(tmp_path)
    question = "Why do agents plateau on long-horizon tasks?"
    out = mgr.submit("develop", {"question": question, "budget_cny": 20}, USER)
    job_id = out["job_id"]
    st = _wait_run_dir(mgr, job_id)
    run = mgr.store.get_run(st["job"]["run_dir"])
    assert run["state"]["imported_input"] == question
    prog = st["progress"]
    assert prog["rounds_completed"] == 1
    assert prog["budget"]["limit_cny"] == pytest.approx(20)
    mgr.cancel(job_id, USER)


def test_debate_proposal_written_to_uploads(tmp_path: Path):
    mgr, cfg = make_manager(tmp_path)
    proposal = "# Test Idea\nSome research idea for debate."
    out = mgr.submit("debate", {"proposal": proposal}, USER)
    job_id = out["job_id"]
    st = _wait_run_dir(mgr, job_id)
    run = mgr.store.get_run(st["job"]["run_dir"])
    assert run["mode"] == "run"
    assert run["state"]["imported_input"] == proposal
    uploads = list(cfg.uploads_dir.glob(f"{job_id}_proposal.md"))
    assert uploads and uploads[0].read_text(encoding="utf-8") == proposal
    mgr.cancel(job_id, USER)


def test_develop_from_idea_matches_run(tmp_path: Path):
    mgr, _ = make_manager(tmp_path)
    out = mgr.submit("develop", {"idea_id": "idea_abc123"}, USER)
    job_id = out["job_id"]
    st = _wait_run_dir(mgr, job_id)
    run = mgr.store.get_run(st["job"]["run_dir"])
    assert run["state"]["idea_input"]["idea_id"] == "idea_abc123"
    mgr.cancel(job_id, USER)


def test_resume_paused_run(tmp_path: Path):
    mgr, _ = make_manager(tmp_path)
    # 手工造一个 PAUSED_BUDGET 的 run
    run_id = "run_paused01"
    mgr.store.db_path  # 确保 db 存在路径
    import sqlite3 as sq
    conn = sq.connect(str(mgr.cfg.arc_db))
    conn.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.execute("INSERT INTO runs VALUES(?,?)", (run_id, json.dumps(
        {"run_id": run_id, "mode": "develop", "status": "PAUSED_BUDGET",
         "stop_reason": "budget_exhausted", "state": {}, "created_at": "2026-09-01T00:00:00+00:00"})))
    conn.commit()
    conn.close()

    out = mgr.submit("resume", {"run_id": run_id, "add_budget_cny": 5}, USER)
    job_id = out["job_id"]
    st = _wait(lambda: mgr.status(job_id))
    assert st["job"]["run_dir"] == run_id
    def done():
        s = mgr.status(job_id)
        return s if s["job"]["status"] != "running" else None
    st = _wait(done, timeout=15)
    assert st["job"]["status"] == "completed"
    prog = st["progress"]
    assert prog["status"] == "COMPLETED"
    assert prog["assessment"] == "PROMISING"


def test_resume_protocol_paused_uses_retry_task(tmp_path: Path):
    """PAUSED_PROTOCOL 的续跑应走 retry-task（普通 resume 只会重放旧输出再次暂停）。"""
    mgr, _ = make_manager(tmp_path)
    run_id = "run_proto01"
    import sqlite3 as sq
    conn = sq.connect(str(mgr.cfg.arc_db))
    conn.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data TEXT NOT NULL)")
    conn.execute("INSERT INTO runs VALUES(?,?)", (run_id, json.dumps(
        {"run_id": run_id, "mode": "discover", "status": "PAUSED_PROTOCOL",
         "stop_reason": "INVALID_OUTPUT_AFTER_REPAIR", "state": {}, "created_at": "2026-09-01T00:00:00+00:00"})))
    conn.execute("INSERT INTO tasks VALUES(?,?,?)",
                 (run_id + ".idea1.check", run_id, json.dumps({"status": "PAUSED_PROTOCOL"})))
    conn.execute("INSERT INTO tasks VALUES(?,?,?)",
                 (run_id + ".survey", run_id, json.dumps({"status": "ACCEPTED"})))
    conn.commit()
    conn.close()

    assert mgr.store.paused_task_key(run_id) == "idea1.check"

    out = mgr.submit("resume", {"run_id": run_id}, USER)
    job_id = out["job_id"]

    def done():
        s = mgr.status(job_id)
        return s if s["job"]["status"] != "running" else None
    st = _wait(done, timeout=15)
    assert st["job"]["status"] == "completed"
    # fake arc 把收到的 --task-key 回写进 stop_reason，据此断言 argv 走的是 retry-task
    run = mgr.store.get_run(run_id)
    assert run["stop_reason"] == "retry:idea1.check"
# ------------------------------------------------------------- guards
def test_concurrency_limit(tmp_path: Path):
    mgr, _ = make_manager(tmp_path, max_jobs=1)
    mgr.submit("discover", {"topic": "first topic"}, USER)
    with pytest.raises(JobError) as exc:
        mgr.submit("discover", {"topic": "second topic"}, USER)
    assert exc.value.status == 429
    for j in mgr.list_jobs():
        if j["status"] == "running":
            mgr.cancel(j["id"], USER)


def test_param_validation(tmp_path: Path):
    mgr, _ = make_manager(tmp_path)
    with pytest.raises(JobError):
        mgr.submit("discover", {"topic": ""}, USER)
    with pytest.raises(JobError):
        mgr.submit("discover", {"topic": "x", "draws": 99}, USER)
    with pytest.raises(JobError):
        mgr.submit("develop", {}, USER)  # 缺输入
    with pytest.raises(JobError):
        mgr.submit("develop", {"question": "q", "proposal": "p"}, USER)  # 互斥
    with pytest.raises(JobError):
        mgr.submit("resume", {"run_id": "run_nope"}, USER)  # run 不存在
    with pytest.raises(JobError):
        mgr.submit("bogus", {}, USER)


def test_zombie_process_is_harvested(tmp_path: Path):
    """子进程退出成僵尸（父进程未 wait）时不能永远卡在 running。"""
    mgr, cfg = make_manager(tmp_path)
    arc = cfg.arc_bin
    arc.write_text("#!/usr/bin/env bash\nsleep 0.2\n")
    job_id = mgr.submit("discover", {"topic": "zombie test"}, USER)["job_id"]

    def harvested():
        st = mgr.status(job_id)
        return st if st["job"]["status"] != "running" else None

    st = _wait(harvested, timeout=10)
    # 进程正常退出（exit 0）且无 ARC run 终态：按成功收割
    assert st["job"]["status"] == "completed"


def test_orphan_completed_by_run_state(tmp_path: Path):
    """服务重启后的孤儿任务：进程已死但 ARC run 落了 COMPLETED -> 判定成功。"""
    mgr, cfg = make_manager(tmp_path)
    job_id = mgr.submit("discover", {"topic": "orphan done"}, USER)["job_id"]
    _wait_run_dir(mgr, job_id)
    run_id = mgr.status(job_id)["job"]["run_dir"]
    import sqlite3 as sq
    conn = sq.connect(str(cfg.arc_db))
    row = conn.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
    run = json.loads(row[0])
    run.update({"status": "COMPLETED", "stop_reason": "discover_draws_finished_human_selection"})
    conn.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(run), run_id))
    conn.commit()
    conn.close()
    _kill(mgr, cfg, job_id)
    time.sleep(0.3)
    mgr._procs.clear()
    mgr.recover()
    st = mgr.status(job_id)
    assert st["job"]["status"] == "completed"


def test_recover_marks_orphans_failed(tmp_path: Path):
    mgr, cfg = make_manager(tmp_path)
    job_id = mgr.submit("discover", {"topic": "orphan"}, USER)["job_id"]
    _kill(mgr, cfg, job_id)
    time.sleep(0.3)
    mgr._procs.clear()
    mgr.recover()
    st = mgr.status(job_id)
    assert st["job"]["status"] == "failed"
    assert "interrupted" in (st["job"]["error"] or "")
