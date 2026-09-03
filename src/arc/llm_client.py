from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml


@dataclass
class ModelSpec:
    name: str
    provider: str
    base_url_env: str
    api_key_env: str
    endpoint: str
    max_output_tokens: int | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class LLMClient:
    def __init__(self, config_path: str | Path = "configs/models.yaml") -> None:
        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        defaults = config.get("generation_defaults", {}
                              ) if isinstance(config, dict) else {}
        self._default_temperature = _as_float(defaults.get("temperature"), 0.3)
        self._default_max_output_tokens = _as_int(
            defaults.get("max_output_tokens"), 16384)
        self._default_fallback_max_output_tokens = _as_int(
            defaults.get("fallback_max_output_tokens"), 4096)
        self._models: dict[str, ModelSpec] = {}
        for name, spec in config.get("models", {}).items():
            self._models[name] = ModelSpec(
                name=name,
                provider=spec["provider"],
                base_url_env=spec["base_url_env"],
                api_key_env=spec["api_key_env"],
                endpoint=spec["endpoint"],
                max_output_tokens=_as_optional_int(
                    spec.get("max_output_tokens")),
                max_tokens=_as_optional_int(spec.get("max_tokens")),
                temperature=_as_optional_float(spec.get("temperature")),
            )

    def chat(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        if model not in self._models:
            raise ValueError(f"Unknown model: {model}")
        spec = self._models[model]
        base_url = os.getenv(spec.base_url_env, "").rstrip("/")
        api_key = os.getenv(spec.api_key_env, "")
        if not base_url or not api_key:
            raise RuntimeError(
                f"Missing endpoint or API key for model {model}. "
                f"Set {spec.base_url_env} and {spec.api_key_env}."
            )

        # Some gateways may (rarely) return empty strings with 200 OK.
        # Treat empty/whitespace as a transient failure and retry a small number of times.
        empty_retry_attempts = min(2, _retry_attempts())
        delay = 0.6
        last_text: str | None = None
        for attempt in range(1, empty_retry_attempts + 1):
            if spec.endpoint == "chat_completions":
                text = self._call_chat_completions(
                    base_url,
                    api_key,
                    model,
                    system_prompt,
                    user_prompt,
                    self._resolve_temperature(spec, temperature),
                    self._resolve_chat_max_tokens(spec),
                )
            elif spec.endpoint == "responses":
                text = self._call_responses(
                    base_url,
                    api_key,
                    model,
                    system_prompt,
                    user_prompt,
                    self._resolve_temperature(spec, temperature),
                    self._resolve_max_output_tokens(spec),
                    self._resolve_fallback_max_output_tokens(),
                )
            else:
                raise ValueError(f"Unsupported endpoint: {spec.endpoint}")

            last_text = text
            if isinstance(text, str) and text.strip():
                return text

            if attempt < empty_retry_attempts:
                time.sleep(delay)
                delay = min(delay * 2, 3.0)

        raise RuntimeError(f"Empty text returned by model '{model}'")

    def _resolve_temperature(self, spec: ModelSpec, requested: float) -> float:
        env = os.getenv("ARC_TEMPERATURE")
        if env is not None and env.strip():
            return _as_float(env, self._default_temperature)
        if requested != 0.3:
            return requested
        if spec.temperature is not None:
            return spec.temperature
        return self._default_temperature

    def _resolve_max_output_tokens(self, spec: ModelSpec) -> int:
        env = os.getenv("ARC_MAX_OUTPUT_TOKENS")
        if env is not None and env.strip():
            return max(1, _as_int(env, self._default_max_output_tokens))
        if spec.max_output_tokens is not None:
            return max(1, spec.max_output_tokens)
        return max(1, self._default_max_output_tokens)

    def _resolve_chat_max_tokens(self, spec: ModelSpec) -> int:
        env = os.getenv("ARC_CHAT_MAX_TOKENS")
        if env is not None and env.strip():
            return max(1, _as_int(env, self._default_max_output_tokens))
        if spec.max_tokens is not None:
            return max(1, spec.max_tokens)
        return max(1, self._default_max_output_tokens)

    def _resolve_fallback_max_output_tokens(self) -> int:
        env = os.getenv("ARC_FALLBACK_MAX_OUTPUT_TOKENS")
        if env is not None and env.strip():
            return max(1, _as_int(env, self._default_fallback_max_output_tokens))
        return max(1, self._default_fallback_max_output_tokens)

    @staticmethod
    def _call_chat_completions(
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        url = _resolve_api_url(base_url, "chat/completions")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            data = _post_json_with_retry(url, headers, payload)
            # Some gateways return 200 with an empty/missing choices array;
            # treat malformed shapes like empty content and fall back to streaming.
            try:
                text = data["choices"][0]["message"].get("content")
            except (KeyError, IndexError, AttributeError, TypeError):
                text = None
            if isinstance(text, str) and text.strip():
                return text
        except requests.exceptions.HTTPError as exc:
            # Some gateways reject non-streaming requests for large payloads
            # but succeed with streaming.  Only fall back on client errors
            # that might be gateway-specific (e.g. 400).
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and status < 500 and status != 401 and status != 403:
                pass  # fall through to streaming fallback below
            else:
                raise
        # Some gateways return empty content in non-streaming mode, or
        # reject non-streaming requests outright; fall back to streaming
        # which reliably delivers text chunks.  Retry streaming a few
        # times on empty responses since the gateway may be flaky.
        max_stream_retries = 3
        delay = 2.0
        for attempt in range(1, max_stream_retries + 1):
            try:
                return _stream_chat_completions(url, headers, payload, timeout=_request_timeout_seconds())
            except RuntimeError:
                if attempt >= max_stream_retries:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 15.0)

    @staticmethod
    def _call_responses(
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_output_tokens: int,
        fallback_max_output_tokens: int,
    ) -> str:
        url = _resolve_api_url(base_url, "responses")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "temperature": temperature,
            "reasoning": {
                "effort": _gpt_reasoning_effort(),
            },
            "text": {
                "verbosity": _gpt_text_verbosity(),
            },
            "max_output_tokens": max_output_tokens,
        }
        try:
            data = _post_json_with_retry(url, headers, payload)
        except (requests.exceptions.HTTPError, requests.exceptions.ReadTimeout) as e:
            if not _is_transient_gateway_error(e):
                raise

            fallback_payload = {
                "model": model,
                "input": payload["input"],
                "max_output_tokens": fallback_max_output_tokens,
            }
            # Keep temperature only if explicitly requested by caller path.
            if "temperature" in payload:
                fallback_payload["temperature"] = payload["temperature"]
            data = _post_json_with_retry(url, headers, fallback_payload)

        # Responses API may return either output_text shortcut or nested output items.
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"]

        output = data.get("output", [])
        texts: list[str] = []
        for item in output:
            for c in item.get("content", []):
                text = c.get("text")
                if text:
                    texts.append(text)
        if texts:
            return "\n".join(texts)

        raise RuntimeError("No text content returned by responses API")


