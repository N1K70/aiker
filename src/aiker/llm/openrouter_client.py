from __future__ import annotations

import json
import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class LLMConfig:
    model: str = "qwen/qwen3-235b-a22b"
    temperature: float = 0.01
    top_p: float = 0.2


class OpenRouterClient:
    def __init__(self, api_key: str, config: LLMConfig | None = None) -> None:
        self._config = config or LLMConfig(model=os.getenv("AIKER_MODEL", "qwen/qwen3-235b-a22b"))
        self._client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        return cls(api_key=api_key)

    def text_completion(self, static_system: str, dynamic_context: str, temperature: float = 0.65) -> str:
        """
        Free-form text completion — no JSON response_format enforced.
        Used for narrative/creative outputs like the pirate booklog.
        Higher temperature than json_completion to allow expressive language.
        """
        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=temperature,
            top_p=0.9,
            messages=[
                {"role": "system", "content": static_system},
                {"role": "user", "content": dynamic_context},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    def json_completion(self, static_system: str, dynamic_context: str) -> dict:
        """
        Two-part prompt architecture:
        - static_system: identity, rules, tool guidelines — stable across turns, cacheable.
        - dynamic_context: env, memory, current state — changes every turn.

        The model receives static_system as the system message and dynamic_context
        as the user message. This mirrors the cache-boundary pattern where stable
        content is separated from volatile content to maximize cache reuse.
        """
        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            top_p=self._config.top_p,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": static_system},
                {"role": "user", "content": dynamic_context},
            ],
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response was not valid JSON: {content}") from exc
