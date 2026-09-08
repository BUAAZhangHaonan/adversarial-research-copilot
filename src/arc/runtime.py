"""One model protocol, one admission boundary, durable role/tool checkpoints."""
from __future__ import annotations

import asyncio
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version as package_version
import platform
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Awaitable, Callable
from uuid import uuid4

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from .mcp_client import ToolArgumentError, model_schema, validate_arguments
from .pricing import PriceBook
from .budget import BudgetExceeded
from .validation import output_validation_errors


def encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def digest(value) -> str:
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def correction_counts(state):
    """Read old checkpoints without granting another use of an exhausted category."""
    if 'repair_counts' in state:
        return dict(state['repair_counts'])
    tool_used = bool(state.get('tool_correction') or state.get('repair_kind') == 'tool_arguments')
    json_used = bool(state.get('repair_snapshot_path') or
                     (state.get('repair_count') and not tool_used))
    return {'tool_arguments': int(tool_used), 'output_json': int(json_used)}


def spend_correction(state, kind):
    counts = correction_counts(state)
    if counts[kind]:
        raise ValueError('CORRECTION_CATEGORY_EXHAUSTED')
    counts[kind] = 1
    state['repair_counts'] = counts
    state['repair_count'] = sum(counts.values())
    state['repair_kind'] = kind


def derive_investigator_searches(envelope, tool_trace):
    """Derive execution facts without changing the model's research fields."""
    from .schemas import InvestigatorResult, SearchTrace
    if not isinstance(envelope.result, InvestigatorResult):
        return envelope
    searches = []
    for trace in tool_trace:
        if trace.get('status') != 'completed' or trace.get('name') not in {'search_web', 'search_literature'}:
            continue
        if trace.get('task_id') != envelope.task_id or trace.get('run_id') != envelope.subject.run_id:
            raise ValueError('SEARCH_TRACE_TASK_MISMATCH')
        arguments = trace['arguments']
        searches.append(SearchTrace(trace_id=trace['call_id'], operation=trace['name'],
            query=arguments.get('query', arguments.get('theme_document', arguments.get('url'))),
            source_ids=trace['source_ids']))
    if len({search.trace_id for search in searches}) != len(searches):
        raise ValueError('DUPLICATE_SEARCH_TRACE_ID')
    derived = envelope.model_copy(deep=True)
    derived.result.actual_searches = searches
    return derived


EVIDENCE_REF_KEYS = frozenset({'evidence_id', 'evidence_ids', 'new_evidence_ids', 'anchor_evidence_ids',
    'trigger_evidence_ids', 'decisive_evidence_ids', 'basis_evidence_ids'})
SOURCE_REF_KEYS = frozenset({'source_id', 'source_ids', 'target_source_ids', 'original_sources_revisited'})


def reference_ids(value, keys) -> set[str]:
    if isinstance(value, BaseModel): value = value.model_dump(mode='json')
    if isinstance(value, (list, tuple)): return set().union(*(reference_ids(item, keys) for item in value))
    if not isinstance(value, dict): return set()
    found = set()
    for key, item in value.items():
        if key in keys and item is not None:
            ids = item if isinstance(item, list) else [item]
            if any(not isinstance(identifier, str) for identifier in ids):
                raise ValueError('REFERENCE_ID_NOT_STRING')
            found.update(ids)
        elif isinstance(item, (list, tuple, dict, BaseModel)):
            found.update(reference_ids(item, keys))
    return found


def environment_snapshot() -> dict:
    packages = {}
    for name in ('adversarial-research-copilot', 'openai', 'mcp', 'pydantic', 'httpx', 'anyio',
                 'jsonschema', 'Jinja2', 'tzdata'):
        try: packages[name] = package_version(name)
        except PackageNotFoundError: packages[name] = None
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
            'platform': sys.platform, 'packages': packages}


class RuntimePaused(RuntimeError):
    def __init__(self, status: str, reason: str):
        self.status, self.reason = status, reason
        super().__init__(reason)


@dataclass(frozen=True)
class BoundTool:
    name: str
    parameters: dict
    handler: Callable[[dict, dict], Awaitable[dict]]
    cost_upper_cny: Decimal | None
    cost_basis: str
    service: str = 'local'
    persists_raw_response: bool = False


def web_text_representation(body: dict, arguments: dict) -> dict:
    """Decode the audited fetch_page protocol, including its explicit trailer."""
    text = body.get('text') or ''
    limit = arguments.get('max_chars', 4000)
    if type(limit) is not int or limit < 1:
        raise ValueError('WEB_READ_LIMIT_INVALID')
    total, complete = len(text), True
    if len(text) > limit:
        trailer = re.fullmatch(r'\n\.\.\.\[truncated (\d+) chars\]', text[limit:])
        if trailer is None or int(trailer.group(1)) <= limit:
            raise ValueError('WEB_READ_TRUNCATION_PROTOCOL_INVALID')
        total, complete, text = int(trailer.group(1)), False, text[:limit]
    resource = body.get('resource') or {}
    identity = resource.get('content_hash')
    extractor = body.get('extractor') or resource.get('extractor')
    return {'content': text, 'content_complete': complete, 'content_total_chars': total,
            'representation_id': f'webresearch:{extractor}:{identity}' if identity and extractor else None}


