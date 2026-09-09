"""Assemble installed resources and configured read-only services."""
import json
from importlib.resources import files
from pathlib import Path
import shutil
import hashlib

from .mcp_client import MCPHub
from .pricing import PriceBook
from .prompting import PromptLoader
from .runtime import Runtime, build_tools


async def make_runtime(store, ledger, run, settings):
    run_root = settings.data_dir.resolve() / 'artifacts' / 'runs' / run.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    resource_root = run_root / 'prompt-resources'
    # A whole run keeps the same prompt resources, including future unfinished tasks.
    if not resource_root.exists():
        temporary = run_root / 'prompt-resources.tmp'
        shutil.copytree(Path(str(files('arc_prompt_assets'))), temporary, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        temporary.rename(resource_root)
    loader = PromptLoader(resource_root=resource_root)
    if run.prompt_version.startswith('bundle-sha256:') and run.prompt_version != 'bundle-sha256:' + loader.bundle_hash:
        from .runtime import RuntimePaused
        raise RuntimePaused('PAUSED_PROTOCOL', 'RUN_PROMPT_BUNDLE_CHANGED_FORK_REQUIRED')
    config_root = files('arc_config_assets')
    prices = PriceBook(settings.pricing_path or Path(str(config_root.joinpath('pricing.json'))))
    mappings = json.loads(config_root.joinpath('mcp.json').read_text(encoding='utf-8'))
    hub = MCPHub.from_environment(mappings)
    await hub.prepare()
    store.save_artifact(f'runs/{run.run_id}/mcp_inventory.json', json.dumps(
        {'inventory': hub.inventory, 'failures': hub.failures}, ensure_ascii=False, indent=2))
    all_tools = build_tools(store, hub)
    # Financially unavailable operations remain in the inventory/requirements record,
    # but are not advertised as executable research tools in this run.
    tools = {name: tool for name, tool in all_tools.items() if tool.cost_upper_cny is not None}
    blocked = {name: tool.cost_basis for name, tool in all_tools.items() if tool.cost_upper_cny is None}
    state = dict(store.get_run(run.run_id).state)
    state.update(available_tools=list(tools), blocked_capabilities=blocked)
    manifest_hash = hashlib.sha256((resource_root / 'manifest.json').read_bytes()).hexdigest()
    state['prompt_manifest_hash'] = manifest_hash
    state['prompt_bundle_hash'] = loader.bundle_hash
    store.update_run(run.run_id, state=state)
    def progress(event):
        current = store.get_run(run.run_id)
        campaign = store.get_campaign(current.campaign_id) if current.campaign_id else None
        event.update(run_status=current.status, card_id=current.card_id, card_version=current.card_version,
                     rounds_completed=current.state.get('rounds_completed', 0),
                     draws_started=campaign.draws_started if campaign else None,
                     max_draws=campaign.max_draws if campaign else None)
        print(json.dumps(event, ensure_ascii=False, default=str), flush=True)

    return Runtime(store=store, ledger=ledger, account_id=run.budget_account_id,
        loader=loader, role_models=settings.roles, models=settings.models, prices=prices,
        tools=tools,
        on_progress=progress)
