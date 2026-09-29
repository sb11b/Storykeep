# StoryKeep

Review for bugs that change behavior, lose data, or break auth. Skip style, naming, and formatting.

Fix these when they show up:

- Adding to a note keeps the existing text and puts the new text after it. A save must not leave only the new paragraph.
- `/api/v1/junior/*` stays behind `require_user`. A demo account gets 403. Do not add a public route.
- A pasted git log is not a branch name. `from 0` is not a starting ref. Cloud Agent starts on `main` unless Steve named a real branch.
- A stuck Ubuntu merge is fixed with `git merge --abort`, then `git fetch github`, `git checkout main`, `git reset --hard github/main`. Do not merge into an index that already has unmerged files.
- SQL stays idempotent. No `DROP TABLE`. Do not re-run migrations in a review fix.
- Do not change the owner email.
- Do not print secrets, tokens, or `DATABASE_URL`.

Junior Cloud Agent runs open a pull request into `main` so this review runs. Do not merge steve-bitsko Cursor PR #2.

The repo is `github.com/sb11b/Storykeep-`. Production deploys from GitHub `main`.