def build_tools(store, hub=None) -> dict[str, BoundTool]:
    """Bind audited operations; keep original text in the source registry."""
    from .schemas import CapabilityRequest, SourceRecord
    tools = {}

    async def read_record(arguments, metadata):
        from .store import StateError
        try:
            record = store.get_record(arguments['record_id'], version=arguments.get('version'),
                                      run_id=metadata.get('run_id'))
        except StateError as exc:
            if str(exc) not in {'record_missing', 'record_ambiguous_requires_run_id'}:
                raise
            return {'is_error': True, 'error': str(exc), 'record_id': arguments['record_id']}
        if record is None: return {'is_error': True, 'error': 'RECORD_NOT_FOUND'}
        result = dict(record)
        content = result.pop('content', None)
        if content is not None:
            offset, limit = arguments.get('offset', 0), arguments.get('limit', 12000)
            more_cached = offset + limit < len(content)
            result.update(content=content[offset:offset+limit], content_offset=offset,
                          cached_content_chars=len(content), more_cached_content=more_cached,
                          requires_source_fetch=result.get('content_complete') is False and not more_cached)
            if offset >= len(content):
                result.update(is_error=True,
                    error='SOURCE_CACHE_EXHAUSTED' if result.get('content_complete') is False else 'SOURCE_END_REACHED',
                    cached_range_start=0, cached_range_end=len(content), next_cached_offset=None)
        elif 'source_type' in result and 'access_status' in result:
            # Search metadata can be opened as metadata, but it is never a body.
            # Old records may have defaulted content_complete to true without text.
            result.update(content=None, content_complete=False, cached_content_chars=0,
                          more_cached_content=False, requires_source_fetch=True)
        return result
    tools['read_record'] = BoundTool('read_record', {'type': 'object', 'properties': {
        'record_id': {'type': 'string'}, 'version': {'type': ['integer', 'null'], 'minimum': 1},
        'offset': {'type': 'integer', 'minimum': 0}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 64000}},
        'required': ['record_id'], 'additionalProperties': False}, read_record, Decimal(0), 'LOCAL_SQLITE_READ')

    async def request_capability(arguments, metadata):
        identifier = store.save_capability_request(metadata['run_id'], arguments,
            task_id=metadata['task_id'],
            request_key=metadata['parent_call_id'] + ':' + metadata['tool_call_id'])
        return {'recorded': True, 'request_id': identifier, 'capability_available': False,
                'status': 'pending_user_review', 'execution_authorized': False}
    tools['request_capability'] = BoundTool('request_capability', CapabilityRequest.model_json_schema(),
        request_capability, Decimal(0), 'LOCAL_REQUIREMENTS_ARTIFACT')

    async def lookup_archive(arguments, metadata):
        return store.lookup_archive(arguments['query'], limit=arguments.get('limit', 8), offset=arguments.get('offset', 0))
    tools['lookup_archive'] = BoundTool('lookup_archive', {'type': 'object', 'properties': {
        'query': {'type': 'string'}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 8},
        'offset': {'type': 'integer', 'minimum': 0}}, 'required': ['query'], 'additionalProperties': False},
        lookup_archive, Decimal(0), 'LOCAL_SQLITE_ARCHIVE')

    if hub is None: return tools
    for name, cap in hub.capabilities.items():
        async def execute(arguments, metadata, name=name, cap=cap):
            raw_path = metadata['raw_response_artifact_path']
            try:
                response = json.loads(store.read_artifact(raw_path))
            except FileNotFoundError:
                response = await hub.call(name, arguments)
                # Persist the remote result before any JSON decoding or registry
                # work. A local processing failure must not repeat this call.
                store.save_artifact(raw_path, encoded(response))
            if response['is_error']: return response
            body = response.get('structured_content')
            if isinstance(body, dict) and set(body) == {'result'}: body = body['result']
            if body is None:
                texts = [b['text'] for b in response['content'] if b.get('type') == 'text']
                body = '\n'.join(texts)
            if isinstance(body, str):
                try: body = json.loads(body)
                except ValueError:
                    return {'is_error': True, 'error': 'MCP_RESULT_NOT_JSON', 'content': body}
            if not isinstance(body, dict) or body.get('error') or body.get('status') in {'failed', 'error'}:
                return {'is_error': True, 'error': 'MCP_OPERATION_FAILED', 'data': body}
            source_ids, registered = [], []
            if name == 'read_paper':
                paper = dict(body.get('paper') or {})
                text = body.get('markdown')
                identity = paper.get('versioned_id') or paper.get('arxiv_id')
                if not (paper.get('title') or '').strip():
                    if (isinstance(text, str) and text.strip() and isinstance(identity, str)
                            and re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-zA-Z][a-zA-Z.\-]*/\d{7})v[1-9]\d*', identity)):
                        paper['title'] = 'arXiv ' + identity
                    else:
                        return {'is_error': True, 'error': 'MCP_SOURCE_METADATA_INCOMPLETE',
                                'missing': ['title_or_versioned_arxiv_identity_with_body'],
                                'raw_artifact_path': raw_path}
                items = [{**paper, 'content': text, 'origin': cap.origin,
                          'representation_id': f'{cap.service}:{cap.method}:markdown'}]
            elif name == 'read_web':
                items = [{**body, **web_text_representation(body, arguments), 'origin': cap.origin}]
            else:
                raw_items = body.get('papers', body.get('results', []))
                if not isinstance(raw_items, list) or any(not isinstance(item, dict) for item in raw_items):
                    return {'is_error': True, 'error': 'MCP_RESULT_ITEMS_INVALID', 'raw_artifact_path': raw_path}
                items = [{**item, 'origin': 'metadata'} for item in raw_items]
            for item in items:
                arxiv_id = item.get('versioned_id') or item.get('arxiv_id')
                url = item.get('url') or item.get('canonical_url')
                if not url and arxiv_id: url = 'https://arxiv.org/abs/' + arxiv_id
                if not url or not item.get('title'):
                    if name == 'read_paper':
                        return {'is_error': True, 'error': 'MCP_SOURCE_METADATA_INCOMPLETE',
                                'missing': ['source_identity' if not url else 'title'],
                                'raw_artifact_path': raw_path}
                    continue
                origin = item['origin']
                text = item.get('content')
                source = store.register_source(SourceRecord(title=item['title'], url=url, arxiv_id=arxiv_id,
                    doi=item.get('doi'), version=None,
                    source_type='paper' if name in {'read_paper', 'search_literature'} else 'web_unclassified',
                    access_status='retrieved' if text else 'metadata_only', content_origin=origin,
                    content_complete=item.get('content_complete', bool(text)),
                    content_total_chars=item.get('content_total_chars', len(text) if text else None),
                    representation_id=item.get('representation_id')), content=text)
                source_ids.append(source.source_id)
                registered.append({'source_id': source.source_id, 'title': source.title, 'url': source.url,
                    'canonical_id': source.canonical_id, 'version': source.version,
                    'representation_id': source.representation_id,
                    'content_origin': origin, 'abstract': item.get('abstract'), 'snippet': item.get('snippet'),
                    'content_chars': len(text) if text else 0,
                    'content_complete': item.get('content_complete', bool(text)),
                    'content_total_chars': item.get('content_total_chars', len(text) if text else None),
                    'registered_content_complete': source.content_complete,
                    'content': text if text and len(text) <= 12000 else None,
                    'content_requires_read_record': bool(text and len(text) > 12000)})
            return {'is_error': False, 'source_ids': source_ids, 'sources': registered,
                    'service': cap.service, 'method': cap.method, 'origin': cap.origin,
                    'raw_artifact_path': raw_path, 'errors': body.get('errors', []),
                    'status': body.get('status')}
        tools[name] = BoundTool(name, cap.parameters, execute, cap.cost_upper_cny, cap.cost_basis, cap.service, True)
    return tools


