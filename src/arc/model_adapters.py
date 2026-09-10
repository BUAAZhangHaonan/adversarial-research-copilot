"""Configured Chat Completions adapters; provider details stay outside research tasks."""
from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra='forbid')
    json_output: bool = True
    tools: bool = True
    streaming_usage: bool = True
    max_output_tokens: int = Field(default=384000, ge=1)


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['deepseek', 'openai_compatible'] = 'deepseek'
    model: str = Field(min_length=1)
    base_url: str = 'https://api.deepseek.com'
    base_url_env: str | None = 'DEEPSEEK_BASE_URL'
    api_key_env: str = 'DEEPSEEK_API_KEY'
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    # Only this provider adapter interprets these options. Other compatible
    # endpoints omit both by default; support must be configured explicitly.
    reasoning_effort: str | None = None
    thinking: Literal['enabled', 'disabled'] | None = None

    @model_validator(mode='after')
    def provider_options(self):
        if self.provider == 'deepseek':
            if self.reasoning_effort not in (None, 'max') or self.thinking not in (None, 'enabled'):
                raise ValueError('DEEPSEEK_CURRENT_CAPABILITY_MUST_REMAIN_MAX')
            self.reasoning_effort, self.thinking = 'max', 'enabled'
            if self.capabilities.max_output_tokens != 384000:
                raise ValueError('DEEPSEEK_CURRENT_OUTPUT_LIMIT_MUST_REMAIN_384000')
        else:
            if self.thinking is not None:
                raise ValueError('PROVIDER_THINKING_OPTION_UNSUPPORTED')
            if not {'base_url', 'api_key_env'} <= self.model_fields_set:
                raise ValueError('COMPATIBLE_ENDPOINT_AND_CREDENTIAL_ENV_REQUIRED')
            if 'base_url_env' not in self.model_fields_set:
                self.base_url_env = None
        if not self.base_url.startswith(('https://', 'http://')):
            raise ValueError('MODEL_BASE_URL_INVALID')
        return self

    def endpoint(self):
        return (os.environ.get(self.base_url_env) if self.base_url_env else None) or self.base_url

    def credentials(self):
        value = os.environ.get(self.api_key_env)
        if not value:
            raise ValueError('MODEL_CREDENTIALS_MISSING:' + self.api_key_env)
        return value

    def invocation_config(self, alias, prices, functions):
        for operation in ('json_output', 'streaming_usage'):
            if not getattr(self.capabilities, operation):
                raise ValueError('MODEL_OPERATION_UNSUPPORTED:' + alias + ':' + operation)
        if functions and not self.capabilities.tools:
            raise ValueError('MODEL_OPERATION_UNSUPPORTED:' + alias + ':tools')
        if prices.maximum_output(self.model) != self.capabilities.max_output_tokens:
            raise ValueError('MODEL_PRICING_OUTPUT_LIMIT_MISMATCH:' + alias)
        config = dict(model=self.model, model_alias=alias, provider=self.provider,
            endpoint=self.endpoint(), max_tokens=self.capabilities.max_output_tokens, tools=functions)
        if self.reasoning_effort is not None:
            config['reasoning_effort'] = self.reasoning_effort
        if self.thinking is not None:
            config['thinking'] = {'type': self.thinking}
        return config


CURRENT_RESEARCH_ALIAS = 'deepseek-v4.1-flash'
CURRENT_API_MODEL = 'deepseek-flash'


def default_models():
    return {CURRENT_RESEARCH_ALIAS: ModelSpec(model=CURRENT_API_MODEL)}


def request_parameters(config, messages, tools):
    if config['provider'] == 'deepseek':
        # The provider rejects JSON mode unless a system/user prompt names JSON.
        # Validate the actual wire messages, including replacement repair prompts;
        # do not silently inject instructions or count assistant/tool output.
        prompt_text = []
        for message in messages:
            if message.get('role') not in {'system', 'user'}:
                continue
            content = message.get('content')
            if isinstance(content, str):
                prompt_text.append(content)
            elif isinstance(content, list):
                prompt_text.extend(part['text'] for part in content if isinstance(part, dict)
                    and part.get('type') == 'text' and isinstance(part.get('text'), str))
        if not any('json' in text.casefold() for text in prompt_text):
            raise ValueError('DEEPSEEK_JSON_PROMPT_KEYWORD_REQUIRED')
    request = {k: v for k, v in config.items()
        if k not in {'thinking', 'tools', 'model_alias', 'provider', 'endpoint'}}
    # DeepSeek needs reasoning_content on tool continuations; standard compatible
    # endpoints receive only the supported conversation fields.
    if config['provider'] != 'deepseek':
        messages = [{k: v for k, v in message.items() if k != 'reasoning_content'} for message in messages]
    request.update(messages=messages, stream=True, stream_options={'include_usage': True},
        response_format={'type': 'json_object'})
    if 'thinking' in config:
        request['extra_body'] = {'thinking': config['thinking']}
    if tools:
        request['tools'] = tools
    return request


def normalized_usage(provider, usage):
    if provider == 'openai_compatible' and usage and 'prompt_tokens_details' in usage:
        usage = dict(usage)
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
        if type(cached) is int and type(usage.get('prompt_tokens')) is int:
            usage['prompt_cache_hit_tokens'] = cached
            usage['prompt_cache_miss_tokens'] = usage['prompt_tokens'] - cached
    return usage
