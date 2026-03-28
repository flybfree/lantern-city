from __future__ import annotations

import json

import httpx
import pytest

from lantern_city.llm_client import (
    LLMClientError,
    LLMClientResponseError,
    OpenAICompatibleConfig,
    OpenAICompatibleLLMClient,
)


@pytest.fixture
def sample_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": "Generate a city seed."},
    ]


def test_openai_compatible_client_posts_to_v1_chat_completions(
    sample_messages: list[dict[str, str]],
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [
                    {
                        "message": {
                            "content": '{"schema_version": "1.0"}',
                        }
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(
            base_url="http://192.168.3.181:1234",
            model="nvidia/nemotron-3-nano-4b",
        ),
        http_client=http_client,
    )

    response = client.create_chat_completion(
        messages=sample_messages,
        temperature=0.2,
        max_tokens=700,
    )

    assert captured["url"] == "http://192.168.3.181:1234/v1/chat/completions"
    normalized_headers = {key.lower() for key in captured["headers"]}
    assert "authorization" not in normalized_headers
    assert captured["json"] == {
        "model": "nvidia/nemotron-3-nano-4b",
        "messages": sample_messages,
        "temperature": 0.2,
        "max_tokens": 700,
        "response_format": {"type": "text"},
    }
    assert response.content == '{"schema_version": "1.0"}'


def test_generate_json_uses_json_schema_response_format_when_schema_is_provided(
    sample_messages: list[dict[str, str]],
) -> None:
    captured: dict[str, object] = {}
    schema = {
        "type": "object",
        "properties": {"schema_version": {"type": "string"}},
        "required": ["schema_version"],
        "additionalProperties": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"schema_version": "1.0"}',
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model"),
        http_client=http_client,
    )

    parsed = client.generate_json(messages=sample_messages, schema=schema)

    assert parsed == {"schema_version": "1.0"}
    assert captured["json"] == {
        "model": "demo-model",
        "messages": sample_messages,
        "temperature": 0.2,
        "max_tokens": 2400,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "schema": schema,
            },
        },
    }


def test_openai_compatible_client_includes_bearer_auth_when_api_key_is_present(
    sample_messages: list[dict[str, str]],
) -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"ok": true}',
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(
            base_url="http://127.0.0.1:8080/v1",
            model="demo-model",
            api_key="secret-token",
        ),
        http_client=http_client,
    )

    client.create_chat_completion(messages=sample_messages)

    normalized_headers = {key.lower(): value for key, value in captured_headers.items()}
    assert normalized_headers["authorization"] == "Bearer secret-token"


@pytest.mark.parametrize(
    ("response_payload", "expected"),
    [
        pytest.param(
            {"choices": [{"message": {"content": '{"value": 1}'}}]},
            {"value": 1},
            id="plain-json-string",
        ),
        pytest.param(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "output_text", "text": '{"value": 2}'},
                            ]
                        }
                    }
                ]
            },
            {"value": 2},
            id="content-parts",
        ),
    ],
)
def test_parse_json_content_extracts_json_from_supported_response_shapes(
    response_payload: dict[str, object], expected: dict[str, object]
) -> None:
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model")
    )

    parsed = client.parse_json_content(response_payload)

    assert parsed == expected


def test_parse_json_content_raises_clear_error_for_invalid_json() -> None:
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model")
    )

    with pytest.raises(LLMClientResponseError, match="invalid JSON"):
        client.parse_json_content({"choices": [{"message": {"content": "not json"}}]})


def test_parse_json_content_rejects_non_object_json() -> None:
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model")
    )

    with pytest.raises(LLMClientResponseError, match="must be an object"):
        client.parse_json_content(
            {"choices": [{"message": {"content": '["not", "an", "object"]'}}]}
        )


@pytest.mark.parametrize(
    "response_payload",
    [
        pytest.param({}, id="missing-choices"),
        pytest.param({"choices": []}, id="empty-choices"),
        pytest.param({"choices": [{"message": {"content": None}}]}, id="missing-text-content"),
    ],
)
def test_extract_content_rejects_malformed_response_shapes(
    response_payload: dict[str, object],
) -> None:
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model")
    )

    with pytest.raises(LLMClientResponseError):
        client.extract_content(response_payload)


def test_openai_compatible_client_wraps_http_status_errors(
    sample_messages: list[dict[str, str]],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": {"message": "upstream unavailable"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model"),
        http_client=http_client,
    )

    with pytest.raises(LLMClientError, match="503"):
        client.create_chat_completion(messages=sample_messages)


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param("application/json", b'{"choices": [', id="truncated-json"),
        pytest.param("text/plain", b"plain text error", id="plain-text"),
        pytest.param("text/html", b"<html>bad gateway</html>", id="html"),
    ],
)
def test_openai_compatible_client_wraps_malformed_top_level_response_body(
    sample_messages: list[dict[str, str]],
    content_type: str,
    body: bytes,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            content=body,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = OpenAICompatibleLLMClient(
        OpenAICompatibleConfig(base_url="http://127.0.0.1:8080", model="demo-model"),
        http_client=http_client,
    )

    with pytest.raises(LLMClientResponseError, match="valid JSON"):
        client.create_chat_completion(messages=sample_messages)
