# StoryKeep

Review this diff the way a senior engineer would. Report bugs that change behavior, lose data, or break auth. Skip style, naming, and formatting.

A high-severity finding is one that drops user text, exposes a private route, prints a secret, or pushes to `main`.

## Checklist

- Adding to a note keeps the existing text and puts the new text after it. A save must not leave only the new paragraph.
- `/api/v1/junior/*` stays behind `require_user`. A demo account gets 403. Do not add a public route.
- A pasted git log is not a branch name. `from 0` is not a starting ref. A Cloud Agent starts on `main` unless Steve named a real branch.
- A stuck Ubuntu merge is fixed with `git merge --abort`, then `git fetch github`, `git checkout main`, `git reset --hard github/main`. Do not merge into an index that already has unmerged files.
- SQL stays idempotent. No `DROP TABLE`. Do not re-run migrations in a review fix.
- Do not change the owner email (`angry.tune8751@fastmail.com`).
- Do not print secrets, tokens, or `DATABASE_URL`.
- The change opens a pull request into `main` and does not merge it. It does not push to `main`.
- Do not merge steve-bitsko Cursor PR #2.
- Tests cover the behavior that changed. A review fix that only restyles code is out of scope.

For each finding, name the file, the broken behavior, and the fix.

The repo is `github.com/sb11b/Storykeep-`. Production deploys from GitHub `main`.
