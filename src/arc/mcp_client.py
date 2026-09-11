"""Official MCP v2 sessions with explicit capabilities and strict read-only dispatch."""
from __future__ import annotations

import anyio
import ipaddress
import os
import re
import shlex
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import AsyncIterator, Literal
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from mcp import Client, StdioServerParameters
from mcp.client.sse import sse_client


class MCPFailure(RuntimeError):
    pass


class ToolArgumentError(MCPFailure):
    """Recoverable argument structure errors, distinct from access-policy failures."""
    def __init__(self, code, details):
        super().__init__(code)
        self.details = details


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    transport: Literal['sse', 'stdio']
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict, repr=False)
    headers: dict[str, str] = field(default_factory=dict, repr=False)
    timeout_seconds: float = 900
    startup_timeout_seconds: float = 30


@dataclass(frozen=True)
class Capability:
    name: str
    service: str
    method: str
    parameters: dict
    origin: str
    cost_upper_cny: Decimal | None
    cost_basis: str
    allow_unmetered: bool = False


def model_schema(schema: dict) -> dict:
    """Schema structure is mechanical; external prose is retained only in audit."""
    if isinstance(schema, dict):
        return {key: ({name: model_schema(child) for name, child in value.items()}
                      if key in {'properties', '$defs', 'definitions', 'patternProperties'} else model_schema(value))
                for key, value in schema.items() if key not in {'description', 'title', 'examples', '$comment'}}
    if isinstance(schema, list):
        return [model_schema(value) for value in schema]
    return schema


def validate_arguments(parameters: dict, arguments: dict) -> None:
    if not isinstance(arguments, dict):
        raise ToolArgumentError('TOOL_ARGUMENTS_NOT_OBJECT',
                                [{'path': [], 'validator': 'type', 'expected': 'object'}])
    # Omitted additionalProperties in MCP does not authorize ARC metadata.
    allowed = set(parameters.get('properties', {}))
    undeclared = [{'path': [key], 'validator': 'additionalProperties', 'expected': False}
                  for key in sorted(set(arguments) - allowed)]
    errors = list(Draft202012Validator(parameters).iter_errors(arguments))
    if errors or undeclared:
        def details(error):
            path = list(error.absolute_path)
            editable = [path]
            if error.validator == 'required' and isinstance(error.instance, dict):
                editable = [path + [key] for key in error.validator_value if key not in error.instance]
            elif error.validator == 'additionalProperties' and isinstance(error.instance, dict):
                properties = error.schema.get('properties', {})
                patterns = error.schema.get('patternProperties', {})
                editable = [path + [key] for key in error.instance
                            if key not in properties and not any(re.search(p, key) for p in patterns)]
            elif error.validator in {'anyOf', 'oneOf', 'allOf', 'not', 'if', 'dependentRequired'}:
                # A compound failure does not identify which otherwise valid fields may change.
                editable = []
            return {'path': path, 'validator': error.validator,
                    'expected': error.validator_value, 'editable_paths': editable}
        raise ToolArgumentError('TOOL_ARGUMENTS_UNDECLARED' if undeclared else 'TOOL_ARGUMENTS_SCHEMA',
                                undeclared + [details(error) for error in errors])
    def check(value):
        if isinstance(value, dict):
            for item in value.values(): check(item)
        elif isinstance(value, list):
            for item in value: check(item)
        elif isinstance(value, str) and '://' in value:
            parsed = urlparse(value)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
                raise MCPFailure('TOOL_URL_FORBIDDEN')
            host = parsed.hostname.lower()
            if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
                raise MCPFailure('TOOL_URL_FORBIDDEN')
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                return
            if not address.is_global:
                raise MCPFailure('TOOL_URL_FORBIDDEN')
    check(arguments)


