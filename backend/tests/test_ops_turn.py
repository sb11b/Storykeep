from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import cursor_agent_tool, junior_model, railway_tool


class OpsTurnTests(unittest.TestCase):
    def test_is_ops_turn_for_github_then_deploy(self):
        msg = "Show GitHub status, then deploy Storykeep."
        self.assertTrue(junior_model.is_ops_turn(msg))
        self.assertTrue(railway_tool.wants_railway_deploy(msg))

    def test_build_turn_extras_ops_includes_ops_append(self):
        extras = junior_model.build_turn_extras(
            "Show GitHub status, then deploy Storykeep.",
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
            railway_enabled=True,
            railway_tools=True,
            github_enabled=True,
            github_tools=True,
            ops_turn=True,
        )
        joined = "\n".join(extras)
        self.assertIn("Owner ops twin turn", joined)
        self.assertIn("Storykeep web", joined)

    def test_is_ops_turn_false_for_cline_pending(self):
        self.assertFalse(junior_model.is_ops_turn("Cline pending"))
        self.assertFalse(junior_model.is_ops_turn("The Cline operator is pending"))

    def test_is_ops_turn_false_for_approve_or_deny(self):
        self.assertFalse(junior_model.is_ops_turn("Approve or Deny"))
        self.assertFalse(junior_model.is_ops_turn("Please Approve or Deny this request"))

    def test_is_ops_turn_false_for_git_add(self):
        self.assertFalse(junior_model.is_ops_turn("git add backend/app/main.py"))
        self.assertFalse(junior_model.is_ops_turn("git add ."))
        self.assertFalse(junior_model.is_ops_turn("git status"))

    def test_is_ops_turn_true_for_github_status(self):
        self.assertTrue(junior_model.is_ops_turn("Show GitHub status"))
        self.assertTrue(junior_model.is_ops_turn("What is on github?"))

    def test_is_delegate_turn_false_for_cline_pending(self):
        with patch("app.services.cursor_agent_tool.settings") as mock_settings:
            mock_settings.cursor_api_key = "test_key"
            self.assertFalse(junior_model.is_delegate_turn("Cline pending"))
            self.assertFalse(junior_model.is_delegate_turn("Approve or Deny"))

    def test_is_cline_operator_message_detects_patterns(self):
        self.assertTrue(junior_model.is_cline_operator_message("Cline pending"))
        self.assertTrue(junior_model.is_cline_operator_message("The Cline operator is pending"))
        self.assertTrue(junior_model.is_cline_operator_message("Approve or Deny"))
        self.assertFalse(junior_model.is_cline_operator_message("Start a cursor agent"))
        self.assertFalse(junior_model.is_cline_operator_message("Show GitHub status"))


    def test_pick_xhigh_for_auto_false_when_asks_for_cursor_prompt(self):
        from app.services import chat as chat_service
        msg = "Write me a Cursor prompt to fix the login bug on Railway."
        self.assertTrue(junior_model.asks_for_cursor_prompt(msg))
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

    def test_pick_xhigh_for_auto_false_when_do_not_start_cursor(self):
        from app.services import chat as chat_service
        msg = "Do not start Cursor Agent. Just give me a prompt for the Railway deploy."
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

    def test_pick_xhigh_for_auto_false_sequence_number(self):
        from app.services import chat as chat_service
        msg = "sequenced #68 pick xhigh"
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

    def test_pick_xhigh_for_auto_false_write_cline_prompt(self):
        from app.services import chat as chat_service
        msg = "write a Cline prompt to fix the bug"
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

    def test_pick_xhigh_for_auto_false_file_path(self):
        from app.services import chat as chat_service
        msg = "backend/app/services/chat.py needs review"
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

    def test_pick_xhigh_for_auto_false_cline_result(self):
        from app.services import chat as chat_service
        msg = "Cline returned the fix for login"
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

    def test_pick_xhigh_for_auto_true_explicit_start(self):
        from app.services import chat as chat_service
        # Explicit start should still return True for sequence number
        msg = "go ahead and start sequenced #68"
        self.assertTrue(chat_service.pick_xhigh_for_auto(msg))

    def test_wants_start_false_for_sequence_number(self):
        msg = "sequenced #68 pick xhigh"
        self.assertFalse(cursor_agent_tool.wants_start(msg))

    def test_wants_start_false_for_write_cline_prompt(self):
        msg = "write a Cline prompt to fix the bug"
        self.assertFalse(cursor_agent_tool.wants_start(msg))

    def test_wants_start_false_for_file_path(self):
        msg = "backend/app/services/chat.py needs review"
        self.assertFalse(cursor_agent_tool.wants_start(msg))

    def test_wants_start_false_for_cline_result(self):
        msg = "Cline returned the fix for login"
        self.assertFalse(cursor_agent_tool.wants_start(msg))

    def test_wants_start_true_explicit_start(self):
        msg = "go ahead and start sequenced #68"
        self.assertTrue(cursor_agent_tool.wants_start(msg))


if __name__ == "__main__":
    unittest.main()
