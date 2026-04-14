from __future__ import annotations

import json
import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class LLMConfig:
    model: str = "qwen/qwen3.6-plus"
    temperature: float = 0.01
    top_p: float = 0.2


class OpenRouterClient:
    def __init__(self, api_key: str, config: LLMConfig | None = None) -> None:
        self._config = config or LLMConfig(model=os.getenv("AIKER_MODEL", "qwen/qwen3.6-plus"))
        self._client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    @classmethod
    def from_env(cls) -> "OpenRouterClient":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        return cls(api_key=api_key)

    def json_completion(self, system_prompt: str, user_prompt: str) -> dict:
        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            top_p=self._config.top_p,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response was not valid JSON: {content}") from exc
