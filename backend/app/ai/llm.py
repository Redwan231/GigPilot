"""GLM 5.3 Flash client via OpenAI-compatible endpoint (04_TRD §4.2).

JSON mode, timeouts, retries with jitter, writes ai_usage on every call."""

import json
import logging
import random

from openai import AsyncOpenAI

from app.config import settings
from app.db.models.ai_usage import AiUsage
from app.db.session import system_session

log = logging.getLogger(__name__)

# Pricing (04_TRD §4.2): input $0.05/M, output $0.45/M
_INPUT_COST_PER_TOKEN = 0.05 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 0.45 / 1_000_000


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=30.0,
        max_retries=0,
    )


async def chat_json(
    messages: list[dict[str, str]],
    *,
    user_id: str | None = None,
    operation: str = "score",
    temperature: float = 0.3,
    max_tokens: int = 512,
    retries: int = 2,
) -> dict:
    """Send a chat completion with JSON mode. Retries with jitter on failure.
    Writes ai_usage row on success. Returns parsed JSON dict."""
    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            content = choice.message.content or "{}"
            parsed = json.loads(content)

            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            cost = (
                input_tokens * _INPUT_COST_PER_TOKEN
                + output_tokens * _OUTPUT_COST_PER_TOKEN
            )

            async with system_session() as session:
                session.add(
                    AiUsage(
                        user_id=user_id,
                        operation=operation,
                        model=settings.llm_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost,
                    )
                )

            return parsed

        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                wait = (2**attempt) + random.uniform(0, 1)
                log.warning(
                    "LLM call attempt %d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    exc,
                    wait,
                )
                import asyncio

                await asyncio.sleep(wait)

    raise last_exc  # type: ignore[misc]


async def chat_text(
    messages: list[dict[str, str]],
    *,
    user_id: str | None = None,
    operation: str = "draft",
    temperature: float = 0.6,
    max_tokens: int = 1024,
    retries: int = 2,
) -> str:
    """Send a chat completion (plain text mode). Retries with jitter.
    Writes ai_usage row on success. Returns the text content."""
    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""

            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            cost = (
                input_tokens * _INPUT_COST_PER_TOKEN
                + output_tokens * _OUTPUT_COST_PER_TOKEN
            )

            async with system_session() as session:
                session.add(
                    AiUsage(
                        user_id=user_id,
                        operation=operation,
                        model=settings.llm_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost,
                    )
                )

            return content

        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                wait = (2**attempt) + random.uniform(0, 1)
                log.warning("LLM text call attempt %d failed; retrying", attempt + 1)
                import asyncio

                await asyncio.sleep(wait)

    raise last_exc  # type: ignore[misc]
