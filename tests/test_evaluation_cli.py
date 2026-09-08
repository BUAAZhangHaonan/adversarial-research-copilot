"""Public evaluation flags delegate explicitly without model calls."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from arc.cli import app


@pytest.mark.parametrize('options,expected', [
    ([], {'seed': 20260907, 'include_swapped_order': True}),
    (['--seed', '42', '--no-swap-order'], {'seed': 42, 'include_swapped_order': False}),
    (['--seed', '13', '--swap-order'], {'seed': 13, 'include_swapped_order': True}),
])
def test_comparison_cli_passes_seed_and_presentation_order(tmp_path, monkeypatch, options, expected):
    calls = []

    async def fake(settings, source, **kwargs):
        calls.append((source, kwargs))

    monkeypatch.setattr('arc.evaluation.run_comparison', fake)
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path / 'data'),
        'test-compare', '--source-run', 'source.run', *options])
    assert result.exit_code == 0, result.output + repr(result.exception)
    assert calls == [('source.run', expected)]
    assert not (tmp_path / 'data' / 'arc.sqlite').exists()


def test_comparison_requires_source_run(tmp_path, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail('Missing source must not start comparison')

    monkeypatch.setattr('arc.evaluation.run_comparison', forbidden)
    result = CliRunner().invoke(app, ['--data-dir', str(tmp_path / 'data'), 'test-compare'])
    assert result.exit_code != 0 and '--source-run' in result.output
