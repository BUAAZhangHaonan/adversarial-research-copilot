from __future__ import annotations

import os
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
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
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
            "max_output_tokens": 1800,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()

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
