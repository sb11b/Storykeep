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
        with patch.object(chat_service.settings, "canopy_base_url", ""):
            assert not chat_service.key_configured()
        with patch.object(chat_service.settings, "canopy_base_url", "https://canopy.example.com/v1"):
            assert chat_service.key_configured()

    # Unset at end (patcher context managers handle it)
