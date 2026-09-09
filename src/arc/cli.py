"""Stage boundaries are explicit CLI actions, not model decisions."""
from __future__ import annotations
import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Optional
from uuid import uuid4
import hashlib
import typer
from dotenv import load_dotenv
from .config import load_settings, Settings
from .prompting import PromptLoader

app = typer.Typer(help='ARC：发现研究卡、展开方案、压力测试。每个阶段默认结束即停。', no_args_is_help=True)
requirements = typer.Typer(help='登记改进需求、记录用户评估并导出执行模板；不执行变更。', no_args_is_help=True)
app.add_typer(requirements, name='requirements')


@requirements.command(name='add')
def add_requirement(ctx: typer.Context, run_id: str, request: Path = typer.Option(..., exists=True, dir_okay=False)):
    store, _ = services(ctx.obj)
    identifier=store.save_capability_request(run_id,json.loads(request.read_text(encoding='utf-8')))
    typer.echo(identifier)


@requirements.command(name='list')
def list_requirements(ctx: typer.Context, run_id: str):
    store, _ = services(ctx.obj)
    typer.echo(json.dumps(store.list_capability_requests(run_id),ensure_ascii=False,indent=2))


@requirements.command(name='review')
def review_requirement(ctx: typer.Context, request_id: str, review: Path = typer.Option(..., exists=True, dir_okay=False),
                       reviewer: str = typer.Option('user'), development_review: bool = typer.Option(False)):
    """记录评估 JSON；开发阶段可显式指定 codex 评估者，不触发模型。"""
    if reviewer not in ('user','codex'):
        raise typer.BadParameter('--reviewer must be user or codex')
    if reviewer=='codex' and not development_review:
        raise typer.BadParameter('--reviewer codex requires --development-review')
    store, _ = services(ctx.obj)
    record=store.review_capability_request(request_id,json.loads(review.read_text(encoding='utf-8')),
                                          reviewer=reviewer,development=development_review)
    typer.echo(json.dumps(record,ensure_ascii=False,indent=2))


@requirements.command(name='export')
def export_requirement(ctx: typer.Context, request_id: str, output: Optional[Path] = typer.Option(None),
                       development_review: bool = typer.Option(False)):
    from .reports import render_capability_handoff
    store, _ = services(ctx.obj)
    text=render_capability_handoff(store.get_capability_request(request_id),development_review=development_review)
    if output is None:
        typer.echo(text)
    else:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(text,encoding='utf-8')
        typer.echo(str(output))

@app.callback()
def root(ctx: typer.Context, data_dir: Optional[Path] = typer.Option(None),
         config: Optional[Path] = typer.Option(None), env_file: Optional[Path] = typer.Option(None)):
    if env_file:
        load_dotenv(env_file, override=False)
    ctx.obj = load_settings(config, data_dir=data_dir)

def services(settings):
    from .store import Store
    from .budget import BudgetLedger
    root = settings.data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return Store(root / 'arc.sqlite', artifact_root=root / 'artifacts'), BudgetLedger(root / 'arc.sqlite')

