"""Versioned CNY pricing; provider context limits bound admission without token guesses."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx


@dataclass(frozen=True)
class CostRange:
    lower: Decimal
    upper: Decimal
    status: str


class PriceBook:
    def __init__(self, path: str | Path):
        self._load(Path(path).read_bytes())

    @classmethod
    def from_bytes(cls, raw: bytes) -> 'PriceBook':
        book = cls.__new__(cls)
        book._load(raw)
        return book

    def _load(self, raw: bytes):
        self.raw = raw
        self.snapshot = json.loads(raw)
        self.snapshot_id = self.snapshot['snapshot_id']
        self.content_hash = hashlib.sha256(raw).hexdigest()
        if self.snapshot['currency'] != 'CNY':
            raise ValueError('PRICE_CURRENCY')

    def model(self, name: str) -> dict:
        if name not in self.snapshot['models']:
            raise ValueError('MODEL_NOT_ALLOWED')
        return self.snapshot['models'][name]

    async def verify_online(self) -> dict:
        """Observe the current official page without changing selected prices."""
        result = {'status': 'unavailable', 'checked_at': datetime.now(UTC).isoformat(),
                  'source_url': self.snapshot['source_url'], 'http_status': None,
                  'expected_html_sha256': self.snapshot.get('source_html_sha256'),
                  'actual_html_sha256': None, 'snapshot_id': self.snapshot_id,
                  'snapshot_hash': self.content_hash, 'warning': None}
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(result['source_url'])
            result['http_status'] = response.status_code
            response.raise_for_status()
            result['actual_html_sha256'] = hashlib.sha256(response.content).hexdigest()
            result['status'] = ('unchanged' if result['actual_html_sha256'] == result['expected_html_sha256']
                                else 'changed')
            if result['status'] == 'changed':
                result['warning'] = 'OFFICIAL_PAGE_CHANGED_REVIEW_SELECTED_CNY_SNAPSHOT'
        except httpx.HTTPError as exc:
            result['warning'] = 'OFFICIAL_PRICE_RECHECK_UNAVAILABLE:' + type(exc).__name__
        return result

    def maximum_output(self, model: str) -> int:
        return self.model(model)['max_output_tokens']

    @staticmethod
    def period(at: datetime) -> str:
        if at.tzinfo is None:
            raise ValueError('TIMEZONE_REQUIRED')
        local = at.astimezone(ZoneInfo('Asia/Shanghai'))
        minute = local.hour * 60 + local.minute
        return 'peak' if local.weekday() < 5 and (540 <= minute < 720 or 840 <= minute < 1080) else 'off_peak'

    def rates(self, model: str, period: str) -> dict[str, Decimal]:
        return {k: Decimal(v) for k, v in self.model(model)['prices'][period].items()}

    def admission_bound(self, model: str) -> Decimal:
        """Maximize p*input + q*output subject to input+output<=context.

        q >= p, output<=max_output. No assumption about serialization/tokenizer
        overhead or cache hit rate is needed. Peak rates cover arbitrarily long
        responses and undocumented peak-boundary billing conventions.
        """
        m = self.model(model)
        r = self.rates(model, 'peak')
        if r['output'] < r['miss'] or m['context_tokens'] < m['max_output_tokens']:
            raise ValueError('PRICE_BOUND_INVALID')
        return (Decimal(m['context_tokens']) * r['miss'] +
                Decimal(m['max_output_tokens']) * (r['output'] - r['miss'])) / Decimal(1000000)

    def cost(self, model: str, usage: dict | None, started: datetime, completed: datetime) -> CostRange:
        if not usage or usage.get('prompt_tokens') is None or usage.get('completion_tokens') is None:
            return CostRange(Decimal(0), self.admission_bound(model), 'bounded_estimate')
        prompt, completion = usage['prompt_tokens'], usage['completion_tokens']
        if any(type(v) is not int or v < 0 for v in (prompt, completion)):
            raise ValueError('USAGE_INVALID')
        hit, miss = usage.get('prompt_cache_hit_tokens'), usage.get('prompt_cache_miss_tokens')
        known_cache = hit is not None and miss is not None
        if known_cache and (type(hit) is not int or type(miss) is not int or min(hit, miss) < 0 or hit + miss != prompt):
            raise ValueError('CACHE_USAGE_INVALID')
        # Every crossed minute is checked because the provider does not document
        # whether request start, completion, or token emission selects the tariff.
        periods = {self.period(started), self.period(completed)}
        tick = started
        while tick < completed and len(periods) < 2:
            periods.add(self.period(tick))
            tick += timedelta(minutes=1)
        bounds = []
        for period in periods:
            r = self.rates(model, period)
            low_in = hit*r['hit'] + miss*r['miss'] if known_cache else prompt*r['hit']
            high_in = low_in if known_cache else prompt*r['miss']
            # reasoning_tokens are a subset of completion_tokens, never added.
            bounds.append(((low_in + completion*r['output']) / Decimal(1000000),
                           (high_in + completion*r['output']) / Decimal(1000000)))
        return CostRange(min(x[0] for x in bounds), max(x[1] for x in bounds),
                         'usage_calculated' if known_cache else 'bounded_estimate')
