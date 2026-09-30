from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import github_tool


class GitHubToolTests(unittest.TestCase):
    def test_wants_github(self):
        self.assertTrue(github_tool.wants_github("show open PRs on github"))
        self.assertTrue(github_tool.wants_github("latest commits on the repo"))
        self.assertFalse(github_tool.wants_github("what is a database"))

    def test_owner_can_use_requires_token(self):
        user = type("User", (), {"email": "stevebitsko@duck.com", "is_demo_locked": False})()
        with patch.object(github_tool.settings, "github_token", ""):
            self.assertFalse(github_tool.owner_can_use(user))
        with patch.object(github_tool.settings, "github_token", "ghp_test"):
            self.assertTrue(github_tool.owner_can_use(user))

    def test_assemble_status_tool_call(self):
        call = github_tool.assemble_tool_call(
            [{"index": 0, "function": {"name": "github_status", "arguments": "{}"}}]
        )
        self.assertEqual(call, {"name": "github_status"})

    def test_fetch_status_not_configured(self):
        with patch.object(github_tool.settings, "github_token", ""):
            outcome = github_tool.fetch_status()
        self.assertFalse(outcome.ok)
        self.assertIn("not set", outcome.text.lower())

    def test_default_repo(self):
        self.assertEqual(github_tool._repo(), "sb11b/Storykeep-")

    def test_open_pull_request_comments_bugbot_run(self):
        created = {"html_url": "https://github.com/sb11b/Storykeep-/pull/12", "number": 12}
        with (
            patch.object(github_tool.settings, "github_token", "ghp_test"),
            patch.object(github_tool, "_post", side_effect=[(201, created), (201, {"id": 1})]) as post,
            patch.object(github_tool, "_get", return_value=(200, [])) as get,
        ):
            url = github_tool.open_pull_request(head="cursor/senior-review", title="Review")
        self.assertEqual(url, "https://github.com/sb11b/Storykeep-/pull/12")
        self.assertEqual(get.call_args.args[0], "/repos/sb11b/Storykeep-/issues/12/comments?per_page=30")
        self.assertEqual(post.call_args_list[1].args[0], "/repos/sb11b/Storykeep-/issues/12/comments")
        self.assertEqual(post.call_args_list[1].args[1], {"body": "bugbot run"})

    def test_open_pull_request_does_not_repeat_bugbot_run(self):
        created = {"html_url": "https://github.com/sb11b/Storykeep-/pull/12", "number": 12}
        with (
            patch.object(github_tool.settings, "github_token", "ghp_test"),
            patch.object(github_tool, "_post", return_value=(201, created)) as post,
            patch.object(github_tool, "_get", return_value=(200, [{"body": "bugbot run"}])),
        ):
            github_tool.open_pull_request(head="cursor/senior-review", title="Review")
        self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
