"""Thin provider adapter. The LLM is used for exactly two things:
(1) parsing intents into JSON, (2) phrasing the final reply from verified facts.

Every call is optional: if no key is configured, the SDK is missing, the call
fails or the model refuses, callers fall back to deterministic code.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from app import config

log = logging.getLogger("novamart.llm")


@dataclass
class Usage:
    calls: list[dict] = field(default_factory=list)

    def add(self, purpose: str, model: str, inp: int, out: int, ms: int, ok: bool, note: str = "") -> None:
        self.calls.append({"purpose": purpose, "model": model, "input_tokens": inp, "output_tokens": out,
                           "latency_ms": ms, "ok": ok, **({"note": note} if note else {})})

    @property
    def total_tokens(self) -> int:
        return sum(c["input_tokens"] + c["output_tokens"] for c in self.calls)


class LLM:
    def __init__(self, provider: str = config.LLM_PROVIDER, model: str = config.LLM_MODEL,
                 api_key: str = config.LLM_API_KEY):
        self.provider, self.model, self.api_key = provider, model, api_key
        self._client = None

    # ------------------------------------------------------------ availability
    @property
    def available(self) -> bool:
        return config.LLM_MODE != "off" and bool(self.api_key) and self._get_client() is not None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            if self.provider == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key, timeout=config.LLM_TIMEOUT_S, max_retries=1)
            elif self.provider == "gemini":
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            elif self.provider == "openai":
                import openai
                self._client = openai.OpenAI(api_key=self.api_key, timeout=config.LLM_TIMEOUT_S, max_retries=1)
        except Exception as e:  # SDK not installed / bad config -> deterministic mode
            log.warning("LLM client unavailable: %s", e)
            self._client = None
        return self._client

    # -------------------------------------------------------------------- calls
    def complete(self, system: str, user: str, usage: Usage, purpose: str,
                 schema: dict | None = None, max_tokens: int = 1024) -> str | None:
        """Return text (JSON text when `schema` is given) or None on any failure."""
        if not self.available:
            return None
        t0 = time.perf_counter()
        try:
            text, inp, out = getattr(self, f"_call_{self.provider}")(system, user, schema, max_tokens)
            usage.add(purpose, self.model, inp, out, int((time.perf_counter() - t0) * 1000), text is not None)
            return text
        except Exception as e:
            usage.add(purpose, self.model, 0, 0, int((time.perf_counter() - t0) * 1000), False, type(e).__name__)
            log.warning("LLM call failed (%s): %s", purpose, e)
            return None

    def complete_json(self, system: str, user: str, schema: dict, usage: Usage, purpose: str) -> dict | None:
        text = self.complete(system, user, usage, purpose, schema=schema)
        if not text:
            return None
        try:
            return json.loads(text[text.find("{"): text.rfind("}") + 1])
        except (ValueError, TypeError):
            return None

    # --------------------------------------------------------------- providers
    def _call_anthropic(self, system, user, schema, max_tokens):
        output_config: dict = {"effort": "low"}  # short extraction/phrasing tasks: low effort keeps latency + cost down
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        resp = self._client.messages.create(
            model=self.model, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config=output_config,
        )
        if resp.stop_reason in ("refusal", "max_tokens"):
            return None, resp.usage.input_tokens, resp.usage.output_tokens
        text = next((b.text for b in resp.content if b.type == "text"), None)
        return text, resp.usage.input_tokens, resp.usage.output_tokens

    def _call_gemini(self, system, user, schema, max_tokens):
        from google.genai import types
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=0, max_output_tokens=max_tokens,
                                          response_mime_type="application/json" if schema else "text/plain")
        resp = self._client.models.generate_content(model=self.model, contents=user, config=cfg)
        um = getattr(resp, "usage_metadata", None)
        return resp.text, getattr(um, "prompt_token_count", 0) or 0, getattr(um, "candidates_token_count", 0) or 0

    def _call_openai(self, system, user, schema, max_tokens):
        kwargs = {"response_format": {"type": "json_object"}} if schema else {}
        resp = self._client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs)
        return resp.choices[0].message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm
