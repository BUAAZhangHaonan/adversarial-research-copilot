"""Two explicitly selected development samples; no automatic retries or stage transitions."""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
from arc.cli import new_run, execute, services
from arc.config import Settings

TOPICS = {
    1: "多模态模型在真实任务中何时需要主动获取额外信息。",
    2: "具身智能在环境变化后如何使用和更新既有经验。",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=int, choices=TOPICS)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    settings = Settings(data_dir=args.data_dir.resolve())
    store, ledger = services(settings)
    parent = ledger.summary(args.parent)
    pending = [call for call in ledger.list_calls(args.parent) if call["state"] not in {"SETTLED", "NOT_SENT"}]
    # HTTP 400 was rejected before streaming; preserve its full unknown-cost
    # reservation while allowing this independent sample. Never replay it here.
    rejected = [call for call in pending if call["state"] == "UNKNOWN"
                and call.get("metadata", {}).get("error") == "BadRequestError"]
    if len(rejected) != len(pending):
        raise RuntimeError("PARENT_HAS_ACTIVE_OR_UNIDENTIFIED_REQUESTS")
    if parent["remaining_micro"] < 20_000_000:
        raise RuntimeError("INSUFFICIENT_EXISTING_AUTHORIZED_BALANCE")
    run_id = f"discover-first-20260909.sample{args.sample}"
    with store._connect() as db:
        exists = db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone()
    if exists:
        raise RuntimeError("SAMPLE_ALREADY_EXISTS: inspect or explicitly resume the saved run; do not recreate")
    run = new_run(settings, "discover", topic=TOPICS[args.sample], budget="20",
                  parent=args.parent, run_id=run_id)
    store.update_run(run_id, state={**run.state, "validation_scope": "development_sample_not_quality_certification"})
    print(json.dumps({"event": "sample_started", "run_id": run_id, "topic": TOPICS[args.sample],
                      "stage_cap_cny": 20, "total_sample_cap_cny": 40}, ensure_ascii=False), flush=True)
    asyncio.run(execute(settings, run_id))


if __name__ == "__main__":
    main()
