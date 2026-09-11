"""Transactional parent/child CNY accounting in integer millionths of a yuan."""
from __future__ import annotations
from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from .schemas import utc_now

MICRO = Decimal(1_000_000)

class BudgetError(RuntimeError):
    pass

class BudgetExceeded(BudgetError):
    pass

def to_micro(value, *, upper=True) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid_cny_amount")
    return int((amount * MICRO).to_integral_value(rounding=ROUND_CEILING if upper else ROUND_FLOOR))

def as_cny(value: int) -> str:
    return format(Decimal(value) / MICRO, ".6f")

class BudgetLedger:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS budget_accounts (
                  account_id TEXT PRIMARY KEY, parent_id TEXT REFERENCES budget_accounts(account_id),
                  limit_micro INTEGER NOT NULL CHECK(limit_micro>=0), created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS budget_authorizations (
                  authorization_id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
                  added_micro INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS budget_calls (
                  call_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES budget_accounts(account_id),
                  reserved_micro INTEGER NOT NULL, admitted_micro INTEGER NOT NULL,
                  lower_micro INTEGER NOT NULL DEFAULT 0, upper_micro INTEGER,
                  state TEXT NOT NULL, cost_status TEXT, metadata TEXT NOT NULL,
                  started_at TEXT, completed_at TEXT, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS budget_calls_account ON budget_calls(account_id);
            """)

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create_account(self, id, limit_cny, parent_id=None):
        limit = to_micro(limit_cny)
        with self._transaction() as db:
            existing = db.execute("SELECT * FROM budget_accounts WHERE account_id=?", (id,)).fetchone()
            if existing:
                if existing["parent_id"] != parent_id or existing["limit_micro"] != limit:
                    raise BudgetError("account_exists_with_different_authorization")
            else:
                if parent_id is not None:
                    parent = db.execute("SELECT * FROM budget_accounts WHERE account_id=?", (parent_id,)).fetchone()
                    if parent is None:
                        raise BudgetError("parent_account_missing")
                    if limit > parent["limit_micro"]:
                        raise BudgetError("child_limit_exceeds_parent_authorization")
                db.execute("INSERT INTO budget_accounts VALUES (?,?,?,?)", (id, parent_id, limit, utc_now()))
                db.execute("INSERT INTO budget_authorizations(account_id,added_micro,reason,created_at) VALUES (?,?,?,?)", (id, limit, "initial_authorization", utc_now()))
        return self.summary(id)

    def _summary(self, db, account_id):
        account = db.execute("SELECT * FROM budget_accounts WHERE account_id=?", (account_id,)).fetchone()
        if account is None:
            raise BudgetError("account_missing")
        aggregate = db.execute("""
            WITH RECURSIVE descendants(id) AS (
              SELECT ? UNION ALL SELECT a.account_id FROM budget_accounts a JOIN descendants d ON a.parent_id=d.id)
            SELECT COALESCE(SUM(CASE WHEN state='SETTLED' THEN lower_micro ELSE 0 END),0) AS lower,
              COALESCE(SUM(CASE WHEN state='SETTLED' THEN upper_micro ELSE 0 END),0) AS upper,
              COALESCE(SUM(reserved_micro),0) AS reserved,
              COALESCE(SUM(CASE WHEN state='UNKNOWN' THEN lower_micro ELSE 0 END),0) AS unsettled_lower,
              COALESCE(SUM(CASE WHEN state='UNKNOWN' THEN 1 ELSE 0 END),0) AS unknown,
              COALESCE(SUM(CASE WHEN cost_status='unmetered' AND state!='NOT_SENT' THEN 1 ELSE 0 END),0) AS unmetered,
              COUNT(*) AS calls FROM budget_calls WHERE account_id IN (SELECT id FROM descendants)
        """, (account_id,)).fetchone()
        lower, upper, reserved = aggregate["lower"], aggregate["upper"], aggregate["reserved"]
        remaining = account["limit_micro"] - upper - reserved
        return {
            "account_id": account_id, "parent_id": account["parent_id"],
            "limit_micro": account["limit_micro"], "spent_lower_micro": lower,
            "spent_upper_micro": upper, "reserved_micro": reserved, "remaining_micro": remaining,
            "limit_cny": as_cny(account["limit_micro"]), "spent_lower_cny": as_cny(lower),
            "spent_upper_cny": as_cny(upper), "reserved_cny": as_cny(reserved),
            "remaining_cny": as_cny(remaining), "unknown_calls": aggregate["unknown"],
            "call_count": aggregate["calls"], "currency": "CNY",
            "unmetered_calls": aggregate["unmetered"],
            "total_cost_complete": not bool(aggregate["unmetered"] or aggregate["unknown"] or reserved),
            "cost_scope": "metered_costs_only" if aggregate["unmetered"] else "recorded_costs",
            "unsettled_lower_micro": aggregate["unsettled_lower"],
            "unsettled_lower_cny": as_cny(aggregate["unsettled_lower"]),
        }

    def summary(self, account_id):
        with self._connect() as db:
            return self._summary(db, account_id)

    def _call(self, row):
        result = dict(row)
        result["metadata"] = json.loads(result["metadata"])
        result.update(reserved_cny=as_cny(result["reserved_micro"]),
                      cost_estimate_lower=as_cny(result["lower_micro"]),
                      cost_estimate_upper=None if result["upper_micro"] is None else as_cny(result["upper_micro"]))
        metadata=result["metadata"]
        for name in ("campaign_id","run_id","stage","task_id","request_id","model_requested",
                     "model_returned","fingerprint","thinking","effort","prompt_manifest","prompt_hash",
                     "price_snapshot_id","tool_call_id","parent_call_id","finish_reason","response_artifact_path"):
            result[name]=metadata.get(name)
        result["attempt_id"]=metadata.get("attempt_id",result["call_id"])
        result["retry_number"]=metadata.get("attempt")
        usage=metadata.get("usage") or {}
        result["input_tokens"]=usage.get("prompt_tokens")
        result["cache_hit_tokens"]=usage.get("prompt_cache_hit_tokens")
        result["cache_miss_tokens"]=usage.get("prompt_cache_miss_tokens")
        result["completion_tokens"]=usage.get("completion_tokens")
        result["reasoning_tokens"]=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        result["currency"]="CNY"
        result["reserved_amount"]=as_cny(result["reserved_micro"])
        result["cost_actual_if_available"]=metadata.get("cost_actual_if_available")
        if result["cost_status"]=="measured_invoice" and result["lower_micro"]==result["upper_micro"]:
            result["cost_actual_if_available"]=as_cny(result["upper_micro"])
        if result['cost_status'] == 'unmetered':
            # Integer admission columns are unused for authorized external costs;
            # never expose their storage placeholders as a zero-price claim.
            for name in ('reserved_micro', 'admitted_micro', 'lower_micro', 'upper_micro',
                         'reserved_cny', 'reserved_amount', 'cost_estimate_lower', 'cost_estimate_upper'):
                result[name] = None
            result['external_cost_status'] = 'unmetered'
            result['outcome_status'] = metadata.get('outcome_status', 'pending')
        return result

    def get_call(self, call_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM budget_calls WHERE call_id=?", (call_id,)).fetchone()
            return self._call(row) if row else None

    def reserve(self, account_id, call_id, upper_cny, **metadata):
        maximum = to_micro(upper_cny)
        with self._transaction() as db:
            old = db.execute("SELECT * FROM budget_calls WHERE call_id=?", (call_id,)).fetchone()
            if old:
                if old["account_id"] != account_id or old["admitted_micro"] != maximum:
                    raise BudgetError("call_id_reused_with_different_admission")
                original=json.loads(old["metadata"])
                if any(key not in original or original[key]!=value for key,value in metadata.items()):
                    raise BudgetError("call_id_reused_with_different_request_metadata")
                return self._call(old)
            current = account_id
            while current is not None:
                summary = self._summary(db, current)
                if summary["remaining_micro"] < maximum:
                    raise BudgetExceeded(f"budget_not_admitted:{current}")
                current = summary["parent_id"]
            db.execute("""INSERT INTO budget_calls
                (call_id,account_id,reserved_micro,admitted_micro,state,metadata,created_at)
                VALUES (?,?,?,?,?,?,?)""", (call_id, account_id, maximum, maximum, "RESERVED", json.dumps(metadata, ensure_ascii=False), utc_now()))
        return self.get_call(call_id)

    def register_unmetered(self, account_id, call_id, **metadata):
        """Record authorized external execution without asserting a price bound."""
        if not (metadata.get('allow_unmetered') is True
                and metadata.get('service') == 'scholartrace' and metadata.get('method') == 'search_literature'):
            raise BudgetError('unmetered_tool_not_authorized')
        with self._transaction() as db:
            if db.execute('SELECT 1 FROM budget_accounts WHERE account_id=?', (account_id,)).fetchone() is None:
                raise BudgetError('account_missing')
            old = db.execute('SELECT * FROM budget_calls WHERE call_id=?', (call_id,)).fetchone()
            if old:
                if (old['account_id'] != account_id or old['cost_status'] != 'unmetered'
                        or json.loads(old['metadata']) != metadata):
                    raise BudgetError('call_id_reused_with_different_request_metadata')
                return self._call(old)
            # This table's nonnullable numeric columns are not used for this row.
            # Public views return null and summary explicitly excludes external cost.
            db.execute("""INSERT INTO budget_calls
                (call_id,account_id,reserved_micro,admitted_micro,state,cost_status,metadata,created_at)
                VALUES (?,?,0,0,'RESERVED','unmetered',?,?)""",
                (call_id, account_id, json.dumps(metadata, ensure_ascii=False), utc_now()))
        return self.get_call(call_id)

    def finish_unmetered(self, call_id, *, outcome_unknown=False, **metadata):
        """SETTLED closes the action record, not an assertion of measured cost."""
        with self._transaction() as db:
            old = db.execute('SELECT * FROM budget_calls WHERE call_id=?', (call_id,)).fetchone()
            if old is None or old['cost_status'] != 'unmetered' or old['state'] == 'NOT_SENT':
                raise BudgetError('unmetered_call_not_registered')
            payload = json.loads(old['metadata'])
            if any(key in payload and payload[key] != value for key, value in metadata.items()):
                raise BudgetError('unmetered_completion_cannot_rewrite_identity')
            payload.update(metadata, outcome_status='unmetered_outcome_unknown' if outcome_unknown else 'response_received')
            db.execute("UPDATE budget_calls SET state='SETTLED',upper_micro=NULL,metadata=?,completed_at=? WHERE call_id=?",
                       (json.dumps(payload, ensure_ascii=False), utc_now(), call_id))
        return self.get_call(call_id)

    def mark_started(self, call_id):
        with self._transaction() as db:
            row = db.execute("SELECT * FROM budget_calls WHERE call_id=?", (call_id,)).fetchone()
            if row is None:
                raise BudgetError("call_not_reserved")
            if row["state"] != "RESERVED":
                raise BudgetError("call_already_sent_or_completed")
            db.execute("UPDATE budget_calls SET state='IN_FLIGHT',started_at=? WHERE call_id=?", (utc_now(), call_id))
        return self.get_call(call_id)

    def mark_not_sent(self, call_id):
        with self._transaction() as db:
            row = db.execute("SELECT * FROM budget_calls WHERE call_id=?", (call_id,)).fetchone()
            if row is None or row["state"] != "RESERVED":
                raise BudgetError("cannot_release_potentially_sent_call")
            db.execute("UPDATE budget_calls SET state='NOT_SENT',reserved_micro=0,lower_micro=0,upper_micro=0,completed_at=? WHERE call_id=?", (utc_now(), call_id))
        return self.get_call(call_id)

    def settle(self, call_id, lower_cny, upper_cny, status, **metadata):
        if status not in {"measured_invoice", "usage_calculated", "bounded_estimate", "unknown"}:
            raise ValueError("invalid_cost_status")
        lower = to_micro(lower_cny, upper=False)
        upper = None if upper_cny is None else to_micro(upper_cny)
        if upper is not None and lower > upper:
            raise ValueError("invalid_cost_range")
        if status != "unknown" and upper is None:
            raise ValueError("known_cost_requires_upper")
        if status=="measured_invoice" and Decimal(str(lower_cny))!=Decimal(str(upper_cny)):
            raise ValueError("invoice_requires_exact_amount")
        with self._transaction() as db:
            old = db.execute("SELECT * FROM budget_calls WHERE call_id=?", (call_id,)).fetchone()
            if old is None or old["state"] == "NOT_SENT":
                raise BudgetError("unadmitted_call")
            if old["state"] == "SETTLED":
                if old["lower_micro"] != lower or old["upper_micro"] != upper or old["cost_status"] != status:
                    raise BudgetError("settlement_conflict")
                return self._call(old)
            # Observed overrun is retained honestly and blocks later calls; accounting
            # never discards a real bill merely because the original bound was wrong.
            payload = json.loads(old["metadata"])
            immutable={"campaign_id","run_id","stage","task_id","attempt_id","attempt",
                "model_requested","thinking","effort","prompt_hash","prompt_manifest",
                "price_snapshot_id","price_snapshot_hash","price_snapshot_path","parent_call_id","tool_call_id"}
            if any(key in metadata and key in payload and metadata[key]!=payload[key] for key in immutable):
                raise BudgetError("settlement_cannot_rewrite_request_identity")
            payload.update(metadata)
            if upper is not None and upper > old["admitted_micro"]:
                payload["admission_bound_exceeded"] = True
            unknown = status == "unknown"
            reservation = max(old["admitted_micro"], upper or 0) if unknown else 0
            db.execute("""UPDATE budget_calls SET lower_micro=?,upper_micro=?,reserved_micro=?,
                state=?,cost_status=?,metadata=?,completed_at=? WHERE call_id=?""",
                (lower, upper, reservation, "UNKNOWN" if unknown else "SETTLED", status,
                 json.dumps(payload, ensure_ascii=False), utc_now(), call_id))
        return self.get_call(call_id)

    def add_budget(self, account_id, amount_cny, reason):
        if not str(reason).strip():
            raise ValueError("authorization_reason_required")
        added = to_micro(amount_cny)
        with self._transaction() as db:
            account = db.execute("SELECT * FROM budget_accounts WHERE account_id=?", (account_id,)).fetchone()
            if account is None:
                raise BudgetError("account_missing")
            new_limit = account["limit_micro"] + added
            if account["parent_id"]:
                parent = db.execute("SELECT limit_micro FROM budget_accounts WHERE account_id=?", (account["parent_id"],)).fetchone()
                if new_limit > parent["limit_micro"]:
                    raise BudgetError("child_limit_exceeds_parent_authorization")
            db.execute("UPDATE budget_accounts SET limit_micro=? WHERE account_id=?", (new_limit, account_id))
            db.execute("INSERT INTO budget_authorizations(account_id,added_micro,reason,created_at) VALUES (?,?,?,?)", (account_id, added, reason, utc_now()))
        return self.summary(account_id)

    def list_calls(self, account_id=None):
        with self._connect() as db:
            if account_id is None:
                rows = db.execute("SELECT * FROM budget_calls ORDER BY created_at,call_id").fetchall()
            else:
                rows = db.execute("""WITH RECURSIVE descendants(id) AS
                    (SELECT ? UNION ALL SELECT account_id FROM budget_accounts a JOIN descendants d ON a.parent_id=d.id)
                    SELECT * FROM budget_calls WHERE account_id IN (SELECT id FROM descendants) ORDER BY created_at,call_id""", (account_id,)).fetchall()
        return [self._call(r) for r in rows]
