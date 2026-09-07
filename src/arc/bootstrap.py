"""Assemble installed resources and configured read-only services."""
import json
import os
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
    config_root = files('arc_config_assets')
    prices = PriceBook(Path(str(config_root.joinpath('pricing.json'))))
    price_check = await prices.verify_online()
    store.save_artifact(f'runs/{run.run_id}/price-verification.json', json.dumps(price_check, ensure_ascii=False))
    if price_check['status'] != 'unchanged':
        print(json.dumps({'price_snapshot_warning': price_check}, ensure_ascii=False), flush=True)
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
        loader=loader, role_models=settings.roles, prices=prices,
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'), tools=tools,
        on_progress=progress)
