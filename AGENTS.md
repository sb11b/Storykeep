# Storykeep

Repo: `github.com/sb11b/Storykeep-`. Production deploys from GitHub `main`.

## How to change this repo

- Stay on this repository. Do not create a new project.
- Start from current GitHub `main`. Commit on a `cursor/*` branch.
- Open a pull request into `main`. Do not merge it. Do not push to `main`.
- Do not merge steve-bitsko Cursor PR #2.
- Before every `git push`, review the diff with the senior-reviewer subagent in `.cursor/agents/senior-reviewer.md`. Wait for that review. Put the findings in the pull request body. Do not push when it reports a high-severity issue.
- After the pull request is open, leave it for CodeRabbit. Bugbot is off. Do not comment `bugbot run`.

## Cursor automations

- Bugbot is off. Do not ask Steve to turn it on. Do not comment `bugbot run`.
- CodeRabbit reviews pull requests on this repo. The setup is Chill, comments only, no Slack, no summaries.
- Security and PR Routing & Approval are enabled. Do not ask Steve to enable them again.
- Security reviews the pull request. The scheduled Vulnerability Scanner stays off.
- PR Routing & Approval may assign reviewers. Automatic approval stays off. Do not approve the pull request.
- Rollouts stays disabled. Do not enable it and do not add deploy hooks for it.

## Rules that do not change

- Adding to a note keeps the original text and appends the new text.
- `/api/v1/junior` stays behind `require_user`. A demo account gets 403. Do not add a public route.
- A pasted git log is not a branch name. `from 0` is not a starting ref.
- A stuck Ubuntu merge is `git merge --abort`, then `git fetch github`, `git checkout main`, `git reset --hard github/main`.
- SQL stays idempotent. No `DROP TABLE`. Do not re-run migrations.
- Do not change the owner email (`angry.tune8751@fastmail.com`).
- Do not print secrets, tokens, or `DATABASE_URL`.
