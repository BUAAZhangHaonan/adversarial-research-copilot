"""Process/SQLite contract tests; only isolated fake CLI children are started."""
import json
import sqlite3
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from arc_arena.artifacts import Artifacts, ArtifactError
from arc_arena.jobs import JobError, JobManager
from test_jobs import make_manager, USER


def test_report_only_cost_does_not_claim_complete_accounting(tmp_path):
    manager, cfg = make_manager(tmp_path)
    run = tmp_path / 'report-only'
    run.mkdir()
    (run / 'COST_REPORT.md').write_text('已结算上界（元）：3.2\n授权上限（元）：20\n', encoding='utf-8')
    cost = Artifacts(manager.store, cfg.arc_reports)._cost(run, {})
    assert cost['spent_upper_cny'] == 3.2
    assert cost['total_cost_complete'] is False
    assert cost['cost_scope'] == 'report_snapshot'


def stop_all(manager):
    for job_id, process in list(manager._procs.items()):
        if process.poll() is None:
            manager.cancel(job_id, USER)


def test_identical_topics_bind_each_child_stdout(tmp_path):
    manager, _ = make_manager(tmp_path)
    try:
        ids = [manager.submit('discover', {'topic': 'same topic'}, USER)['job_id'] for _ in range(2)]
        runs = [manager.status(i)['job']['run_dir'] for i in ids]
        assert all(runs) and runs[0] != runs[1]
        for job_id, run_id in zip(ids, runs):
            assert {e['run_id'] for e in manager._log_events(str(manager.cfg.jobs_log_dir / f'{job_id}.log'))} == {run_id}
    finally:
        stop_all(manager)


def test_concurrent_admission_respects_limit_across_managers(tmp_path):
    first, cfg = make_manager(tmp_path, max_jobs=1)
    second = JobManager(cfg)
    barrier = threading.Barrier(2)
    real_popen = subprocess.Popen
    for manager in (first, second):
        validate = manager.validate_params
        def synchronized(mode, params, validate=validate):
            result = validate(mode, params)
            barrier.wait(timeout=5)
            return result
        manager.validate_params = synchronized
        manager._detect_run_dir = lambda *a, **kw: None
    def spawn(*args, **kwargs):
        return real_popen(['/bin/sleep', '20'], **kwargs)
    def submit(manager):
        try:
            return manager.submit('discover', {'topic': 'concurrent request'}, USER)
        except JobError as exc:
            return exc.status
    try:
        with patch('arc_arena.jobs.subprocess.Popen', side_effect=spawn):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(submit, [first, second]))
        assert sum(isinstance(r, dict) for r in results) == 1
        assert results.count(429) == 1
        assert len([r for r in first.list_jobs() if r['status'] == 'running']) == 1
    finally:
        stop_all(first)
        stop_all(second)


def test_cancel_visible_consistently_without_mutating_arc(tmp_path):
    manager, cfg = make_manager(tmp_path)
    job_id = manager.submit('discover', {'topic': 'cancel audit'}, USER)['job_id']
    run_id = manager.status(job_id)['job']['run_dir']
    before = manager.store.get_run(run_id)
    manager.cancel(job_id, USER)
    status = manager.status(job_id)
    assert status['job']['status'] == 'cancelled'
    assert status['progress']['status'] == 'CANCELLED'
    assert status['progress']['arc_status'] == 'RUNNING'
    assert manager.store.get_run(run_id) == before
    artifacts = Artifacts(manager.store, cfg.arc_reports, manager)
    assert artifacts.run_detail(run_id)['run']['status'] == 'CANCELLED'
    assert artifacts.run_detail(run_id)['pause_recovery'] is None
    assert artifacts.list_runs()[0]['status'] == 'CANCELLED'
    with pytest.raises(JobError):
        manager.validate_params('resume', {'run_id': run_id})


def test_final_cost_event_supersedes_progress_budget(tmp_path):
    manager, _ = make_manager(tmp_path)
    log = tmp_path / 'events.log'
    log.write_text('\n'.join(json.dumps(e) for e in [
        {'run_id': 'r', 'task_id': 'r.task', 'status': 'ACCEPTED', 'budget': {'spent_upper_cny': 3.2}},
        {'run_id': 'r', 'status': 'COMPLETED', 'cost': {'spent_upper_cny': 5.0}},
    ]))
    assert manager._progress('discover', None, str(log))['budget']['spent_upper_cny'] == 5


