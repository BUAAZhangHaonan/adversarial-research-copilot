"""Version selection uses only synthetic artifacts and temporary metadata."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket

import pytest

from arc_arena.artifacts import ArtifactError
from arc_arena.run_versions import RunVersions, VersionError
from arc_arena.versioned_artifacts import VersionedArtifacts


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('version tests must not open network connections')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


class FakeArtifacts:
    def __init__(self, root):
        self.root = root
        self.records = {}
        self.detail_hook = None
        self.file_hook = None

    def add(self, run_id, status='COMPLETED', mode='discover', count=2, topic='identical topic'):
        directory = self.root / run_id
        (directory / 'ideas').mkdir(parents=True)
        (directory / 'REPORT.md').write_text('# Synthetic report\n', encoding='utf-8')
        cards = []
        for number in range(count if mode == 'discover' else 0):
            idea_id = f'{run_id}_idea_{number}'
            name = f'ideas/{idea_id}.md'
            (directory / name).write_text(f'# Synthetic card {number}\n', encoding='utf-8')
            cards.append({'idea_id': idea_id, 'idea_md': name,
                'seed': {'question': 'synthetic question'}, 'note': {'decision': 'discuss'}})
        self.records[run_id] = {'dir': run_id, 'mode': mode, 'topic': topic,
            'run': {'run_id': run_id, 'status': status}, 'cards': cards,
            'files': [{'name': p.relative_to(directory).as_posix()}
                for p in directory.rglob('*') if p.is_file()]}

    def list_runs(self):
        return [{'dir': key, 'mode': item['mode'], 'topic': item['topic'],
            'status': item['run']['status']} for key, item in self.records.items()]

    def run_detail(self, run_id):
        if run_id not in self.records:
            raise ArtifactError('missing synthetic run')
        detail = deepcopy(self.records[run_id])
        if self.detail_hook:
            self.detail_hook()
        return detail

    def read_file(self, run_id, name):
        try:
            content = (self.root / run_id / name).read_text(encoding='utf-8')
        except FileNotFoundError as exc:
            raise ArtifactError('missing synthetic file') from exc
        if self.file_hook:
            self.file_hook()
        return {'name': name, 'content': content}


@pytest.fixture
def setup(tmp_path):
    artifacts = FakeArtifacts(tmp_path / 'reports')
    artifacts.add('old_a', count=2)
    artifacts.add('new_a', count=3)
    artifacts.add('other_b', count=4)  # Same topic text; explicitly another problem.
    artifacts.add('old_develop', mode='develop')
    artifacts.add('old_debate', mode='debate')
    artifacts.add('new_develop', mode='develop')
    registry = RunVersions(tmp_path / 'display' / 'run_versions.json')
    wrapper = VersionedArtifacts(artifacts, registry)
    return wrapper, registry, artifacts


def register(setup):
    wrapper, _, _ = setup
    wrapper.register_current('problem_a', 'old_a', 'tester')
    wrapper.register_stage('old_develop', 'old_a', 'tester')
    wrapper.register_stage('old_debate', 'old_develop', 'tester')
    wrapper.register_version('problem_a', 'new_a', 'old_a', 'tester')
    wrapper.register_stage('new_develop', 'new_a', 'tester')
    wrapper.register_current('problem_b', 'other_b', 'tester')


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file()}


def test_missing_registry_read_is_side_effect_free(tmp_path):
    directory = tmp_path / 'not_created'
    registry = RunVersions(directory / 'run_versions.json')
    assert registry.snapshot()['revision'] == 0
    assert not directory.exists()


def test_unregistered_legacy_runs_stay_visible_without_topic_inference(setup):
    wrapper, registry, artifacts = setup
    assert {r['dir'] for r in wrapper.list_runs()} == set(artifacts.records)
    assert all(wrapper.visibility(key)['visible'] for key in artifacts.records)
    assert not registry.path.exists()


def test_registration_leaves_previous_selection_until_explicit_review(setup):
    register(setup)
    wrapper, registry, _ = setup
    assert registry.snapshot()['problems']['problem_a']['selected_version'] == 'old_a'
    assert {r['dir'] for r in wrapper.list_runs()} == {'old_a', 'old_develop', 'old_debate', 'other_b'}
    assert wrapper.visibility('new_a')['current_run_id'] == 'old_a'


def test_selection_matches_list_details_files_jobs_and_card_counts_without_rewriting(setup):
    wrapper, registry, artifacts = setup
    before_records, before_files = deepcopy(artifacts.records), hashes(artifacts.root)
    register(setup)
    wrapper.select_version('problem_a', 'new_a', 'old_a', True, 'tester')
    visible = wrapper.list_runs()
    assert {r['dir'] for r in visible} == {'new_a', 'new_develop', 'other_b'}
    assert sum(len(wrapper.run_detail(r['dir'])['cards']) for r in visible) == 7
    assert {r['version_revision'] for r in visible} == {registry.snapshot()['revision']}
    assert wrapper.run_detail('new_develop')['version_run_id'] == 'new_a'
    for old in ('old_a', 'old_develop', 'old_debate'):
        with pytest.raises(VersionError) as error:
            wrapper.run_detail(old)
        assert error.value.status == 410
        assert error.value.current_run_id == 'new_a'
        with pytest.raises(VersionError):
            wrapper.read_file(old, 'REPORT.md')
    assert wrapper.read_file('new_a', 'REPORT.md')['content']
    assert artifacts.records == before_records
    assert hashes(artifacts.root) == before_files
    jobs = [{'id': 'old', 'run_dir': 'old_a'}, {'id': 'new', 'run_dir': 'new_a'},
        {'id': 'resume', 'params': {'run_id': 'old_a'}}, {'id': 'other', 'run_dir': 'other_b'},
        {'id': 'unbound', 'params': {}}]
    assert [j['id'] for j in wrapper.visible_jobs(jobs)] == ['new', 'other', 'unbound']
    with pytest.raises(VersionError):
        wrapper.require_visible_job(jobs[2])
    assert wrapper.job_visibility(jobs[0])['current_run_id'] == 'new_a'
    assert wrapper.job_visibility(jobs[0])['visible'] is False
    assert wrapper.job_visibility(jobs[-1])['visible'] is True


@pytest.mark.parametrize('status', ['RUNNING', 'ERROR', 'CANCELLED', 'PAUSED_BUDGET', 'PAUSED_PROTOCOL'])
def test_incomplete_or_failed_run_keeps_successful_selection(setup, status):
    register(setup)
    wrapper, registry, artifacts = setup
    artifacts.records['new_a']['run']['status'] = status
    before = registry.path.read_bytes()
    with pytest.raises(VersionError):
        wrapper.select_version('problem_a', 'new_a', 'old_a', True, 'tester')
    assert registry.path.read_bytes() == before
    assert wrapper.visibility('old_a')['visible']
    assert not wrapper.visibility('new_a')['visible']


@pytest.mark.parametrize('failure', ['missing_report', 'empty_report', 'missing_card', 'empty_card', 'unpublished_card', 'no_cards'])
def test_missing_publication_artifacts_leave_previous_version(setup, failure):
    register(setup)
    wrapper, registry, artifacts = setup
    report = artifacts.root / 'new_a' / 'REPORT.md'
    card = artifacts.root / 'new_a' / artifacts.records['new_a']['cards'][0]['idea_md']
    if failure == 'missing_report':
        report.unlink()
    elif failure == 'empty_report':
        report.write_text(' ')
    elif failure == 'missing_card':
        card.unlink()
    elif failure == 'empty_card':
        card.write_text(' ')
    elif failure == 'unpublished_card':
        artifacts.records['new_a']['cards'][0]['idea_md'] = None
    else:
        artifacts.records['new_a']['cards'] = []
    before = registry.path.read_bytes()
    with pytest.raises(VersionError):
        wrapper.select_version('problem_a', 'new_a', 'old_a', True, 'tester')
    assert registry.path.read_bytes() == before


def test_success_alone_does_not_select_without_review(setup):
    register(setup)
    wrapper, registry, _ = setup
    before = registry.path.read_bytes()
    with pytest.raises(VersionError) as error:
        wrapper.select_version('problem_a', 'new_a', 'old_a', False, 'tester')
    assert error.value.status == 400
    assert registry.path.read_bytes() == before


def test_cross_problem_link_and_selection_are_rejected(setup):
    register(setup)
    wrapper, registry, artifacts = setup
    artifacts.add('third_a')
    before = registry.path.read_bytes()
    with pytest.raises(VersionError):
        wrapper.register_version('problem_a', 'third_a', 'other_b', 'tester')
    with pytest.raises(VersionError):
        wrapper.select_version('problem_a', 'other_b', 'old_a', True, 'tester')
    with pytest.raises(VersionError):
        wrapper.register_current('problem_c', 'old_a', 'tester')
    assert registry.path.read_bytes() == before


def test_selection_can_be_reversed_with_complete_history_and_backups(setup):
    register(setup)
    wrapper, registry, artifacts = setup
    wrapper.select_version('problem_a', 'new_a', 'old_a', True, 'tester')
    wrapper.select_version('problem_a', 'old_a', 'new_a', True, 'tester')
    value = registry.snapshot()
    assert value['problems']['problem_a']['selected_version'] == 'old_a'
    assert set(value['runs']) == set(artifacts.records)
    assert [e['selected_version'] for e in value['events'] if e['action'] == 'select'] == ['new_a', 'old_a']
    backups = list(registry.path.parent.glob('run_versions.json.backups/*.json'))
    assert len(backups) == value['revision']
    assert sorted(json.loads(p.read_text())['revision'] for p in backups) == list(range(value['revision']))
    assert artifacts.run_detail('new_a')['cards']  # Archived source is intact.


def test_stale_selection_cannot_overwrite_another_operator(setup):
    register(setup)
    wrapper, registry, artifacts = setup
    artifacts.add('third_a')
    wrapper.register_version('problem_a', 'third_a', 'old_a', 'tester')
    wrapper.select_version('problem_a', 'new_a', 'old_a', True, 'first')
    before = registry.path.read_bytes()
    with pytest.raises(VersionError):
        wrapper.select_version('problem_a', 'third_a', 'old_a', True, 'second')
    assert registry.path.read_bytes() == before


def test_atomic_write_failure_preserves_selected_metadata(setup, monkeypatch):
    register(setup)
    wrapper, registry, _ = setup
    before = registry.path.read_bytes()
    def fail(*args):
        raise OSError('synthetic disk failure')
    monkeypatch.setattr('arc_arena.run_versions.os.replace', fail)
    with pytest.raises(OSError):
        wrapper.select_version('problem_a', 'new_a', 'old_a', True, 'tester')
    assert registry.path.read_bytes() == before
    assert sorted(p.name for p in registry.path.parent.iterdir() if p.is_file()) == [
        'run_versions.json', 'run_versions.json.lock']


@pytest.mark.parametrize('bad', ['{', '{"schema_version": 9}',
    '{"schema_version":1,"revision":0,"problems":{"p":{"selected_version":"missing"}},"runs":{},"events":[]}'])
def test_invalid_registry_fails_closed_instead_of_showing_archived_runs(setup, bad):
    wrapper, registry, _ = setup
    registry.path.parent.mkdir()
    registry.path.write_text(bad)
    with pytest.raises(VersionError) as error:
        wrapper.list_runs()
    assert error.value.status == 503


def test_concurrent_registration_preserves_all_versions(tmp_path):
    path = tmp_path / 'versions.json'
    RunVersions(path).register_current('p', 'old', 'tester')
    def register(number):
        RunVersions(path).register_version('p', f'new_{number}', 'old', 'tester')
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(register, range(12)))
    snapshot = RunVersions(path).snapshot()
    assert len(snapshot['runs']) == 13
    assert snapshot['revision'] == 13
    assert snapshot['problems']['p']['selected_version'] == 'old'


@pytest.mark.parametrize('kind', ['detail', 'file'])
def test_selection_during_read_cannot_return_retired_content(setup, kind):
    register(setup)
    wrapper, registry, artifacts = setup
    def switch():
        registry.select('problem_a', 'new_a', 'old_a', 'tester')
    if kind == 'detail':
        artifacts.detail_hook = switch
        operation = lambda: wrapper.run_detail('old_a')
    else:
        artifacts.file_hook = switch
        operation = lambda: wrapper.read_file('old_a', 'REPORT.md')
    with pytest.raises(VersionError) as error:
        operation()
    assert error.value.status == 410


def test_api_admin_selection_and_all_default_entry_points(setup, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from arc_arena import app as app_module
    from arc_arena.auth import AuthManager
    from arc_arena.config import Config

    wrapper, _, artifacts = setup
    class FakeJobs:
        def recover(self):
            pass
        def list_jobs(self):
            return [{'id': 'old_job', 'run_dir': 'old_a'}, {'id': 'new_job', 'run_dir': 'new_a'}]
        def status(self, job_id):
            return {'job': next(j for j in self.list_jobs() if j['id'] == job_id)}
    monkeypatch.setattr(app_module, 'JobManager', lambda cfg: FakeJobs())
    monkeypatch.setattr(app_module, 'Artifacts', lambda *args: artifacts)
    cfg = Config(data_dir=tmp_path / 'app_data', backend_root=tmp_path / 'unused_backend')
    application = app_module.create_app(cfg)
    auth = AuthManager(cfg.db_path)
    auth.create_user('version_admin', 'synthetic-password', is_admin=True)
    auth.create_user('version_reader', 'synthetic-password')

    with TestClient(application) as client:
        assert client.get('/api/run-versions').status_code == 401
        assert client.post('/api/auth/login', json={'username': 'version_reader', 'password': 'synthetic-password'}).status_code == 200
        assert client.get('/api/run-versions').status_code == 403
        assert client.post('/api/run-versions/current', json={'problem_id': 'p', 'run_id': 'old_a'}).status_code == 403
        assert client.post('/api/auth/login', json={'username': 'version_admin', 'password': 'synthetic-password'}).status_code == 200
        assert client.post('/api/run-versions/current', json={'problem_id': 'p', 'run_id': 'old_a'}).status_code == 200
        assert client.post('/api/run-versions/versions', json={
            'problem_id': 'p', 'run_id': 'new_a', 'previous_run_id': 'old_a'}).status_code == 200
        assert client.get('/api/runs/old_a').status_code == 200
        assert client.get('/api/runs/new_a').status_code == 410
        selection = {'problem_id': 'p', 'run_id': 'new_a', 'expected_selected': 'old_a'}
        assert client.post('/api/run-versions/selection', json=selection).status_code == 400
        assert client.post('/api/run-versions/selection', json={**selection, 'reviewed': True}).status_code == 200
        runs = client.get('/api/runs').json()['runs']
        assert 'old_a' not in {r['dir'] for r in runs}
        assert client.get('/api/runs/old_a').status_code == 410
        assert client.get('/api/runs/old_a/file?name=REPORT.md').status_code == 410
        visibility = client.get('/api/runs/old_a/visibility').json()
        assert visibility['visible'] is False and visibility['current_run_id'] == 'new_a'
        assert [j['id'] for j in client.get('/api/jobs').json()['jobs']] == ['new_job']
        assert client.get('/api/jobs/old_job').status_code == 410
        assert client.get('/api/jobs/old_job/visibility').json()['current_run_id'] == 'new_a'
        assert client.get('/api/jobs/new_job/visibility').json()['visible'] is True
        assert client.get('/api/run-versions/runs/old_a').json()['cards']
        assert client.get('/api/run-versions/runs/old_a/file?name=REPORT.md').status_code == 200
        assert client.get('/api/runs/new_a').json()['cards'] == artifacts.records['new_a']['cards']


def test_invalid_ids_never_reach_artifact_reader(setup):
    wrapper, _, artifacts = setup
    def forbidden(*args):
        pytest.fail('invalid identifier reached scientific records')
    artifacts.run_detail = forbidden
    for invalid in ('../old_a', '/old_a', '..', ''):
        with pytest.raises(VersionError) as error:
            wrapper.run_detail(invalid)
        assert error.value.status == 400
