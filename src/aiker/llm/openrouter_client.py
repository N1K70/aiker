from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from openai import OpenAI


def _extract_json(content: str) -> str:
    """
    Strip Qwen3 / other CoT model thinking blocks and extract the JSON object.

    Some reasoning models (Qwen3, DeepSeek-R1) wrap their chain-of-thought in
    <think>...</think> tags before the actual response.  When response_format is
    json_object, the thinking content may still appear in the message and contain
    large integers (reasoning budget tokens) that exceed Python 3.11+ int limits.

    Strategy:
      1. Remove <think>...</think> blocks (including partial/unclosed ones).
      2. Scan for the first top-level JSON object { ... }.
      3. Fall back to the raw content so the caller gets a useful error message.
    """
    # Strip thinking blocks (may be unclosed if the model was interrupted)
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL).strip()

    # Extract first JSON object — handles preamble text before the brace
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else cleaned


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
        raw = response.choices[0].message.content or ""
        # Strip thinking blocks — narrative output should be just the entry text
        return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

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
            # Do NOT set response_format=json_object — Qwen3 / DeepSeek-R1 in
            # thinking mode return a JSON-encoded string instead of an object
            # when that flag is used.  We enforce JSON via the system prompt and
            # extract it manually via _extract_json().
            messages=[
                {"role": "system", "content": static_system},
                {"role": "user", "content": dynamic_context},
            ],
        )
        content = response.choices[0].message.content or "{}"
        extracted = _extract_json(content)
        try:
            # parse_int=str avoids Python 3.11+ integer-string conversion limits
            # triggered by large CoT budget tokens in Qwen3/DeepSeek-R1 responses.
            result = json.loads(extracted, parse_int=str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response was not valid JSON: {extracted!r}") from exc
        if not isinstance(result, dict):
            raise ValueError(f"Model returned {type(result).__name__}, expected JSON object: {extracted!r}")
        return result
