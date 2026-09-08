"""Public evaluation flags delegate explicitly without model calls."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from arc.cli import app


def ablation_arguments():
    return ['--source-run', 'source.run', '--experiment-id', 'ablation-1',
            '--parent-budget', 'authorized-parent', '--budget-cny', '7.50', '--seed', '41']


@pytest.mark.parametrize('custom_root', [False, True])
def test_ablation_cli_passes_explicit_budget_identity_and_prompt_directory(tmp_path, monkeypatch, custom_root):
    monkeypatch.chdir(Path(__file__).parents[1])
    root = Path('tests/fixtures/prompts_pre_redesign').resolve()
    options = []
    if custom_root:
        root = tmp_path / 'historical-prompts'
        root.mkdir()
        (root / 'manifest.json').write_text('{}', encoding='utf-8')
        options = ['--legacy-prompt-root', str(root)]
    calls = []

    async def fake(settings, source, **kwargs):
        calls.append((source, kwargs))

    monkeypatch.setattr('arc.functional_evaluation.run_ablation', fake)
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path / 'data'),
        'test-ablation', *ablation_arguments(), *options])
    assert result.exit_code == 0, result.output + repr(result.exception)
    assert calls == [('source.run', {'experiment_id': 'ablation-1',
        'parent_id': 'authorized-parent', 'budget_cny': '7.50', 'seed': 41,
        'legacy_prompt_root': root})]
    assert not (tmp_path / 'data' / 'arc.sqlite').exists()


@pytest.mark.parametrize('missing', ['--source-run', '--experiment-id', '--parent-budget', '--budget-cny', '--seed'])
def test_ablation_requires_each_execution_input_before_calling_harness(tmp_path, monkeypatch, missing):
    async def forbidden(*args, **kwargs):
        pytest.fail('Missing input must not start evaluation')

    monkeypatch.setattr('arc.functional_evaluation.run_ablation', forbidden)
    args = ablation_arguments()
    index = args.index(missing)
    del args[index:index + 2]
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path / 'data'), 'test-ablation', *args])
    assert result.exit_code != 0 and missing in result.output
    assert not (tmp_path / 'data' / 'arc.sqlite').exists()


@pytest.mark.parametrize('case', ['missing_directory', 'missing_manifest', 'missing_default', 'zero', 'nan'])
def test_ablation_rejects_missing_historical_prompts_and_invalid_budget(tmp_path, monkeypatch, case):
    async def forbidden(*args, **kwargs):
        pytest.fail('Invalid setup must not start evaluation')

    monkeypatch.setattr('arc.functional_evaluation.run_ablation', forbidden)
    args = ablation_arguments()
    if case == 'missing_default':
        monkeypatch.chdir(tmp_path)
    else:
        root = tmp_path / 'prompts'
        if case != 'missing_directory':
            root.mkdir()
        if case in {'zero', 'nan'}:
            (root / 'manifest.json').write_text('{}', encoding='utf-8')
            args[args.index('--budget-cny') + 1] = '0' if case == 'zero' else 'NaN'
        args += ['--legacy-prompt-root', str(root)]
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path / 'data'), 'test-ablation', *args])
    assert result.exit_code != 0
    assert ('--budget-cny' if case in {'zero', 'nan'} else '--legacy-prompt-root') in result.output
    assert not (tmp_path / 'data' / 'arc.sqlite').exists()
