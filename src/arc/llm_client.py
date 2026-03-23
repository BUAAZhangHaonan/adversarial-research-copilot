from __future__ import annotations

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


class LLMClient:
    def __init__(self, config_path: str | Path = "configs/models.yaml") -> None:
        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        self._models: dict[str, ModelSpec] = {}
        for name, spec in config.get("models", {}).items():
            self._models[name] = ModelSpec(
                name=name,
                provider=spec["provider"],
                base_url_env=spec["base_url_env"],
                api_key_env=spec["api_key_env"],
                endpoint=spec["endpoint"],
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

        if spec.endpoint == "chat_completions":
            return self._call_chat_completions(base_url, api_key, model, system_prompt, user_prompt, temperature)
        if spec.endpoint == "responses":
            return self._call_responses(base_url, api_key, model, system_prompt, user_prompt, temperature)

        raise ValueError(f"Unsupported endpoint: {spec.endpoint}")

    @staticmethod
    def _call_chat_completions(
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        url = f"{base_url}/chat/completions"
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
            "max_tokens": 1800,
            "stream": False,
        }
        data = _post_json_with_retry(url, headers, payload)
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _call_responses(
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        url = f"{base_url}/responses"
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
            "max_output_tokens": 1800,
        }
        try:
            data = _post_json_with_retry(url, headers, payload)
        except (requests.exceptions.HTTPError, requests.exceptions.ReadTimeout) as e:
            if not _is_transient_gateway_error(e):
                raise

            fallback_payload = {
                "model": model,
                "input": payload["input"],
                "max_output_tokens": 900,
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
            resp = requests.post(url, headers=headers, json=payload, timeout=_request_timeout_seconds())
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ReadTimeout as e:
            last_exc = e
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and status < 500:
                raise
            last_exc = e

        if attempt < max_attempts:
            time.sleep(delay)
            delay = min(delay * 2, 5.0)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unexpected retry state")


def _retry_attempts() -> int:
    raw = os.getenv("ARC_LLM_RETRY_ATTEMPTS", "3").strip()
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
        return status in {502, 503, 504, 524}
    return False


def _gpt_reasoning_effort() -> str:
    raw = os.getenv("ARC_GPT_REASONING_EFFORT", "high").strip().lower()
    allowed = {"none", "minimal", "low", "medium", "high", "xhigh"}
    return raw if raw in allowed else "high"


def _gpt_text_verbosity() -> str:
    raw = os.getenv("ARC_GPT_VERBOSITY", "medium").strip().lower()
    allowed = {"low", "medium", "high"}
    return raw if raw in allowed else "medium"
