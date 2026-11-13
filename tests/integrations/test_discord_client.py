import httpx
import pytest

from asta.integrations.discord.client import DiscordWebhookClient
from asta.utils.exceptions import DiscordError

WEBHOOK = "https://discord.com/api/webhooks/123/abc"


def make_client(handler, sleep=None, attempts=3):
    transport = httpx.MockTransport(handler)
    return DiscordWebhookClient(
        client=httpx.Client(transport=transport), max_attempts=attempts, sleep=sleep or (lambda _s: None)
    )


def test_successful_delivery():
    client = make_client(lambda request: httpx.Response(204))
    result = client.post(WEBHOOK, {"content": "hi"})
    assert result.ok is True
    assert result.status_code == 204
    assert result.attempts == 1


def test_invalid_webhook_is_rejected_without_a_request():
    client = make_client(lambda request: httpx.Response(204))
    result = client.post("http://example.com/hook", {})
    assert result.ok is False
    assert "invalid webhook" in result.error


def test_rate_limit_is_retried_using_retry_after():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"retry_after": 0.25})
        return httpx.Response(204)

    delays = []
    client = make_client(handler, sleep=delays.append)
    result = client.post(WEBHOOK, {})
    assert result.ok is True
    assert result.attempts == 2
    assert delays == [0.25]


def test_client_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"message": "bad payload"})

    client = make_client(handler)
    result = client.post(WEBHOOK, {})
    assert result.ok is False
    assert result.status_code == 400
    assert len(calls) == 1


def test_retryable_exhaustion_raises_discord_error():
    client = make_client(lambda request: httpx.Response(503, text="unavailable"), attempts=2)
    with pytest.raises(DiscordError):
        client.post(WEBHOOK, {})