class Runtime:
    def __init__(self, *, store, ledger, account_id: str, loader, role_models: dict[str, str],
                 prices: PriceBook, client=None, api_key=None, base_url='https://api.deepseek.com',
                 tools: dict[str, BoundTool] | None = None, timeout_seconds=1800, on_progress=None):
        self.store, self.ledger, self.account_id = store, ledger, account_id
        self.loader, self.role_models, self.prices = loader, role_models, prices
        self.client = client or AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0,
                                          timeout=timeout_seconds)
        if getattr(self.client, 'max_retries', 0) != 0:
            raise ValueError('SDK_RETRIES_MUST_BE_ZERO')
        self.tools = tools or {}
        self.on_progress = on_progress
        self._lock = asyncio.Lock()

    def _progress(self, record, status):
        if self.on_progress:
            self.on_progress({'task_id': record.task_id, 'run_id': record.run_id, 'status': status,
                              'budget': self.ledger.summary(self.account_id)})

    async def close(self):
        await self.client.close()

    def _checkpoint(self, record, state, status=None):
        path = f'runs/{record.run_id}/tasks/{digest(record.task_id)}/states/{uuid4().hex}.json'
        self.store.save_artifact(path, encoded(state))
        record.response_artifact_path = path
        if status is not None: record.status = status
        self.store.put_task(record)

    def tool_trace(self, task_id: str) -> list[dict]:
        record = self.store.get_task(task_id)
        if not record or not record.response_artifact_path: return []
        return json.loads(self.store.read_artifact(record.response_artifact_path)).get('tool_trace', [])

    def _load_prompt_snapshot(self, record, state=None):
        from .prompting import RenderedPrompt
        try:
            snapshot = RenderedPrompt.from_snapshot(json.loads(self.store.read_artifact(record.rendered_prompt_path)))
            if snapshot.prompt_hash != record.prompt_hash or snapshot.source_hashes != record.prompt_manifest:
                raise ValueError('TASK_PROMPT_SNAPSHOT_HASH_MISMATCH')
            if state is not None:
                active = snapshot
                if state.get('repair_snapshot_path'):
                    active = RenderedPrompt.from_snapshot(json.loads(self.store.read_artifact(state['repair_snapshot_path'])))
                    if active.source_hashes != snapshot.source_hashes or active.sources != snapshot.sources:
                        raise ValueError('REPAIR_SNAPSHOT_SOURCE_MISMATCH')
                if active.prompt_hash != state['prompt_hash'] or state['messages'][:2] != active.messages:
                    raise ValueError('TASK_PROMPT_HISTORY_MISMATCH')
            return snapshot
        except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
            raise RuntimePaused('PAUSED_PROTOCOL', str(exc)) from exc

    def _validate_output_reference_targets(self, envelope, payload, state):
        """Read-only address diagnostics; no citation replacement or evidence writes."""
        from .store import StateError
        visible = {kind: reference_ids([payload, state.get('tool_trace', [])], keys)
                   for kind, keys in [('source', SOURCE_REF_KEYS), ('evidence', EVIDENCE_REF_KEYS)]}
        errors = []
        checked = {}

        def walk(value, path=()):
            if isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, path + (index,))
            elif isinstance(value, dict):
                for key, item in value.items():
                    kind = 'source' if key in SOURCE_REF_KEYS else 'evidence' if key in EVIDENCE_REF_KEYS else None
                    if kind is None:
                        walk(item, path + (key,))
                        continue
                    if item is None:
                        continue
                    entries = enumerate(item) if isinstance(item, list) else [(None, item)]
                    for index, identifier in entries:
                        loc = path + (key,) + ((index,) if index is not None else ())
                        reason = None
                        if not isinstance(identifier, str):
                            reason = 'REFERENCE_ID_NOT_STRING'
                        else:
                            address = (kind, identifier)
                            if address not in checked:
                                try:
                                    self.store.validate_references({kind + '_id': identifier})
                                except StateError as exc:
                                    checked[address] = str(exc)
                                else:
                                    checked[address] = None
                            reason = checked[address]
                            if reason is None and identifier not in visible[kind]:
                                reason = 'reference_not_supplied_to_task'
                        if reason:
                            errors.append({'loc': list(loc), 'type': reason, 'supplied': identifier,
                                           'visible_candidates': sorted(visible[kind])})
        walk(envelope.model_dump(mode='json'))
        if errors:
            raise ValueError('OUTPUT_REFERENCE_INVALID; ' + json.dumps(errors, ensure_ascii=False))

    def _validate_evidence_request_targets(self, envelope, payload):
        """Pure claim/issue/draw addressing; no source checks or registry writes."""
        from .schemas import ModeratorResult, ComposeResult, ConceptionResult
        from .store import StateError
        for field in ('claim_id', 'issue_id', 'draw_id'):
            visible = reference_ids(payload, {field, field + 's'})
            if field == 'claim_id' and isinstance(envelope.result, (ComposeResult, ConceptionResult)):
                candidate = envelope.result.card_candidate
                if candidate is not None:
                    visible.update(claim.claim_id for claim in candidate.claims)
            if field == 'issue_id' and isinstance(envelope.result, ModeratorResult):
                # A completed moderator may create an issue and request evidence
                # for it in the same ruling. Store gates still validate the issue
                # transitions and claim version before executing the retrieval.
                current_claims = reference_ids(payload, {'claim_id', 'claim_ids'})
                declared = {issue.issue_id: issue for issue in envelope.result.updated_issues
                            if issue.claim_id in current_claims}
                for index, request in enumerate(envelope.evidence_requests):
                    issue = declared.get(request.issue_id)
                    if issue is not None and request.claim_id not in (None, issue.claim_id):
                        raise StateError('evidence_request_issue_claim_mismatch; ' + json.dumps({
                            'loc': ['evidence_requests', index, 'claim_id'],
                            'expected': [issue.claim_id], 'supplied': request.claim_id}))
                visible.update(declared)
            for index, request in enumerate(envelope.evidence_requests):
                target = getattr(request, field)
                if target and target not in visible:
                    raise StateError(f'evidence_request_{field}_not_supplied_to_task; ' + json.dumps({
                        'loc': ['evidence_requests', index, field],
                        'expected': sorted(visible), 'supplied': target}))

    def _validate_semantics(self, envelope, payload, state):
        from .schemas import InvestigatorResult, ModeratorResult, ComposeResult, ConceptionResult
        from .store import StateError
        from .validation import validate_role_targets
        validate_role_targets(envelope, payload)
        research_references = envelope.model_dump(mode='json')
        if isinstance(envelope.result, InvestigatorResult):
            # Search hits are an ordered execution log, so repeated hits remain
            # valid. Research citation lists retain the store's uniqueness rule.
            research_references['result'].pop('actual_searches')
            for search in envelope.result.actual_searches:
                for source_id in search.source_ids:
                    self.store.validate_references({'source_id': source_id})
        self.store.validate_references(research_references)
        keys = EVIDENCE_REF_KEYS | SOURCE_REF_KEYS
        if reference_ids(envelope, keys) - reference_ids([payload, state['tool_trace']], keys):
            raise StateError('reference_not_supplied_to_task')
        self._validate_evidence_request_targets(envelope, payload)
        findings = (getattr(envelope.result, 'findings', []) + getattr(envelope.result, 'contrary_findings', [])
                    if envelope.result is not None else [])
        self.store.validate_finding_sources(findings)
        targeted = [finding for finding in findings if getattr(finding, 'claim_id', None) is not None]
        if targeted:
            claims = list(payload.get('claims', []))
            card = payload.get('card')
            if card:
                subject = envelope.subject
                if (card.get('card_id'), card.get('version')) != (subject.card_id, subject.card_version):
                    raise StateError('finding_target_card_not_current_subject')
                claims.extend(card.get('draft', {}).get('claims', []))
            visible_claims = {(claim['claim_id'], claim['version']) for claim in claims}
            for finding in targeted:
                if (finding.claim_id, finding.claim_version) not in visible_claims:
                    raise StateError('finding_target_claim_not_supplied_to_task')
        searches = getattr(envelope.result, 'actual_searches', []) if envelope.result is not None else []
        traces = {trace['call_id']: trace for trace in state['tool_trace']}
        if envelope.result is not None and hasattr(envelope.result, 'actual_searches'):
            expected = {trace['call_id'] for trace in state['tool_trace']
                        if trace['status'] == 'completed' and trace['name'] in {'search_literature', 'search_web'}}
            declared = [search.trace_id for search in searches]
            if len(declared) != len(set(declared)) or set(declared) != expected:
                raise StateError('actual_searches_incomplete_or_duplicate')
        for search in searches:
            trace = traces.get(search.trace_id)
            if trace is None or trace['status'] != 'completed' or search.operation != trace['name']:
                raise StateError('actual_search_not_in_trace')
            query = trace['arguments'].get('query', trace['arguments'].get('theme_document', trace['arguments'].get('url')))
            if search.query != query or set(search.source_ids) != set(trace['source_ids']):
                raise StateError('actual_search_trace_mismatch')

    def _normalize_search_provenance(self, envelope, record, state):
        from .schemas import InvestigatorResult, ModeratorResult, ComposeResult
        if not isinstance(envelope.result, InvestigatorResult):
            return envelope
        derived = derive_investigator_searches(envelope, state['tool_trace'])
        before = envelope.model_dump(mode='json')
        after = derived.model_dump(mode='json')
        original_searches = before['result'].pop('actual_searches')
        actual_searches = after['result'].pop('actual_searches')
        before_hash, after_hash = digest(before), digest(after)
        if before_hash != after_hash:
            raise ValueError('SEARCH_NORMALIZATION_CHANGED_RESEARCH_FIELDS')
        previous = state.get('actual_searches_provenance')
        if original_searches == actual_searches and previous:
            saved = json.loads(self.store.read_artifact(previous['audit_path']))
            if digest(saved) != previous['audit_hash']:
                raise ValueError('SEARCH_NORMALIZATION_AUDIT_HASH_MISMATCH')
            if saved['authoritative_trace_hash'] != digest(state['tool_trace']) or saved['research_fields_after_hash'] != after_hash:
                raise ValueError('SEARCH_NORMALIZATION_DEPENDENCY_CHANGED')
            return derived
        response = state.get('response') or {}
        audit = {'kind': 'runtime_actual_searches_from_task_trace_v1',
            'task_id': record.task_id, 'run_id': record.run_id,
            'prior_task_status': record.status, 'prior_error': record.error,
            'input_state_artifact_path': record.response_artifact_path,
            'response_call_id': response.get('call_id'),
            'raw_content_hash': digest(response.get('message', {}).get('content')),
            'original_model_declaration': original_searches,
            'authoritative_actual_searches': actual_searches,
            'authoritative_trace_hash': digest(state['tool_trace']),
            'authoritative_trace': [{key: trace.get(key) for key in
                ('task_id', 'run_id', 'call_id', 'parent_call_id', 'name', 'status', 'arguments',
                 'source_ids', 'raw_response_artifact_path')} for trace in state['tool_trace']],
            'research_fields_before_hash': before_hash, 'research_fields_after_hash': after_hash}
        audit_hash = digest(audit)
        path = f'runs/{record.run_id}/tasks/{digest(record.task_id)}/normalizations/{audit_hash}.json'
        try:
            existing = self.store.read_artifact(path)
        except FileNotFoundError:
            self.store.save_artifact(path, encoded(audit))
        else:
            if existing != encoded(audit):
                raise ValueError('SEARCH_NORMALIZATION_AUDIT_CHANGED')
        # New acceptance checkpoints this provenance. Cached acceptance returns
        # a derived view and independent audit without rewriting its TaskRecord.
        state['actual_searches_provenance'] = {'source': audit['kind'], 'audit_path': path, 'audit_hash': audit_hash}
        return derived

    async def invoke(self, role: str, task: str, payload: dict, result_schema: type[BaseModel],
                     subject, task_id: str, tool_profile: list[str] | None = None,
                     on_admitted: Callable | None = None):
        async with self._lock:
            try:
                return await self._invoke(role, task, payload, result_schema, subject, task_id,
                                          tool_profile, on_admitted)
            except BudgetExceeded as exc:
                raise RuntimePaused('PAUSED_BUDGET', 'budget_not_admitted') from exc

    async def _invoke(self, role, task, payload, result_schema, subject, task_id, tool_profile, on_admitted):
        from .schemas import Envelope, TaskRecord
        envelope_type = Envelope[result_schema]
        subject_data = subject.model_dump(mode='json') if isinstance(subject, BaseModel) else subject
        model = self.role_models[role]
        self.prices.model(model)
        profile = sorted(tool_profile or [])
        if set(profile) - self.tools.keys():
            raise RuntimePaused('PAUSED_EXTERNAL', 'TOOL_PROFILE_UNAVAILABLE')
        record = self.store.get_task(task_id)
        state = json.loads(self.store.read_artifact(record.response_artifact_path)) if record else None
        if state:
            self._load_prompt_snapshot(record, state)
            if record.environment_snapshot_path:
                saved_environment = self.store.read_artifact(record.environment_snapshot_path)
                if hashlib.sha256(saved_environment.encode()).hexdigest() != record.environment_snapshot_hash:
                    raise RuntimePaused('PAUSED_PROTOCOL', 'ENVIRONMENT_SNAPSHOT_HASH_MISMATCH')
                if json.loads(saved_environment) != environment_snapshot():
                    raise RuntimePaused('PAUSED_PROTOCOL', 'DEPENDENCY_ENVIRONMENT_CHANGED_FORK_REQUIRED')
            functions = state['original_tools']
            if [item['function']['name'] for item in functions] != profile:
                raise RuntimePaused('PAUSED_PROTOCOL', 'TOOL_PROFILE_CHANGED_FORK_REQUIRED')
            if any(item['function']['parameters'] != model_schema(self.tools[item['function']['name']].parameters)
                   for item in functions):
                raise RuntimePaused('PAUSED_PROTOCOL', 'TOOL_SCHEMA_CHANGED_FORK_REQUIRED')
        else:
            functions = [dict(type='function', function={
                'name': name, 'description': self.loader.tool_description(name),
                'parameters': model_schema(self.tools[name].parameters)}) for name in profile]
        config = {'model': model, 'reasoning_effort': 'max', 'thinking': {'type': 'enabled'},
                  'max_tokens': self.prices.maximum_output(model), 'tools': functions}
        input_hash = digest({'payload': payload, 'subject': subject_data, 'schema': envelope_type.model_json_schema()})
        data = {'task_id': task_id, 'subject': subject_data, 'payload': payload}
        if record:
            if record.input_hash != input_hash or record.model_config_hash != digest(config):
                raise RuntimePaused('PAUSED_PROTOCOL', 'TASK_DEPENDENCY_CHANGED_FORK_REQUIRED')
            # reserve is durable before task checkpoint or callbacks. RESERVED
            # proves mark_started has not happened, so process-loss orphans can
            # be released; IN_FLIGHT/UNKNOWN are never inferred to be unsent.
            reconciled = False
            for admission in self.ledger.list_calls(self.account_id):
                if admission['task_id'] == task_id and admission['state'] == 'RESERVED':
                    self.ledger.mark_not_sent(admission['call_id'])
                    for pending in ('pending_model', 'pending_tool'):
                        if state.get(pending) == admission['call_id']: state[pending] = None
                    reconciled = True
            if reconciled: self._checkpoint(record, state)
            if record.accepted_result is not None:
                accepted = envelope_type.model_validate(record.accepted_result)
                try:
                    accepted = self._normalize_search_provenance(accepted, record, state)
                    self._validate_semantics(accepted, payload, state)
                except (ValueError, RuntimeError) as exc:
                    # Preserve the historical accepted record, but do not reuse
                    # it when a current deterministic source check fails.
                    raise RuntimePaused('PAUSED_PROTOCOL', str(exc)) from exc
                return accepted
            if record.status == 'UNKNOWN':
                raise RuntimePaused('PAUSED_EXTERNAL', 'REMOTE_RESULT_UNKNOWN')
        else:
            try:
                input_evidence_ids = sorted(reference_ids(payload, EVIDENCE_REF_KEYS))
                self.store.validate_references({'evidence_ids': input_evidence_ids})
            except (ValueError, RuntimeError) as exc:
                raise RuntimePaused('PAUSED_PROTOCOL', str(exc)) from exc
            rendered = self.loader.render(f'{role}.{task}', data, schema=envelope_type.model_json_schema(), tool_profile=profile)
            record = TaskRecord(task_id=task_id, run_id=subject_data['run_id'], input_hash=input_hash,
                                prompt_hash=rendered.prompt_hash, model_config_hash=digest(config), model_id=model,
                                prompt_manifest=rendered.source_hashes,
                                evidence_ids=input_evidence_ids)
            prompt_path = f'runs/{record.run_id}/tasks/{digest(task_id)}/prompt.json'
            self.store.save_artifact(prompt_path, encoded(asdict(rendered)))
            record.rendered_prompt_path = prompt_path
            environment = encoded(environment_snapshot())
            record.environment_snapshot_path = f'runs/{record.run_id}/tasks/{digest(task_id)}/environment.json'
            record.environment_snapshot_hash = hashlib.sha256(environment.encode()).hexdigest()
            self.store.save_artifact(record.environment_snapshot_path, environment)
            state = {'messages': rendered.messages, 'calls': [], 'tool_trace': [], 'repair_count': 0,
                     'repair_counts': {'tool_arguments': 0, 'output_json': 0},
                     'pending_model': None, 'pending_tool': None, 'response': None, 'tools': functions,
                     'original_tools': functions,
                     'subject': subject_data, 'prompt_hash': rendered.prompt_hash,
                     'prompt_manifest': rendered.source_hashes}
            self._checkpoint(record, state)
        while True:
            if state.get('tool_correction_failure'):
                raise RuntimePaused('PAUSED_PROTOCOL', state['tool_correction_failure'])
            for trace in state['tool_trace']:
                ledger_call = self.ledger.get_call(trace['call_id'])
                if ledger_call['state'] != 'SETTLED':
                    bound = Decimal(ledger_call['admitted_micro']) / Decimal(1000000)
                    self.ledger.settle(trace['call_id'], '0', bound, 'bounded_estimate',
                        completed_at=trace['completed_at'], response_artifact_path=record.response_artifact_path)
            if state.get('response') is None:
                response = await self._model_request(record, state, config, on_admitted)
                state['response'] = response
                self._checkpoint(record, state, 'RESPONSE_SAVED')
            response = state['response']
            await self._settle_response(record, state, response)
            finish = response['finish_reason']
            if finish not in {'stop', 'tool_calls'}:
                record.error = 'INVALID_FINISH_REASON:' + str(finish)
                self._checkpoint(record, state, 'PAUSED_PROTOCOL')
                raise RuntimePaused('PAUSED_PROTOCOL', record.error)
            message = response['message']
            if finish == 'tool_calls':
                if not message.get('tool_calls') or not functions or state.get('repair_snapshot_path'):
                    raise RuntimePaused('PAUSED_PROTOCOL', 'UNEXPECTED_TOOL_CALLS')
                if not state.get('assistant_appended'):
                    state['messages'].append(message)
                    state['assistant_appended'] = True
                    self._checkpoint(record, state, 'RESPONSE_SAVED')
                self._prepare_tool_batch(record, state, message['tool_calls'], profile, response['call_id'])
                completed_ids = {t['tool_call_id'] for t in state['tool_trace']
                                 if t['parent_call_id'] == response['call_id']}
                rejected_ids = {t['tool_call_id'] for t in state.get('tool_rejections', [])
                                if t['parent_call_id'] == response['call_id']}
                correction = state.get('tool_correction')
                failures = ({item['tool_call_id']: item for item in correction['failures']}
                            if correction and correction['original_response_id'] == response['call_id'] else {})
                for tool_call in message['tool_calls']:
                    if tool_call['id'] in completed_ids or tool_call['id'] in rejected_ids: continue
                    if tool_call['id'] in failures:
                        rejected = {'status': 'rejected_before_execution',
                                    'parent_call_id': response['call_id'], **failures[tool_call['id']]}
                        state.setdefault('tool_rejections', []).append(rejected)
                        state['messages'].append({'role': 'tool', 'tool_call_id': tool_call['id'],
                                                  'content': encoded(rejected)})
                        self._checkpoint(record, state, 'RESPONSE_SAVED')
                        continue
                    await self._execute_tool(record, state, tool_call, profile, response['call_id'])
                if correction and correction['original_response_id'] == response['call_id']:
                    # The feedback and the request boundary become durable together.
                    state['messages'].append({'role': 'user', 'content': correction['instruction']})
                    correction['phase'] = 'awaiting'
                elif correction and correction.get('corrected_response_id') == response['call_id']:
                    correction['phase'] = 'completed'
                state['response'] = None
                state['assistant_appended'] = False
                self._checkpoint(record, state, 'PENDING')
                continue
            if message.get('tool_calls'):
                raise RuntimePaused('PAUSED_PROTOCOL', 'STOP_WITH_TOOL_CALLS')
            try:
                envelope = envelope_type.model_validate_json(message.get('content') or '')
                from .store import StateError
                self._validate_output_reference_targets(envelope, payload, state)
                try:
                    self._validate_evidence_request_targets(envelope, payload)
                except StateError as exc:
                    # Only addressing errors enter JSON correction; provenance
                    # and authorization remain in post-parse semantic checks.
                    raise ValueError(str(exc)) from exc
                from .scientific import validate_scientific_output_contract
                validate_scientific_output_contract(self.store, payload, envelope.result)
                from .schemas import LibrarianResult, EvaluatorResult
                from .validation import validate_archive_comparisons, validate_evaluator_coverage
                if isinstance(envelope.result, LibrarianResult):
                    validate_archive_comparisons(envelope.result, payload.get('records_to_compare', []), self.store)
                if isinstance(envelope.result, EvaluatorResult):
                    validate_evaluator_coverage(envelope.result, payload.get('candidates', []))
            except (ValueError, ValidationError) as exc:
                errors = (output_validation_errors(message.get('content') or '', envelope_type, exc)
                          if isinstance(exc, ValidationError) else [str(exc)])
                if correction_counts(state)['output_json']:
                    state['final_validation_errors'] = errors
                    record.error = 'INVALID_OUTPUT_AFTER_REPAIR'
                    self._checkpoint(record, state, 'PAUSED_PROTOCOL')
                    raise RuntimePaused('PAUSED_PROTOCOL', record.error) from exc
                # Rendered original system is authoritative on resume. Only the
                # registered repair task supplies additional behavior.
                snapshot = self._load_prompt_snapshot(record)
                repaired = self.loader.render_repair(snapshot, data, schema=envelope_type.model_json_schema(),
                    previous_response=message.get('content'), validation_errors=errors)
                state['messages'] = repaired.messages
                spend_correction(state, 'output_json')
                state['response'] = None
                state['tools'] = []
                state['prompt_hash'] = repaired.prompt_hash
                state['prompt_manifest'] = repaired.source_hashes
                repair_path = f'runs/{record.run_id}/tasks/{digest(task_id)}/repair.json'
                self.store.save_artifact(repair_path, encoded(asdict(repaired)))
                state['repair_snapshot_path'] = repair_path
                state['repair_validation_errors'] = errors
                self._checkpoint(record, state, 'PENDING')
                continue
            try:
                correction = state.get('tool_correction')
                if correction and correction['phase'] == 'awaiting':
                    if envelope.result_status != 'blocked' or not envelope.capability_requests:
                        self._pause_tool_correction(record, state, 'TOOL_CORRECTION_REQUIRED')
                    correction['phase'] = 'declined'
                if envelope.task_id != task_id or envelope.subject.model_dump(mode='json') != subject_data:
                    raise ValueError('SUBJECT_OR_TASK_MISMATCH')
                envelope = self._normalize_search_provenance(envelope, record, state)
                self._validate_semantics(envelope, payload, state)
            except ValueError as exc:
                record.error = str(exc)
                self._checkpoint(record, state, 'PAUSED_PROTOCOL')
                raise RuntimePaused('PAUSED_PROTOCOL', record.error) from exc
            except RuntimeError as exc:
                record.error = str(exc)
                self._checkpoint(record, state, 'PAUSED_PROTOCOL')
                raise RuntimePaused('PAUSED_PROTOCOL', record.error) from exc
            record.accepted_result = envelope.model_dump(mode='json') if envelope.result_status == 'complete' else None
            if envelope.result_status == 'complete':
                record.error = None
            self._checkpoint(record, state, 'ACCEPTED' if envelope.result_status == 'complete' else 'PAUSED_EXTERNAL')
            return envelope

    def _pause_tool_correction(self, record, state, reason):
        state['tool_correction_failure'] = reason
        record.error = reason
        self._checkpoint(record, state, 'PAUSED_PROTOCOL')
        raise RuntimePaused('PAUSED_PROTOCOL', reason)

    def _inspect_tool_arguments(self, call, profile):
        name = call['function']['name']
        if name not in profile:
            raise RuntimePaused('PAUSED_PROTOCOL', 'TOOL_NOT_ALLOWED')
        raw = call['function']['arguments']
        try:
            arguments = json.loads(raw)
        except ValueError:
            return None, [{'path': [], 'validator': 'json', 'expected': 'object'}]
        try:
            validate_arguments(self.tools[name].parameters, arguments)
        except ToolArgumentError as exc:
            return arguments, exc.details
        except RuntimeError as exc:
            # URL/access-policy failures are not permission to request a new target.
            raise RuntimePaused('PAUSED_PROTOCOL', 'TOOL_ARGUMENTS_INVALID') from exc
        return arguments, []

    def _prepare_tool_batch(self, record, state, calls, profile, response_id):
        correction = state.get('tool_correction')
        inspected = [self._inspect_tool_arguments(call, profile) for call in calls]
        is_correction = correction and (correction['phase'] == 'awaiting' or
            correction.get('corrected_response_id') == response_id)
        if is_correction:
            if len(calls) != len(correction['failures']):
                self._pause_tool_correction(record, state, 'TOOL_CORRECTION_CALLS_MISMATCH')
            for call, (arguments, errors), original in zip(calls, inspected, correction['failures']):
                if call['function']['name'] != original['name']:
                    self._pause_tool_correction(record, state, 'TOOL_CORRECTION_TARGET_CHANGED')
                if errors:
                    self._pause_tool_correction(record, state, 'TOOL_ARGUMENTS_INVALID_AFTER_CORRECTION')
                before = original['arguments']
                editable = [tuple(path) for error in original['errors']
                            for path in error.get('editable_paths', [error['path']])]
                if isinstance(before, dict):
                    def differences(left, right, path=()):
                        if isinstance(left, dict) and isinstance(right, dict):
                            for key in left.keys() | right.keys():
                                if key not in left or key not in right:
                                    yield path + (key,)
                                else:
                                    yield from differences(left[key], right[key], path + (key,))
                        elif isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
                            for index, (a, b) in enumerate(zip(left, right)):
                                yield from differences(a, b, path + (index,))
                        elif type(left) is not type(right) or left != right:
                            yield path
                    for changed in differences(before, arguments):
                        if not any(changed[:len(path)] == path for path in editable):
                            self._pause_tool_correction(record, state, 'TOOL_CORRECTION_TARGET_CHANGED')
                else:
                    # No parsed target exists to compare. A blocked improvement request remains available.
                    self._pause_tool_correction(record, state, 'TOOL_CORRECTION_TARGET_UNVERIFIABLE')
            correction['corrected_response_id'] = response_id
            correction['corrected_tool_call_ids'] = [call['id'] for call in calls]
            correction['phase'] = 'executing'
            self._checkpoint(record, state, 'RESPONSE_SAVED')
            return
        failures = [{'tool_call_id': call['id'], 'name': call['function']['name'],
                     'arguments': arguments, 'original_arguments': call['function']['arguments'],
                     'errors': errors, 'parameters': model_schema(self.tools[call['function']['name']].parameters)}
                    for call, (arguments, errors) in zip(calls, inspected) if errors]
        if not failures:
            return
        # Preparing a partially executed batch is idempotent on recovery.
        if correction and correction['original_response_id'] == response_id:
            return
        if correction_counts(state)['tool_arguments']:
            self._pause_tool_correction(record, state, 'TOOL_ARGUMENTS_INVALID_AFTER_CORRECTION')
        try:
            instruction = self.loader.render_tool_correction(self._load_prompt_snapshot(record), failures)
        except ValueError as exc:
            raise RuntimePaused('PAUSED_PROTOCOL', str(exc)) from exc
        spend_correction(state, 'tool_arguments')
        state['tool_correction'] = {'phase': 'preparing', 'original_response_id': response_id,
                                    'failures': failures, 'instruction': instruction}
        self._checkpoint(record, state, 'RESPONSE_SAVED')

    async def _model_request(self, record, state, config, on_admitted):
        if state.get('pending_model'):
            # No replay: it may have reached a remote model before process loss.
            record.error = 'REMOTE_RESULT_UNKNOWN'
            self._checkpoint(record, state, 'UNKNOWN')
            raise RuntimePaused('PAUSED_EXTERNAL', record.error)
        call_id = 'call_' + uuid4().hex
        maximum = self.prices.admission_bound(config['model'])
        request = {k: v for k, v in config.items() if k not in {'thinking', 'tools'}}
        request.update(messages=state['messages'], stream=True, stream_options={'include_usage': True},
                       extra_body={'thinking': config['thinking']}, response_format={'type': 'json_object'})
        if state['tools']:
            # Thinking mode uses the provider's automatic choice; its official
            # integration explicitly excludes the tool_choice request field.
            request.update(tools=state['tools'])
        started = datetime.now(UTC).isoformat()
        request_path = f'runs/{record.run_id}/tasks/{digest(record.task_id)}/requests/{call_id}.json'
        self.store.save_artifact(request_path, encoded(request))
        price_path = f'runs/{record.run_id}/tasks/{digest(record.task_id)}/requests/{call_id}.pricing.json'
        self.store.save_artifact(price_path, self.prices.raw)
        self.ledger.reserve(self.account_id, call_id, maximum, run_id=record.run_id, task_id=record.task_id,
            stage=self.account_id, environment_snapshot_path=record.environment_snapshot_path,
            environment_snapshot_hash=record.environment_snapshot_hash,
            campaign_id=state['subject'].get('campaign_id'), model_requested=config['model'], thinking='enabled', effort='max',
            price_snapshot_id=self.prices.snapshot_id, price_snapshot_hash=self.prices.content_hash,
            price_snapshot_path=price_path,
            prompt_hash=state['prompt_hash'], prompt_manifest=state['prompt_manifest'],
            announced_version=self.prices.model(config['model'])['announced_version'], actual_weights_version=None,
            attempt=len(record.attempt_ids), started_at=started,
            request_artifact_path=request_path, input_bound='provider_context_joint_bound')
        if on_admitted is not None:
            try:
                result = on_admitted()
                if hasattr(result, '__await__'): await result
            except BaseException:
                self.ledger.mark_not_sent(call_id)
                raise
        record.attempt_ids.append(call_id)
        state['pending_model'] = call_id
        self._checkpoint(record, state, 'RESERVED')
        self._progress(record, 'RESERVED')
        self.ledger.mark_started(call_id)
        self._checkpoint(record, state, 'IN_FLIGHT')
        chunks, content, reasoning, tool_parts = [], [], [], {}
        response_id = returned_model = fingerprint = finish = usage = None
        stream = None
        try:
            stream = await self.client.chat.completions.create(**request)
            async for item in stream:
                chunk = item.model_dump(mode='json', exclude_none=False)
                chunks.append(chunk)
                response_id = chunk.get('id') or response_id
                returned_model = chunk.get('model') or returned_model
                fingerprint = chunk.get('system_fingerprint') or fingerprint
                usage = chunk.get('usage') or usage
                for choice in chunk.get('choices', []):
                    if choice.get('index', 0) != 0: raise ValueError('MULTIPLE_CHOICES')
                    delta = choice.get('delta') or {}
                    if delta.get('content') is not None: content.append(delta['content'])
                    if delta.get('reasoning_content') is not None: reasoning.append(delta['reasoning_content'])
                    for part in delta.get('tool_calls') or []:
                        target = tool_parts.setdefault(part['index'], {'id': '', 'type': 'function',
                            'function': {'name': '', 'arguments': ''}})
                        if part.get('id'): target['id'] += part['id']
                        for key in ('name', 'arguments'):
                            if (part.get('function') or {}).get(key): target['function'][key] += part['function'][key]
                    if choice.get('finish_reason') is not None:
                        if finish is not None and finish != choice['finish_reason']: raise ValueError('FINISH_CHANGED')
                        finish = choice['finish_reason']
            if finish is None: raise ValueError('STREAM_ENDED_WITHOUT_FINISH')
            message = {'role': 'assistant', 'content': ''.join(content), 'reasoning_content': ''.join(reasoning)}
            if tool_parts:
                message['tool_calls'] = [tool_parts[i] for i in sorted(tool_parts)]
                ids = [t['id'] for t in message['tool_calls']]
                if not all(ids) or len(ids) != len(set(ids)): raise ValueError('TOOL_IDS_INVALID')
            response = {'call_id': call_id, 'request_id': response_id, 'model_returned': returned_model,
                        'price_snapshot_path': price_path, 'price_snapshot_hash': self.prices.content_hash,
                        'fingerprint': fingerprint, 'message': message, 'finish_reason': finish, 'usage': usage,
                        'started_at': started, 'completed_at': datetime.now(UTC).isoformat(), 'chunks': chunks}
            state['response'] = response
            state['pending_model'] = None
            self._checkpoint(record, state, 'RESPONSE_SAVED')
            return response
        except BaseException as exc:
            state['partial_chunks'] = chunks
            record.error = type(exc).__name__
            self.ledger.settle(call_id, '0', maximum, 'unknown', error=type(exc).__name__)
            self._checkpoint(record, state, 'UNKNOWN')
            if isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError)): raise
            raise RuntimePaused('PAUSED_EXTERNAL', 'REMOTE_RESULT_UNKNOWN') from exc
        finally:
            if stream is not None: await stream.close()

    async def _settle_response(self, record, state, response):
        if response['call_id'] in state['calls']: return
        prices = PriceBook.from_bytes(self.store.read_artifact(response['price_snapshot_path']).encode())
        if prices.content_hash != response['price_snapshot_hash']:
            raise RuntimePaused('PAUSED_PROTOCOL', 'PRICE_SNAPSHOT_HASH_MISMATCH')
        try:
            costs = prices.cost(record.model_id, response['usage'], datetime.fromisoformat(response['started_at']),
                                datetime.fromisoformat(response['completed_at']))
        except ValueError as exc:
            self.ledger.settle(response['call_id'], '0', prices.admission_bound(record.model_id), 'unknown',
                               error=str(exc), response_artifact_path=record.response_artifact_path)
            self._checkpoint(record, state, 'UNKNOWN')
            raise RuntimePaused('PAUSED_PROTOCOL', 'INVALID_PROVIDER_USAGE') from exc
        self.ledger.settle(response['call_id'], costs.lower, costs.upper, costs.status,
            usage=response['usage'], request_id=response['request_id'], model_returned=response['model_returned'],
            fingerprint=response['fingerprint'], finish_reason=response['finish_reason'],
            completed_at=response['completed_at'], response_artifact_path=record.response_artifact_path)
        state['calls'].append(response['call_id'])
        self._checkpoint(record, state, 'RESPONSE_SAVED')
        self._progress(record, 'MODEL_SETTLED')

    async def _execute_tool(self, record, state, call, profile, parent_call_id):
        name = call['function']['name']
        if name not in profile: raise RuntimePaused('PAUSED_PROTOCOL', 'TOOL_NOT_ALLOWED')
        tool = self.tools[name]
        try:
            arguments = json.loads(call['function']['arguments'])
            validate_arguments(tool.parameters, arguments)
        except (ValueError, RuntimeError) as exc:
            raise RuntimePaused('PAUSED_PROTOCOL', 'TOOL_ARGUMENTS_INVALID') from exc
        if tool.cost_upper_cny is None or not tool.cost_basis:
            raise RuntimePaused('PAUSED_EXTERNAL', 'COST_UNOBSERVABLE')
        local_read = (tool.service == 'local' and name in {'read_record', 'lookup_archive', 'request_capability'}
                      and tool.cost_upper_cny == 0)
        if state.get('pending_tool'):
            call_id = state['pending_tool']
            metadata = self.ledger.get_call(call_id)['metadata']
            if (metadata.get('tool_call_id'), metadata.get('arguments'), metadata.get('parent_call_id')) != (
                    call['id'], arguments, parent_call_id):
                raise RuntimePaused('PAUSED_PROTOCOL', 'PENDING_TOOL_ASSOCIATION_MISMATCH')
            raw_path = metadata.get('raw_response_artifact_path')
            if not local_read:
                if not tool.persists_raw_response or not raw_path:
                    raise RuntimePaused('PAUSED_EXTERNAL', 'TOOL_REMOTE_RESULT_UNKNOWN')
                try:
                    self.store.read_artifact(raw_path)
                except FileNotFoundError as exc:
                    raise RuntimePaused('PAUSED_EXTERNAL', 'TOOL_REMOTE_RESULT_UNKNOWN') from exc
        else:
            call_id = 'tool_' + uuid4().hex
            metadata = {'run_id': record.run_id, 'task_id': record.task_id, 'tool_call_id': call['id'],
                        'parent_call_id': parent_call_id, 'service': tool.service, 'method': name,
                        'cost_basis': tool.cost_basis, 'arguments': arguments, 'started_at': datetime.now(UTC).isoformat()}
            if tool.persists_raw_response:
                metadata['raw_response_artifact_path'] = f'runs/{record.run_id}/tools/{call_id}.raw.json'
            self.ledger.reserve(self.account_id, call_id, tool.cost_upper_cny, **metadata)
            self._progress(record, 'TOOL_RESERVED')
            state['pending_tool'] = call_id
            self._checkpoint(record, state)
            self.ledger.mark_started(call_id)
        try:
            result = await tool.handler(arguments, metadata)
            result = {**result, 'trace_id': call_id}
            trace = {**metadata, 'name': name, 'status': 'error' if result.get('is_error') else 'completed',
                     'call_id': call_id, 'result': result, 'source_ids': result.get('source_ids', []),
                     'evidence_ids': result.get('evidence_ids', []), 'completed_at': datetime.now(UTC).isoformat()}
            state['tool_trace'].append(trace)
            state['messages'].append({'role': 'tool', 'tool_call_id': call['id'], 'content': encoded(result)})
            state['pending_tool'] = None
            self._checkpoint(record, state, 'RESPONSE_SAVED')
            self.ledger.settle(call_id, '0', tool.cost_upper_cny, 'bounded_estimate',
                               completed_at=trace['completed_at'], response_artifact_path=record.response_artifact_path)
        except BaseException as exc:
            raw_path = metadata.get('raw_response_artifact_path')
            raw_saved = False
            if tool.persists_raw_response and raw_path:
                try:
                    self.store.read_artifact(raw_path)
                    raw_saved = True
                except FileNotFoundError:
                    pass
            if raw_saved or local_read:
                error = {'call_id': call_id, 'error_type': type(exc).__name__, 'error': str(exc),
                         'raw_response_artifact_path': raw_path, 'recorded_at': datetime.now(UTC).isoformat()}
                state.setdefault('tool_processing_errors', []).append(error)
                self.ledger.settle(call_id, '0', tool.cost_upper_cny, 'bounded_estimate',
                    error=type(exc).__name__, error_detail=str(exc), raw_response_artifact_path=raw_path)
                record.error = 'TOOL_LOCAL_PROCESSING_FAILED:' + type(exc).__name__
                self._checkpoint(record, state, 'PAUSED_PROTOCOL')
                raise RuntimePaused('PAUSED_PROTOCOL', record.error) from exc
            self.ledger.settle(call_id, '0', tool.cost_upper_cny, 'unknown', error=type(exc).__name__)
            self._checkpoint(record, state)
            raise RuntimePaused('PAUSED_EXTERNAL', 'TOOL_REMOTE_RESULT_UNKNOWN') from exc
        self._progress(record, 'TOOL_SETTLED')
