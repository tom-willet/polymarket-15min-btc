import asyncio

from src.polymarket_agent.review.client import ReviewClient, ReviewClientConfig
from src.polymarket_agent.review.models import ProviderResult


def test_client_retries_then_succeeds(monkeypatch) -> None:
    async def _run() -> tuple[str, int]:
        client = ReviewClient(
            ReviewClientConfig(
                provider="openai",
                model="gpt",
                timeout_seconds=1,
                max_retries=2,
            )
        )

        state = {"count": 0}

        async def fake_call_once(*, system_prompt: str, user_prompt: str) -> ProviderResult:
            state["count"] += 1
            if state["count"] < 2:
                raise RuntimeError("temporary")
            return ProviderResult(raw_text="{}")

        monkeypatch.setattr(client, "_call_once", fake_call_once)
        result = await client.run(system_prompt="s", user_prompt="u")
        return result.raw_text, state["count"]

    raw_text, attempts = asyncio.run(_run())
    assert raw_text == "{}"
    assert attempts == 2


def test_client_timeout_failure(monkeypatch) -> None:
    async def _run() -> None:
        client = ReviewClient(
            ReviewClientConfig(
                provider="openai",
                model="gpt",
                timeout_seconds=0,
                max_retries=0,
            )
        )

        async def slow_call_once(*, system_prompt: str, user_prompt: str) -> ProviderResult:
            await asyncio.sleep(0.1)
            return ProviderResult(raw_text="{}")

        monkeypatch.setattr(client, "_call_once", slow_call_once)
        try:
            await client.run(system_prompt="s", user_prompt="u")
        except RuntimeError:
            return
        raise AssertionError("expected RuntimeError")

    asyncio.run(_run())


def test_client_uses_responses_api_for_gpt5() -> None:
    client = ReviewClient(
        ReviewClientConfig(
            provider="openai",
            model="gpt-5.2",
            timeout_seconds=20,
            max_retries=0,
        )
    )
    assert client._use_responses_api() is True  # noqa: SLF001


def test_extract_text_from_responses_body() -> None:
    body = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "hello"},
                    {"type": "output_text", "text": "world"},
                ]
            }
        ]
    }
    text = ReviewClient._extract_text_from_responses_body(body)  # noqa: SLF001
    assert text == "hello\nworld"