def test_sqlite_budget_and_cost_limits_override_report_and_log(tmp_path):
    manager, cfg = make_manager(tmp_path)
    with sqlite3.connect(cfg.arc_db) as db:
        db.executescript('''
            CREATE TABLE runs(id TEXT PRIMARY KEY,data TEXT);
            CREATE TABLE budget_accounts(account_id TEXT PRIMARY KEY,parent_id TEXT,limit_micro INTEGER);
            CREATE TABLE budget_calls(call_id TEXT,account_id TEXT,state TEXT,lower_micro INTEGER,
                upper_micro INTEGER,reserved_micro INTEGER,cost_status TEXT);
            INSERT INTO budget_accounts VALUES('r',NULL,20000000);
            INSERT INTO budget_accounts VALUES('child','r',10000000);
            INSERT INTO budget_calls VALUES('a','r','SETTLED',5000000,5000000,0,'measured');
            INSERT INTO budget_calls VALUES('b','child','UNKNOWN',1000000,NULL,2000000,'unknown');
            INSERT INTO budget_calls VALUES('c','r','SETTLED',0,0,0,'unmetered');
        ''')
        db.execute('INSERT INTO runs VALUES(?,?)', ('r', json.dumps({
            'run_id': 'r', 'mode': 'develop', 'status': 'RUNNING', 'budget_account_id': 'r'})))
    log = tmp_path / 'events.log'
    log.write_text(json.dumps({'run_id': 'r', 'budget': {'spent_upper_cny': 1}}))
    cost = manager._progress('develop', 'r', str(log))['budget']
    assert cost['spent_upper_cny'] == 5
    assert cost['remaining_cny'] == 13
    assert cost['reserved_cny'] == 2
    assert cost['unsettled_lower_cny'] == 1
    assert cost['unknown_calls'] == cost['unmetered_calls'] == 1
    assert cost['total_cost_complete'] is False
    assert cost['cost_scope'] == 'metered_costs_only'
    # No report directory exists yet: both listing and details remain usable.
    artifacts = Artifacts(manager.store, cfg.arc_reports)
    assert artifacts.list_runs()[0]['cost']['spent_upper_cny'] == 5
    assert artifacts.run_detail('r')['cost']['remaining_cny'] == 13


def test_card_version_is_exposed_in_file_list(tmp_path):
    manager, cfg = make_manager(tmp_path)
    run = cfg.arc_reports / 'r'
    (run / 'cards/card_1').mkdir(parents=True)
    (run / 'cards/card_1/v1.md').write_text('card')
    artifacts = Artifacts(manager.store, cfg.arc_reports)
    assert artifacts._file_entries(run) == [{'name': 'cards/card_1/v1.md', 'size': 4}]
    with pytest.raises(ArtifactError):
        artifacts.read_file('..', 'anything.md')


def test_second_resume_is_rejected_while_same_run_has_live_child(tmp_path):
    manager, cfg = make_manager(tmp_path)
    run_id = 'paused_run'
    with sqlite3.connect(cfg.arc_db) as db:
        db.execute('CREATE TABLE runs(id TEXT PRIMARY KEY,data TEXT)')
        db.execute('INSERT INTO runs VALUES(?,?)', (run_id, json.dumps({
            'run_id': run_id, 'mode': 'discover', 'status': 'PAUSED_BUDGET'})))
    real_popen = subprocess.Popen
    def spawn(*args, **kwargs):
        return real_popen(['/bin/sleep', '20'], **kwargs)
    try:
        with patch('arc_arena.jobs.subprocess.Popen', side_effect=spawn):
            manager.submit('resume', {'run_id': run_id}, USER)
            with pytest.raises(JobError) as error:
                manager.submit('resume', {'run_id': run_id}, USER)
        assert error.value.status == 409
    finally:
        stop_all(manager)


def test_completed_child_is_bound_before_harvesting(tmp_path):
    manager, cfg = make_manager(tmp_path)
    # Let the fake CLI finish before its first binding attempt.
    cfg.arc_bin.write_text(cfg.arc_bin.read_text().replace('time.sleep(20)', 'time.sleep(0.05)'))
    with patch.object(manager, '_detect_run_dir', return_value=None):
        job_id = manager.submit('discover', {'topic': 'very short run'}, USER)['job_id']
    process = manager._procs[job_id]
    process.wait(timeout=5)
    result = manager.status(job_id)
    assert result['job']['run_dir']
    assert result['job']['status'] == 'completed'
    assert result['progress']['status'] == 'COMPLETED'
    assert result['progress']['budget']['spent_upper_cny'] == 5


