from unittest.mock import patch

from app.services import chat as chat_service


def test_canopy_chat_url_and_model_when_set():
    """With canopy_base_url empty, chat_url stays current. With it set, chat_url uses that base and model_name."""
    # Empty canopy_base_url keeps current behavior
    with patch.object(chat_service.settings, "canopy_base_url", ""):
        assert chat_service.chat_url() == "https://api.x.ai/v1/chat/completions"
        assert chat_service.rewrite_xai_model("grok-4.6") == "grok-4.6"

    # Set canopy_base_url switches base and model
    with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
        with patch.object(chat_service.settings, "canopy_model_name", "brain-1"):
            assert chat_service.chat_url() == "https://canopy.example.com/v1/chat/completions"
            assert chat_service.rewrite_xai_model("grok-4.6") == "brain-1"

    # canopy_model_name is ignored when canopy_base_url is empty
    with patch.object(chat_service.settings, "canopy_base_url", ""):
        with patch.object(chat_service.settings, "canopy_model_name", "brain-1"):
            assert chat_service.rewrite_xai_model("grok-4.6") == "grok-4.6"

    # key_configured treats Canopy keys as valid when base URL is set
    with patch.object(chat_service.settings, "xai_api_key", "sk-other"):
        with patch.object(chat_service.settings, "canopy_api_key", ""):
            with patch.object(chat_service.settings, "canopy_base_url", ""):
                assert not chat_service.key_configured()
            with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
                assert not chat_service.key_configured()
        with patch.object(chat_service.settings, "canopy_api_key", "canopy-secret"):
            with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
                assert chat_service.key_configured()

    # When canopy_base_url is empty, xai_api_key is used
    with patch.object(chat_service.settings, "xai_api_key", "xai-valid"):
        with patch.object(chat_service.settings, "canopy_base_url", ""):
            assert chat_service.key_configured()
            assert chat_service.require_key() == "xai-valid"
            assert chat_service.key_format_ok()

    # When canopy_base_url is set, canopy_api_key is used
    with patch.object(chat_service.settings, "canopy_api_key", "canopy-secret"):
        with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
            assert chat_service.key_configured()
            assert chat_service.require_key() == "canopy-secret"
            assert chat_service.key_format_ok()

    # When canopy_base_url is set, _xai_key() still returns xai_api_key and _xai_responses_url() stays xAI
    with patch.object(chat_service.settings, "xai_api_key", "xai-test-key"):
        with patch.object(chat_service.settings, "canopy_api_key", "canopy-secret"):
            with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
                # Normal chat still uses Canopy
                assert chat_service.require_key() == "canopy-secret"
                assert chat_service.chat_url() == "https://canopy.example.com/v1/chat/completions"
                assert chat_service.responses_url() == "https://canopy.example.com/v1/responses"
                # But _xai_key() and _xai_responses_url() always use xAI
                assert chat_service._xai_key() == "xai-test-key"
                assert chat_service._xai_responses_url() == "https://api.x.ai/v1/responses"

    # When xai_chat_url is custom, _xai_responses_url() derives from it
    with patch.object(chat_service.settings, "xai_chat_url", "https://custom.x.ai/v1/chat/completions"):
        with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
            assert chat_service._xai_responses_url() == "https://custom.x.ai/v1/responses"

    # When canopy_base_url is set, normal chat strips tools from completions payload
    with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
        with patch.object(chat_service.settings, "canopy_model_name", "brain-1"):
            payload = chat_service.build_chat_completions_payload(
                messages=[{"role": "user", "content": "hello"}],
                model="grok-4.6",
                reasoning_effort="low",
                max_tokens=1200,
                stream=False,
                temperature=0.6,
                tools=[{"type": "web_search"}, {"type": "code_interpreter"}],
            )
            assert "tools" not in payload

    # _strip_canopy_tool_markup removes Kimi tool-use tokens
    assert chat_service._strip_canopy_tool_markup("Hello world") == "Hello world"
    assert chat_service._strip_canopy_tool_markup(
        "Hello <|tool_call_begin|>{'query': 'test'}<|tool_call_end|>world"
    ) == "Hello world"
    assert chat_service._strip_canopy_tool_markup(
        "Hello <|tool_call_begin|>{'query': 'test'}"
    ) == "Hello"
    assert chat_service._strip_canopy_tool_markup(
        "Text<|tool_call_begin|>{'q': 'x'}<|tool_call_end|>More"
    ) == "TextMore"


    # Unset at end (patcher context managers handle it)

def test_strip_printed_kimi_leak():
    from app.services import chat as chat_service
    leaked = (
        "The third screen is Stories.</think>"
        "For the Dodgers score, let me look that up."
        "<|tool_calls_section_begin|>"
        "<|tool_call_begin|>functions.web_search:0"
        "<|tool_call_argument_begin|>"
        '{"query": "Dodgers game yesterday score October 3 2026"}'
        "<|tool_call_end|>"
        "<|tool_calls_section_end|>"
    )
    assert chat_service._strip_canopy_tool_markup(leaked) == "The third screen is Stories.For the Dodgers score, let me look that up."

