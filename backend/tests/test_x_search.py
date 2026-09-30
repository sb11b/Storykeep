import unittest
from unittest.mock import patch

from app.services import x_search
from app.services.chat import SYSTEM_PROMPT
from app.services.junior_model import build_turn_extras


class XLookupTests(unittest.TestCase):
    def test_posts_and_video_urls_match(self):
        self.assertTrue(x_search.wants_x_lookup("what are people saying on X about the game"))
        self.assertTrue(x_search.wants_x_lookup("https://x.com/story/status/1"))
        self.assertTrue(x_search.wants_x_video("watch this video https://x.com/story/status/1"))
        self.assertFalse(x_search.wants_x_video("what are people saying on X"))
        self.assertFalse(x_search.wants_x_lookup("hello"))
        self.assertFalse(x_search.wants_x_lookup("what time are the mlb games"))
        self.assertFalse(x_search.wants_x_lookup("what is x in algebra"))

    def test_missing_key_is_fatal(self):
        with patch.object(x_search.settings, "xai_api_key", ""):
            outcome = x_search.lookup("posts on X about homework")
        self.assertTrue(outcome.fatal)
        self.assertEqual(outcome.detail, x_search.UI_UNAVAILABLE)
        self.assertIn("HTTP 503", x_search.format_for_model(outcome))

    def test_lookup_sends_both_tools(self):
        captured: dict = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "output_text": "People are posting about the game.",
                    "citations": ["https://x.com/story/status/9"],
                    "output": [{"type": "view_x_video_call"}],
                }

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json, headers):
                captured["url"] = url
                captured["json"] = json
                captured["auth"] = headers.get("Authorization")
                return FakeResponse()

        with (
            patch.object(x_search.settings, "xai_api_key", "xai-test-key"),
            patch.object(x_search.settings, "xai_chat_url", "https://api.x.ai/v1/chat/completions"),
            patch("app.services.x_search.httpx.Client", FakeClient),
        ):
            outcome = x_search.lookup("watch this video https://x.com/story/status/9")
        tools = captured["json"]["tools"]
        self.assertEqual(tools, [{"type": "x_search", "enable_video_understanding": True}])
        self.assertNotIn("view_x_video", [item.get("type") for item in tools])
        self.assertNotIn("xai-test-key", str(outcome))
        self.assertTrue(outcome.watched_video)
        self.assertIn("https://x.com/story/status/9", outcome.citations)
        text = x_search.format_for_model(outcome)
        self.assertIn("view_x_video ran", text)
        self.assertIn("https://x.com/story/status/9", text)

    def test_plain_x_search_omits_video_tool(self):
        captured: dict = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "A post."}]}]}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, json, headers):
                captured["json"] = json
                return FakeResponse()

        with (
            patch.object(x_search.settings, "xai_api_key", "xai-test-key"),
            patch("app.services.x_search.httpx.Client", FakeClient),
        ):
            outcome = x_search.lookup("what are people saying on X about the game")
        self.assertEqual(captured["json"]["tools"], [{"type": "x_search"}])
        self.assertFalse(outcome.watched_video)
        self.assertIn("A post.", outcome.text)

    def test_prompt_no_longer_forbids_x(self):
        self.assertIn("x_search", SYSTEM_PROMPT)
        self.assertIn("view_x_video", SYSTEM_PROMPT)
        self.assertNotIn("cannot search X", SYSTEM_PROMPT)

    def test_turn_extra_mentions_tools(self):
        extras = build_turn_extras(
            "posts on X",
            memory_block=None,
            chats_enabled=False,
            index_block=None,
            read_meta=None,
            unread_catalog=None,
            calendar_connected=False,
            calendar_tools=False,
            mail_connected=False,
            mail_unread=False,
            unread_mail_md=None,
            search_enabled=True,
            will_search=False,
            will_x=True,
        )
        self.assertTrue(any("view_x_video" in item for item in extras))