@pytest.mark.parametrize('params', [{'topic': 'x', 'draws': 'not-an-int'},
    {'topic': 'x', 'budget_cny': []}])
def test_bad_numeric_parameters_are_client_errors(tmp_path, params):
    manager, _ = make_manager(tmp_path)
    with pytest.raises(JobError) as error:
        manager.validate_params('discover', params)
    assert error.value.status == 400


def test_scope_change_resume_api_returns_400_without_spawning(tmp_path):
    from fastapi.testclient import TestClient
    from arc_arena.app import create_app
    from arc_arena.auth import AuthManager
    manager, cfg = make_manager(tmp_path)
    with sqlite3.connect(cfg.arc_db) as db:
        db.execute('CREATE TABLE runs(id TEXT PRIMARY KEY,data TEXT)')
        db.execute('INSERT INTO runs VALUES(?,?)', ('scope_run', json.dumps({
            'run_id': 'scope_run', 'mode': 'develop', 'status': 'PAUSED_SCOPE_CHANGE'})))
    auth = AuthManager(cfg.db_path)
    auth.create_user('scope_tester', 'test-password')
    with TestClient(create_app(cfg)) as client:
        assert client.post('/api/auth/login', json={
            'username': 'scope_tester', 'password': 'test-password'}).status_code == 200
        with patch('arc_arena.jobs.subprocess.Popen') as spawn:
            response = client.post('/api/jobs', json={'mode': 'resume', 'params': {'run_id': 'scope_run'}})
            spawn.assert_not_called()
    assert response.status_code == 400
    assert '不能直接续跑' in response.json()['detail']
    assert manager.list_jobs() == []


def test_reused_pid_is_neither_recovered_nor_signalled(tmp_path):
    manager, cfg = make_manager(tmp_path)
    unrelated = subprocess.Popen(['/bin/sleep', '20'], start_new_session=True)
    try:
        with sqlite3.connect(cfg.db_path) as db:
            db.execute('''INSERT INTO jobs(id,mode,params,user_id,username,status,pid,
                pid_start_ticks,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',
                ('reused_pid', 'discover', '{}', USER.id, USER.username, 'running', unrelated.pid, '-1', '2026-09-12'))
        with patch('arc_arena.jobs.os.killpg') as signal_group:
            with pytest.raises(JobError) as error:
                manager.cancel('reused_pid', USER)
            assert error.value.status == 409
            assert manager.status('reused_pid')['job']['status'] == 'failed'
            with sqlite3.connect(cfg.db_path) as db:
                db.execute("UPDATE jobs SET status='running' WHERE id='reused_pid'")
            manager.recover()
            signal_group.assert_not_called()
        assert manager.status('reused_pid')['job']['status'] == 'failed'
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_legacy_pid_requires_exact_job_stdout(tmp_path):
    manager, cfg = make_manager(tmp_path)
    try:
        job_id = manager.submit('discover', {'topic': 'legacy identity'}, USER)['job_id']
        with sqlite3.connect(cfg.db_path) as db:
            db.execute('UPDATE jobs SET pid_start_ticks=NULL WHERE id=?', (job_id,))
            db.row_factory = sqlite3.Row
            row = dict(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
        recovered = JobManager(cfg)
        assert recovered._job_process_alive(row)
        wrong_job = {**row, 'log_path': str(cfg.jobs_log_dir / 'another_job.log')}
        assert not recovered._job_process_alive(wrong_job)
        recovered.recover()
        assert recovered.status(job_id)['job']['status'] == 'running'
    finally:
        stop_all(manager)


def test_existing_job_schema_gets_nullable_process_identity(tmp_path):
    from arc_arena.db import _SCHEMA, init_db
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as db:
        db.executescript(_SCHEMA.replace('  pid_start_ticks TEXT,\n', ''))
        db.execute('''INSERT INTO jobs(id,mode,params,user_id,username,status,pid,created_at)
            VALUES('old','discover','{}',1,'tester','paused',NULL,'2026-09-12')''')
    init_db(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id,status,pid_start_ticks FROM jobs').fetchall() == [('old', 'paused', None)]