def _stream_chat_completions(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> str:
    """Send a chat-completions request with stream=True and concatenate delta chunks."""
    stream_payload = {**payload, "stream": True}
    parts: list[str] = []
    resp = requests.post(url, headers=headers, json=stream_payload, timeout=timeout, stream=True)
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if not decoded.startswith("data: "):
            continue
        data_str = decoded[6:]
        if data_str.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices", []):
            delta = choice.get("delta", {})
            content = delta.get("content", "")
            if content:
                parts.append(content)
    text = "".join(parts)
    if not text.strip():
        raise RuntimeError("No text content from streaming chat completions")
    return text


def _request_timeout_seconds() -> float:
    raw = os.getenv("ARC_LLM_TIMEOUT_SECONDS", "90").strip()
    try:
        value = float(raw)
    except ValueError:
        return 90.0
    return value if value > 0 else 90.0


def _post_json_with_retry(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    max_attempts = _retry_attempts()
    delay = 0.8
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=_request_timeout_seconds())
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ReadTimeout as e:
            last_exc = e
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            # Retry on rate-limit and transient gateway failures.
            if status not in {429} and status is not None and status < 500:
                raise
            last_exc = e

        if attempt < max_attempts:
            if isinstance(last_exc, requests.exceptions.HTTPError) and last_exc.response is not None:
                retry_after = last_exc.response.headers.get(
                    "Retry-After", "").strip()
                if retry_after.isdigit():
                    delay = max(delay, float(retry_after))
                elif last_exc.response.status_code == 429:
                    delay = max(delay, 10.0)
            time.sleep(delay)
            delay = min(delay * 2, 30.0)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unexpected retry state")


def _retry_attempts() -> int:
    raw = os.getenv("ARC_LLM_RETRY_ATTEMPTS", "5").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3
    return value if value >= 1 else 3


def _is_transient_gateway_error(exc: Exception) -> bool:
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        return status in {429, 502, 503, 504, 524}
    return False


def _gpt_reasoning_effort() -> str:
    raw = os.getenv("ARC_GPT_REASONING_EFFORT", "high").strip().lower()
    allowed = {"none", "minimal", "low", "medium", "high", "xhigh"}
    return raw if raw in allowed else "high"


def _gpt_text_verbosity() -> str:
    raw = os.getenv("ARC_GPT_VERBOSITY", "medium").strip().lower()
    allowed = {"low", "medium", "high"}
    return raw if raw in allowed else "medium"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_api_url(base_url: str, endpoint_suffix: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_suffix = endpoint_suffix.strip("/")
    if normalized_base.endswith("/" + normalized_suffix):
        return normalized_base
    return f"{normalized_base}/{normalized_suffix}"