def new_run(settings, mode, *, topic=None, card_id=None, version=None,
            budget='20', parent=None, run_id=None, campaign_id=None, input_text=None,
            parent_card_id=None, parent_card_version=None, boundaries=None, idea_id=None):
    store, ledger = services(settings)
    run_id = run_id or f'run_{uuid4().hex}'
    amount = Decimal(str(budget))
    if amount <= 0:
        raise typer.BadParameter('budget_cny must be positive')
    inherited = None
    idea_input = None
    if idea_id:
        if mode not in ('develop', 'run') or card_id or input_text:
            raise typer.BadParameter('--idea requires develop/run and cannot be combined with another input')
        idea = store.get_discovery_idea(idea_id)
        if not idea.get('seed'): raise typer.BadParameter('idea has no submitted seed')
        origin = store.get_run(idea['run_id'])
        campaign_id = origin.campaign_id
        campaign = store.get_campaign(campaign_id)
        idea_input = {'idea_id': idea_id, 'original_question': campaign.topic, 'user_boundaries': campaign.boundaries,
            'seed': idea['seed'], 'latest_note': idea['note'], 'field_brief': origin.state.get('field_brief')}
        latest = store.latest_idea_prestudy(idea_id)
        if latest:
            idea_input.update(latest_note=latest['note'], latest_note_origin={'run_id': latest['run_id'], 'mode': latest['mode']})
    if mode in ('develop', 'run'):
        if not card_id and not input_text and not idea_id:
            raise typer.BadParameter('--card is required')
        if card_id:
            version = store.get_card(card_id, version).version
            inherited = store.card_provenance_context(card_id, version)
            campaigns = inherited['provenance_campaign_ids']
            if campaign_id is None and len(campaigns) == 1:
                campaign_id = campaigns[0]
    ledger.create_account(run_id, str(amount), parent_id=parent)
    if mode == 'discover':
        campaign = store.create_campaign(topic, boundaries=boundaries, max_draws=settings.draws,
            budget_account_id=run_id, campaign_id=campaign_id,
            parent_card_id=parent_card_id, parent_card_version=parent_card_version)
        campaign_id = campaign.campaign_id
    prompt_hash = 'bundle-sha256:' + PromptLoader().bundle_hash
    code_hash = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
    state = {'source_ids': inherited['source_ids'], 'evidence_ids': inherited['evidence_ids'],
             'input_provenance': inherited} if inherited else {}
    if mode == 'discover':
        state.update(discover_first=True, idea_ids=[])
        reusable = store.reusable_discovery_brief(topic, boundaries)
        if reusable: state['reusable_survey'] = reusable
    if idea_input: state.update(idea_input=idea_input, discover_first=True)
    if input_text:
        from .schemas import SourceRecord
        source = store.register_source(SourceRecord(title='用户导入的研究问题', url=None,
            source_type='user_material', access_status='retrieved', content_origin='original'), content=input_text)
        state = {'imported_input': input_text, 'source_ids': [source.source_id], 'input_origin': 'user_proposal'}
    return store.create_run(mode, campaign_id=campaign_id, card_id=card_id,
        card_version=version, budget_account_id=run_id, config=settings.model_dump(mode='json'), run_id=run_id,
        prompt_version=prompt_hash, code_version='arc-0.2.0:' + code_hash, state=state)

async def execute(settings, run_id):
    from .bootstrap import make_runtime
    from .reports import render_run
    from .workflows import WorkflowEngine
    store, ledger = services(settings)
    run = store.get_run(run_id)
    frozen = Settings.model_validate(run.config)
    runtime = None
    try:
        runtime = await make_runtime(store, ledger, run, frozen)
        await WorkflowEngine(store, runtime, frozen).execute(run_id)
    except Exception as exc:
        status, reason = getattr(exc, 'status', None), getattr(exc, 'reason', None)
        if status in {'PAUSED_BUDGET', 'PAUSED_EXTERNAL', 'PAUSED_PROTOCOL'}:
            store.update_run(run_id, status=status, stop_reason=reason or type(exc).__name__)
        else:
            store.update_run(run_id, status='ERROR', stop_reason=type(exc).__name__)
            raise
    finally:
        render_run(store, run_id, settings.data_dir.resolve() / 'reports' / run_id)
        close = getattr(runtime, 'close', None)
        if close:
            await close()
    run = store.get_run(run_id)
    typer.echo(json.dumps({'run_id': run_id, 'status': run.status, 'assessment': run.assessment,
        'stop_reason': run.stop_reason, 'cost': ledger.summary(run.budget_account_id)}, ensure_ascii=False, default=str))
    return run

@app.command()
def discover(ctx: typer.Context, topic: str, draws: Optional[int] = typer.Option(None, min=1, max=5),
             budget_cny: Optional[str] = typer.Option(None)):
    settings = ctx.obj.model_copy(update={'draws': draws}) if draws is not None else ctx.obj
    run = new_run(settings, 'discover', topic=topic, budget=budget_cny or settings.budget_cny)
    asyncio.run(execute(settings, run.run_id))

