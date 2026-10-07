import io
import json
import traceback
from decimal import Decimal
from urllib.error import HTTPError, URLError

import pytest

from newsflow.domain.editorial import EditorialGate
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.services.rewrite import EditorialRewriteBlocked, RewriteService


def envelope(text="Открыто 10 объектов"):
    return {
        "id": "resp_synthetic",
        "object": "response",
        "status": "completed",
        "model": "synthetic-model",
        "error": None,
        "incomplete_details": None,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": json.dumps({"rewritten_text": text}),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "input_tokens_details": {"cached_tokens": 40},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


class HttpFixture:
    def __init__(self, body=None, error=None):
        self.body = json.dumps(envelope() if body is None else body).encode()
        self.error = error
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append(request)
        if self.error:
            raise self.error
        return io.BytesIO(self.body)


def provider(fixture, **options):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider

    return OpenAIRewriteProvider(
        api_key="synthetic-private-key", model="synthetic-model", opener=fixture, **options
    )


def test_structured_response_uses_selected_model_no_storage_and_reports_estimated_usage():
    from newsflow.providers.openai_rewrite import TokenPrices

    fixture = HttpFixture()
    client = provider(fixture, prices=TokenPrices(Decimal(2), Decimal(1), Decimal(4)))
    assert client.rewrite("Открыто 10 объектов") == "Открыто 10 объектов"
    payload = json.loads(fixture.requests[0].data)
    assert payload["model"] == "synthetic-model"
    assert payload["store"] is False and payload["max_output_tokens"] <= 4096
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["additionalProperties"] is False
    assert payload["input"][0]["role"] == "developer"
    assert payload["input"][1]["content"] == "Открыто 10 объектов"
    assert client.last_usage.input_tokens == 100 and client.last_usage.cached_tokens == 40
    assert client.last_usage.estimated_cost_usd == Decimal("0.00024")
    assert "synthetic-private-key" not in repr(client)


@pytest.mark.parametrize(
    "mutation", ["incomplete", "refusal", "extra", "nontext", "empty", "badusage"]
)
def test_invalid_or_refused_responses_fail_closed_without_automatic_repair(mutation):
    body = envelope()
    content = body["output"][0]["content"][0]
    if mutation == "incomplete":
        body["status"] = "incomplete"
    elif mutation == "refusal":
        content.update(type="refusal", refusal="synthetic-private-key")
    elif mutation == "extra":
        content["text"] = '{"rewritten_text":"safe", "approve":true}'
    elif mutation == "nontext":
        content["text"] = '{"rewritten_text":42}'
    elif mutation == "empty":
        content["text"] = '{"rewritten_text":" "}'
    else:
        body["usage"]["input_tokens"] = True
    fixture = HttpFixture(body)
    from newsflow.providers.openai_rewrite import ProviderResponseInvalid

    with pytest.raises(ProviderResponseInvalid):
        provider(fixture).rewrite("Открыто 10 объектов")
    assert len(fixture.requests) == 1


@pytest.mark.parametrize("status", [401, 400, 429, 503])
def test_http_errors_have_safe_tracebacks_and_no_hidden_retry(status):
    fixture = HttpFixture(
        error=HTTPError("https://synthetic", status, "synthetic-private-key", {}, None)
    )
    from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid

    expected = ProviderConfigurationInvalid if status in (400, 401) else ProviderUnavailable
    with pytest.raises(expected) as captured:
        provider(fixture).rewrite("Открыто 10 объектов")
    assert "synthetic-private-key" not in "".join(traceback.format_exception(captured.value))
    assert len(fixture.requests) == 1


def test_network_error_and_oversized_payload_are_bounded_and_credential_safe():
    fixture = HttpFixture(error=URLError("synthetic-private-key"))
    with pytest.raises(ProviderUnavailable) as captured:
        provider(fixture).rewrite("Открыто 10 объектов")
    assert "synthetic-private-key" not in "".join(traceback.format_exception(captured.value))
    fixture = HttpFixture()
    fixture.body = b"x" * 262145
    from newsflow.providers.openai_rewrite import ProviderResponseInvalid

    with pytest.raises(ProviderResponseInvalid):
        provider(fixture).rewrite("source")


def test_editorial_reject_never_reaches_http_and_changed_facts_never_return_a_rewrite():
    from newsflow.services.fact_guard import FactPreservationBlocked

    fixture = HttpFixture(envelope("Открыто 20 объектов"))
    service = RewriteService(provider(fixture))
    rejected = EditorialGate().evaluate(
        text="bad", protected_entities=("Protected",), sentiment="negative", framing="hostile"
    )
    with pytest.raises(EditorialRewriteBlocked):
        service.rewrite("bad", rejected)
    assert fixture.requests == []
    with pytest.raises(FactPreservationBlocked):
        service.rewrite(
            "Открыто 10 объектов",
            EditorialGate().evaluate(
                text="ok", protected_entities=(), sentiment="neutral", framing="neutral"
            ),
        )
    assert len(fixture.requests) == 1


def test_unknown_prices_are_unknown_not_zero_and_bad_source_has_zero_calls():
    fixture = HttpFixture()
    client = provider(fixture)
    assert client.rewrite("source")
    assert client.last_usage.estimated_cost_usd is None
    with pytest.raises(ValueError):
        client.rewrite("x" * 32001)
    assert len(fixture.requests) == 1


def test_tabloid_style_changes_instructions_not_source_and_cannot_bypass_fact_guard():
    fixture = HttpFixture()
    client = provider(fixture, style="TABLOID")
    assert client.rewrite("Открыто 10 объектов") == "Открыто 10 объектов"
    payload = json.loads(fixture.requests[0].data)
    assert "tabloid" in payload["input"][0]["content"].lower()
    assert "natural" in payload["input"][0]["content"].lower()
    assert payload["input"][1]["content"] == "Открыто 10 объектов"


def test_duplicate_json_keys_are_not_accepted_as_a_valid_structured_rewrite():
    body = envelope()
    body["output"][0]["content"][0]["text"] = '{"rewritten_text":"a","rewritten_text":"b"}'
    from newsflow.providers.openai_rewrite import ProviderResponseInvalid

    with pytest.raises(ProviderResponseInvalid):
        provider(HttpFixture(body)).rewrite("source")


def test_default_http_transport_never_follows_redirects_with_authorization(monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.request import Request as RealRequest

    from newsflow.providers import openai_rewrite

    redirected = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(302)
            self.send_header("Location", "/capture")
            self.end_headers()

        def do_GET(self):
            redirected.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        openai_rewrite,
        "Request",
        lambda url, **kwargs: RealRequest(
            f"http://127.0.0.1:{server.server_port}/responses", **kwargs
        ),
    )
    try:
        with pytest.raises((ProviderUnavailable, openai_rewrite.ProviderResponseInvalid)):
            openai_rewrite.OpenAIRewriteProvider(
                api_key="synthetic-private-key", model="synthetic-model"
            ).rewrite("source")
        assert redirected == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
