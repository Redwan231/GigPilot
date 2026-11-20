"""P2-7: LLM client — mock completion + ai_usage written."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import func, select

from app.ai.llm import chat_json, chat_text
from app.db.models.ai_usage import AiUsage
from app.db.session import system_session


def _mock_response(content: str, input_tokens: int = 10, output_tokens: int = 20):
    usage = MagicMock()
    usage.prompt_tokens = input_tokens
    usage.completion_tokens = output_tokens
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


@pytest.mark.asyncio
async def test_chat_json_parses_and_logs_usage(clean_db) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_response('{"score": 85, "confidence": 0.9}')
    )

    with patch("app.ai.llm._get_client", return_value=mock_client):
        result = await chat_json(
            [{"role": "user", "content": "test"}],
            user_id=None,
            operation="score",
        )

    assert result["score"] == 85
    assert result["confidence"] == 0.9

    async with system_session() as session:
        count = await session.scalar(select(func.count()).select_from(AiUsage))
        assert count == 1
        row = await session.scalar(select(AiUsage))
        assert row.operation == "score"
        assert row.input_tokens == 10
        assert row.output_tokens == 20
        assert row.cost_usd > 0


@pytest.mark.asyncio
async def test_chat_text_returns_content(clean_db) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_mock_response("Draft proposal text here.")
    )

    with patch("app.ai.llm._get_client", return_value=mock_client):
        result = await chat_text(
            [{"role": "user", "content": "draft"}],
            operation="draft",
        )

    assert "Draft proposal" in result

    async with system_session() as session:
        row = await session.scalar(select(AiUsage))
        assert row.operation == "draft"


@pytest.mark.asyncio
async def test_chat_json_retries_on_failure(clean_db) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            ConnectionError("timeout"),
            _mock_response('{"ok": true}'),
        ]
    )

    with patch("app.ai.llm._get_client", return_value=mock_client):
        result = await chat_json(
            [{"role": "user", "content": "test"}],
            retries=1,
        )

    assert result["ok"] is True
    assert mock_client.chat.completions.create.call_count == 2