@app.command()
def develop(ctx: typer.Context, card: Optional[str] = typer.Option(None),
            version: Optional[int] = typer.Option(None, min=1), budget_cny: Optional[str] = typer.Option(None),
            question: Optional[str] = typer.Option(None), proposal: Optional[Path] = typer.Option(None),
            idea: Optional[str] = typer.Option(None)):
    text = explicit_input(card, question, proposal, idea)
    run = new_run(ctx.obj, 'develop', card_id=card, version=version,
                  budget=budget_cny or ctx.obj.budget_cny, input_text=text, idea_id=idea)
    asyncio.run(execute(ctx.obj, run.run_id))

@app.command(name='run')
def pressure_test(ctx: typer.Context, card: Optional[str] = typer.Option(None),
                  version: Optional[int] = typer.Option(None, min=1), budget_cny: Optional[str] = typer.Option(None),
                  question: Optional[str] = typer.Option(None), proposal: Optional[Path] = typer.Option(None),
            idea: Optional[str] = typer.Option(None)):
    text = explicit_input(card, question, proposal, idea)
    run = new_run(ctx.obj, 'run', card_id=card, version=version,
                  budget=budget_cny or ctx.obj.budget_cny, input_text=text, idea_id=idea)
    asyncio.run(execute(ctx.obj, run.run_id))

def explicit_input(card, question, proposal, idea=None):
    if sum(value is not None for value in (card, question, proposal, idea)) != 1:
        raise typer.BadParameter('choose exactly one of --idea, --card, --question, --proposal')
    return proposal.read_text(encoding='utf-8') if proposal is not None else question

@app.command()
def status(ctx: typer.Context, run_id: str):
    store, ledger = services(ctx.obj)
    run = store.get_run(run_id)
    typer.echo(json.dumps({'run': run.model_dump(mode='json'),
        'issues': [i.model_dump(mode='json') for i in store.get_issues(run_id)],
        'budget': ledger.summary(run.budget_account_id)}, ensure_ascii=False, indent=2, default=str))

@app.command()
def resume(ctx: typer.Context, run_id: str, add_budget_cny: Optional[str] = typer.Option(None)):
    store, ledger = services(ctx.obj)
    run = store.get_run(run_id)
    if add_budget_cny is not None:
        ledger.add_budget(run.budget_account_id, add_budget_cny, reason='explicit_cli_budget_addition')
    asyncio.run(execute(ctx.obj, run_id))

@app.command(name='retry-task')
def retry_task(ctx: typer.Context, run_id: str, task_key: str = typer.Option(...),
               reason: str = typer.Option(...)):
    """显式重试失败的 Agent 任务；保留原记录、当前卡及预算。"""
    from .retrying import prepare_task_retry
    from .store import StateError
    store, ledger = services(ctx.obj)
    try:
        retry = prepare_task_retry(store, ledger, run_id, task_key, reason)
    except StateError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(retry, ensure_ascii=False))
    asyncio.run(execute(ctx.obj, run_id))


@app.command(name='import-card')
def import_card(ctx: typer.Context, path: Path):
    """显式导入用户研究卡 JSON；不编造证据，不自动判通过。"""
    from .schemas import CardDraft
    store, _ = services(ctx.obj)
    card = store.save_card(CardDraft.model_validate_json(path.read_text(encoding='utf-8')))
    typer.echo(json.dumps({'card_id': card.card_id, 'version': card.version}, ensure_ascii=False))

@app.command(name='test-e2e')
def test_e2e(ctx: typer.Context, campaign: str = typer.Option('ARC_VNEXT_VALIDATION'),
             total_budget_cny: str = typer.Option('100'), allow_stage_transition: bool = typer.Option(False),
             topic: str = typer.Option('拥挤小目标实例分割中，边界错误与实例合并错误是否需要不同的测量与干预')):
    if not allow_stage_transition:
        raise typer.BadParameter('--allow-stage-transition is required')
    if not 0 < Decimal(total_budget_cny) <= 100:
        raise typer.BadParameter('development parent must be within CNY 100')
    from .evaluation import run_e2e
    asyncio.run(run_e2e(ctx.obj, campaign, topic, total_budget_cny))

