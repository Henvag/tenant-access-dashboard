"""Call OpenAI, Anthropic, Google, or the built-in Cloudflare model. The browser never sees a key."""

from __future__ import annotations

import logging
from typing import Literal

import httpx

Provider = Literal["openai", "anthropic", "google", "cloudflare"]

MODELS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-6-astra", "gpt-6-sol"),
    "anthropic": ("claude-fable-5-1", "claude-opus-5"),
    # Flash-Lite has the free-tier headroom (about 500 requests/day). Full Flash
    # is smarter but typically only about 20 free requests/day.
    "google": ("gemini-3.5-flash-lite", "gemini-3.8-flash"),
}

DEFAULT_MODEL = {
    "openai": "gpt-6-astra",
    "anthropic": "claude-fable-5-1",
    "google": "gemini-3.5-flash-lite",
}

MAX_OUTPUT_TOKENS = 4096
logger = logging.getLogger(__name__)
# Built-in Ask answers are short, but Gemma 4 is a reasoning model: any thinking
# counts toward this cap, so it must leave room for the answer after it.
BUILTIN_MAX_OUTPUT_TOKENS = 3072
# Ask about workspace facts doesn't need step-by-step thinking. Turning it off
# makes answers faster and cheaper and stops them being cut off.
BUILTIN_EXTRA = {"chat_template_kwargs": {"enable_thinking": False}}


def provider_label(provider: str) -> str:
    if provider == "openai":
        return "ChatGPT"
    if provider == "anthropic":
        return "Claude"
    if provider == "google":
        return "Gemini"
    if provider == "cloudflare":
        return "Gemma"
    return provider


def openai_payload(model: str, system: str, messages: list[dict[str, str]]) -> dict:
    return {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": MAX_OUTPUT_TOKENS,
    }


def anthropic_payload(model: str, system: str, messages: list[dict[str, str]]) -> dict:
    return {
        "model": model,
        "system": system,
        "messages": _alternating(messages),
        "max_tokens": MAX_OUTPUT_TOKENS,
    }


def google_payload(system: str, messages: list[dict[str, str]]) -> dict:
    """Gemini generateContent. The model is in the URL, not the body."""
    contents = [
        {
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["content"]}],
        }
        for message in _alternating(messages)
    ]
    return {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS},
    }


def _alternating(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Anthropic and Gemini want user and assistant turns to alternate, starting with user."""
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
    account_id: str = "",
) -> str:
    async with httpx.AsyncClient(timeout=45.0) as client:
        if provider == "cloudflare":
            return await _cloudflare(client, model, api_key, account_id, system, messages)
        if provider == "openai":
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=openai_payload(model, system, messages),
            )
            _raise_for_status("openai", response)
            data = response.json()
            return str(data["choices"][0]["message"]["content"] or "")
        if provider == "google":
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key},
                json=google_payload(system, messages),
            )
            _raise_for_status("google", response)
            data = response.json()
            candidates = data.get("candidates") or []
            parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
            return "\n".join(part.get("text", "") for part in parts if part.get("text"))
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=anthropic_payload(model, system, messages),
        )
        _raise_for_status("anthropic", response)
        data = response.json()
        parts = data.get("content") or []
        texts = [part.get("text", "") for part in parts if part.get("type") == "text"]
        return "\n".join(text for text in texts if text)


async def _cloudflare(
    client: httpx.AsyncClient,
    model: str,
    api_key: str,
    account_id: str,
    system: str,
    messages: list[dict[str, str]],
) -> str:
    """Workers AI speaks the OpenAI chat format. api_key is the account's API token."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    body = {
        **openai_payload(model, system, _alternating(messages)),
        "max_tokens": BUILTIN_MAX_OUTPUT_TOKENS,
    }
    response = await client.post(
        url, headers={"Authorization": f"Bearer {api_key}"}, json={**body, **BUILTIN_EXTRA}
    )
    if response.status_code == 400:
        # A model that doesn't take the thinking switch: ask again without it.
        logger.warning("cloudflare_ai_rejected_extra body=%s", response.text[:300])
        response = await client.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=body)
    if response.status_code >= 300:
        logger.warning(
            "cloudflare_ai_failed status=%s body=%s", response.status_code, response.text[:300]
        )
    _raise_for_status("cloudflare", response)
    choice = response.json()["choices"][0]
    content = str((choice.get("message") or {}).get("content") or "")
    if not content.strip():
        logger.warning("cloudflare_ai_empty_answer finish_reason=%s", choice.get("finish_reason"))
    return content


def _raise_for_status(provider: str, response: httpx.Response) -> None:
    if response.status_code >= 300:
        raise httpx.HTTPStatusError(provider, request=response.request, response=response)
