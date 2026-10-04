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

    def test_is_prompt_only_turn_matches_write_cline_prompt_do_not_start(self):
        self.assertTrue(junior_model.is_prompt_only_turn("Write a Cline prompt only. Do not start Cursor."))
        self.assertTrue(junior_model.is_prompt_only_turn("write a cline prompt. do not start cursor."))
        self.assertFalse(junior_model.is_prompt_only_turn("Write a Cline prompt to fix the login bug"))
        self.assertFalse(junior_model.is_prompt_only_turn("Start a cursor agent to fix the login bug"))

    def test_build_turn_extras_prompt_only_appends_prompt_only(self):
        extras = junior_model.build_turn_extras(
            "Write a Cline prompt only. Do not start Cursor.",
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
            search_enabled=False,
            will_search=False,
            prompt_only_turn=True,
        )
        joined = "\n".join(extras)
        self.assertIn("Steve asked you to write a Cline prompt", joined)
        self.assertNotIn("copy-paste block", joined)

    def test_build_turn_extras_normal_cursor_prompt_appends_cursor_prompt(self):
        extras = junior_model.build_turn_extras(
            "Write a Cline prompt to fix the login bug",
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
            search_enabled=False,
            will_search=False,
            prompt_only_turn=False,
        )
        joined = "\n".join(extras)
        self.assertIn("copy-paste block", joined)
        self.assertNotIn("Reply with ONLY one fenced code block", joined)

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

    def test_pick_xhigh_for_auto_false_sequence_with_explicit(self):
        from app.services import chat as chat_service
        # Sequence numbers no longer trigger xhigh, even with explicit start words.
        msg = "go ahead and start sequenced #68"
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(chat_service.resolve_reasoning_for_request(chat_service.MODEL_AUTO, "auto", msg, []), "low")

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

    def test_wants_start_false_sequence_with_explicit(self):
        # Sequence numbers return False early, even with explicit start words.
        msg = "go ahead and start sequenced #68"
        self.assertFalse(cursor_agent_tool.wants_start(msg))

    def test_pasted_git_status_stays_low(self):
        from app.services import chat as chat_service
        msg = (
            "On branch main\n"
            "Your branch is up to date with 'origin/main'.\n\n"
            "Changes to be committed:\n"
            "  (use \"git restore --staged <file>...\" to unstage)\n"
            "        modified:   backend/app/services/chat.py\n\n"
            "Changes not staged for commit:\n"
            "  (use \"git add <file>...\" to update what will be committed)\n"
            "        modified:   backend/app/services/junior_model.py\n"
        )
        self.assertTrue(junior_model.is_pasted_ops_log(msg))
        self.assertFalse(junior_model.is_ops_turn(msg))
        self.assertFalse(chat_service.pick_xhigh_for_auto(msg))
        self.assertEqual(
            chat_service.resolve_reasoning_for_request(
                chat_service.MODEL_AUTO, "auto", msg, []
            ),
            "low",
        )

    def test_on_branch_alone_is_not_pasted_ops_log(self):
        # A sentence with only "on branch" must not be treated as a pasted log.
        self.assertFalse(junior_model.is_pasted_ops_log("Show GitHub status on branch main"))
        # And it must still be an ops turn.
        self.assertTrue(junior_model.is_ops_turn("Show GitHub status on branch main"))

    def test_sentence_with_two_phrases_is_not_pasted_ops_log(self):
        # Two git phrases in a sentence are not a pasted log.
        msg = "Check GitHub status. On branch main, nothing to commit."
        self.assertFalse(junior_model.is_pasted_ops_log(msg))
        # It must still be an ops turn.
        self.assertTrue(junior_model.is_ops_turn(msg))


if __name__ == "__main__":
    unittest.main()