@app.command(name='test-compare')
def test_compare(ctx: typer.Context, source_run: str = typer.Option(...),
                 seed: int = typer.Option(20260907),
                 swap_order: bool = typer.Option(True, '--swap-order/--no-swap-order')):
    """开发用：冻结同材料比较，自动评价不代表人类认可。"""
    from .evaluation import run_comparison
    asyncio.run(run_comparison(ctx.obj, source_run, seed=seed, include_swapped_order=swap_order))


@app.command(name='test-ablation')
def test_ablation(ctx: typer.Context, source_run: str = typer.Option(...),
                  experiment_id: str = typer.Option(...), parent_budget: str = typer.Option(...),
                  budget_cny: str = typer.Option(...), seed: int = typer.Option(...),
                  legacy_prompt_root: Path = typer.Option(Path('tests/fixtures/prompts_pre_redesign'),
                      exists=True, file_okay=False, resolve_path=True)):
    """开发用：在显式父账本内串行运行或恢复冻结材料的 A–E 消融。"""
    from decimal import InvalidOperation
    from .functional_evaluation import run_ablation
    try:
        budget = Decimal(budget_cny)
    except InvalidOperation as exc:
        raise typer.BadParameter('budget must be a positive finite CNY amount', param_hint='--budget-cny') from exc
    if not budget.is_finite() or budget <= 0:
        raise typer.BadParameter('budget must be a positive finite CNY amount', param_hint='--budget-cny')
    if not (legacy_prompt_root / 'manifest.json').is_file():
        raise typer.BadParameter('historical prompt directory must contain manifest.json',
                                 param_hint='--legacy-prompt-root')
    report = asyncio.run(run_ablation(ctx.obj, source_run, experiment_id=experiment_id,
        parent_id=parent_budget, budget_cny=budget_cny, seed=seed, legacy_prompt_root=legacy_prompt_root))
    summary = {'experiment_id': report['experiment_id'], 'status': report['status'],
        'conditions': {key: report.get('conditions', {}).get(key, {}).get('status', 'NOT_STARTED')
                       for key in 'ABCDE'},
        'judge_status': report.get('judge_status', 'NOT_STARTED'),
        'report_path': str(ctx.obj.data_dir.resolve() / 'artifacts' / 'functional-evaluations'
                           / experiment_id / 'report.json')}
    typer.echo(json.dumps(summary, ensure_ascii=False))
    if report['status'] != 'completed':
        raise typer.Exit(code=1)

@app.command(name='retry-comparison-task')
def retry_comparison_task(ctx: typer.Context, source_run: str,
                          system: str = typer.Option(...), task_key: str = typer.Option(...),
                          reason: str = typer.Option(...)):
    """显式重试冻结对照的失败任务；保留旧输出、已完成候选和原账本。"""
    from .comparison_retry import prepare_comparison_retry, comparison_retry_options
    from .evaluation import run_comparison
    from .store import StateError
    store, ledger = services(ctx.obj)
    try:
        retry = prepare_comparison_retry(store, ledger, source_run, system, task_key, reason)
    except StateError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(retry, ensure_ascii=False))
    asyncio.run(run_comparison(ctx.obj, source_run, **comparison_retry_options(task_key)))


@app.command(name='restart-direction')
def restart_direction(ctx: typer.Context, run_id: str, approve_scope_change: bool = typer.Option(False)):
    """用户明确批准后，从新的 discover 开始，不继承通过状态。"""
    if not approve_scope_change:
        raise typer.BadParameter('--approve-scope-change is required')
    store, _ = services(ctx.obj)
    changes = store.get_scope_changes(run_id)
    if len(changes) != 1:
        raise typer.BadParameter('one frozen scope change is required')
    change = changes[0].model_dump(mode='json')
    run = new_run(ctx.obj, 'discover', topic=change['proposed_problem_anchor']['question'], budget=ctx.obj.budget_cny,
        parent_card_id=change['parent_card_id'], parent_card_version=change['parent_card_version'])
    store.update_run(run.run_id, state={'direction_parent_run': run_id, 'direction_source_event': change,
        'source_ids': change['original_sources_revisited']})
    asyncio.run(execute(ctx.obj, run.run_id))