class MCPHub:
    def __init__(self, services: list[ServiceConfig], mappings: dict[str, dict]):
        self.services = {s.name: s for s in services}
        if len(self.services) != len(services):
            raise ValueError('MCP_DUPLICATE_SERVICE')
        self.mappings = mappings
        self.capabilities: dict[str, Capability] = {}
        self.inventory: dict[str, dict] = {}
        self.failures: dict[str, str] = {}

    @classmethod
    def from_environment(cls, mappings: dict[str, dict], environment: dict[str, str] | None = None):
        env = os.environ if environment is None else environment
        services = []
        timeout = float(env.get('ARC_MCP_CALL_TIMEOUT_SECONDS', '900'))
        for name, prefix in [('scholartrace', 'ARC_SCHOLARTRACE'), ('scholaranalysis', 'ARC_SCHOLARANALYSIS')]:
            url = env.get(prefix + '_URL')
            if url:
                token = env.get(prefix + '_TOKEN')
                headers = {'Authorization': 'Bearer ' + token} if token else {}
                services.append(ServiceConfig(name, 'sse', url=url, headers=headers, timeout_seconds=timeout))
        command = env.get('ARC_MCP_WEBRESEARCH_CMD')
        if command:
            argv = shlex.split(command)
            if not argv: raise MCPFailure('MCP_COMMAND_REQUIRED')
            services.append(ServiceConfig('webresearch', 'stdio', command=argv[0], args=tuple(argv[1:]),
                                          timeout_seconds=timeout))
        return cls(services, mappings)

    @asynccontextmanager
    async def _client(self, config: ServiceConfig) -> AsyncIterator[Client]:
        if config.transport == 'sse':
            if not config.url: raise MCPFailure('MCP_URL_REQUIRED')
            transport = sse_client(config.url, headers=config.headers,
                                   timeout=config.startup_timeout_seconds,
                                   sse_read_timeout=config.timeout_seconds)
        elif config.transport == 'stdio':
            if not config.command: raise MCPFailure('MCP_COMMAND_REQUIRED')
            # Executable and argv are deployment configuration, never model data.
            transport = StdioServerParameters(command=config.command, args=list(config.args), env=config.env or None)
        else:
            raise MCPFailure('MCP_TRANSPORT_FORBIDDEN')
        client = Client(transport, read_timeout_seconds=config.startup_timeout_seconds, raise_exceptions=False)
        # Use the SDK's cancellation system. Native asyncio task.cancel defeats
        # its shielded stdio process cleanup on Windows.
        with anyio.fail_after(config.timeout_seconds + config.startup_timeout_seconds):
            async with client:
                yield client

    async def prepare(self) -> dict[str, Capability]:
        self.capabilities = {}
        self.inventory = {}
        self.failures = {}
        for name, config in self.services.items():
            try:
                async with self._client(config) as client:
                    tool_list = []
                    cursor = None
                    seen = set()
                    while True:
                        page = await client.list_tools(cursor=cursor)
                        tool_list.extend(t.model_dump(mode='json', by_alias=True) for t in page.tools)
                        cursor = page.next_cursor
                        if cursor is None: break
                        if cursor in seen: raise MCPFailure('MCP_CURSOR_CYCLE')
                        seen.add(cursor)
                    self.inventory[name] = {'protocol_version': client.protocol_version, 'tools': tool_list}
            except Exception as exc:
                self.failures[name] = type(exc).__name__
        allowed_wrappers = {'search_literature', 'read_paper', 'search_web', 'read_web'}
        for wrapper, mapping in self.mappings.items():
            if wrapper not in allowed_wrappers:
                raise MCPFailure('MCP_WRAPPER_FORBIDDEN')
            listed = self.inventory.get(mapping['service'], {}).get('tools', [])
            matches = [t for t in listed if t['name'] == mapping['method']]
            if len(matches) != 1:
                continue
            schema = matches[0]['inputSchema']
            Draft202012Validator.check_schema(schema)
            upper = mapping.get('cost_upper_cny')
            basis = mapping.get('cost_basis', '')
            unmetered = mapping.get('allow_unmetered', False)
            if type(unmetered) is not bool or (unmetered and (wrapper, mapping['service'], mapping['method']) != ('search_literature', 'scholartrace', 'query')):
                raise MCPFailure('UNMETERED_TOOL_NOT_AUTHORIZED')
            if upper is not None and (Decimal(str(upper)) < 0 or not basis):
                raise MCPFailure('MCP_COST_BASIS_REQUIRED')
            self.capabilities[wrapper] = Capability(wrapper, mapping['service'], mapping['method'],
                                                   schema, mapping['origin'],
                                                   None if upper is None else Decimal(str(upper)), basis, unmetered)
        return self.capabilities

    async def call(self, name: str, arguments: dict) -> dict:
        if name not in self.capabilities:
            raise MCPFailure('MCP_CAPABILITY_UNAVAILABLE')
        cap = self.capabilities[name]
        validate_arguments(cap.parameters, arguments)
        # Runtime performs financial admission before this method; unknown costs
        # require explicit scoped authorization here too, including direct callers.
        if cap.cost_upper_cny is None and not (cap.allow_unmetered and
                (cap.name, cap.service, cap.method) == ('search_literature', 'scholartrace', 'query')):
            raise MCPFailure('COST_UNOBSERVABLE')
        async with self._client(self.services[cap.service]) as client:
            result = await client.call_tool(cap.method, arguments,
                                           read_timeout_seconds=self.services[cap.service].timeout_seconds)
        raw = result.model_dump(mode='json', by_alias=True)
        return {'is_error': result.is_error, 'structured_content': result.structured_content,
                'content': raw['content'], 'origin': cap.origin,
                'service': cap.service, 'method': cap.method, 'raw': raw}
