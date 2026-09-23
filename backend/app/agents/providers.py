"""Call OpenAI or Anthropic with the company's key. The browser never sees it."""

from __future__ import annotations

from typing import Literal

import httpx

Provider = Literal["openai", "anthropic"]

MODELS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-6-astra", "gpt-6-sol"),
    "anthropic": ("claude-fable-5-1", "claude-opus-5"),
}

DEFAULT_MODEL = {"openai": "gpt-6-astra", "anthropic": "claude-fable-5-1"}


def provider_label(provider: str) -> str:
    if provider == "openai":
        return "ChatGPT"
    if provider == "anthropic":
        return "Claude"
    return provider


def openai_payload(model: str, system: str, messages: list[dict[str, str]]) -> dict:
    return {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": 4096,
    }


def anthropic_payload(model: str, system: str, messages: list[dict[str, str]]) -> dict:
    return {
        "model": model,
        "system": system,
        "messages": _alternating(messages),
        "max_tokens": 4096,
    }


def _alternating(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Anthropic requires user and assistant turns to alternate, starting with user."""
    cleaned: list[dict[str, str]] = []
    for message in messages:
        if message["role"] not in {"user", "assistant"}:
            continue
        if cleaned and cleaned[-1]["role"] == message["role"]:
            cleaned[-1]["content"] = f"{cleaned[-1]['content']}\n\n{message['content']}"
            continue
        cleaned.append({"role": message["role"], "content": message["content"]})
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    return cleaned


async def complete(
    *,
    provider: str,
    model: str,
    api_key: str,
    system: str,
    messages: list[dict[str, str]],
) -> str:
    async with httpx.AsyncClient(timeout=45.0) as client:
        if provider == "openai":
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=openai_payload(model, system, messages),
            )
            if response.status_code >= 300:
                raise httpx.HTTPStatusError(
                    "openai", request=response.request, response=response
                )
            data = response.json()
            return str(data["choices"][0]["message"]["content"] or "")
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=anthropic_payload(model, system, messages),
        )
        if response.status_code >= 300:
            raise httpx.HTTPStatusError(
                "anthropic", request=response.request, response=response
            )
        data = response.json()
        parts = data.get("content") or []
        texts = [part.get("text", "") for part in parts if part.get("type") == "text"]
        return "\n".join(text for text in texts if text)
