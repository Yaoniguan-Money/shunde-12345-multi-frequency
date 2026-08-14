# GIT_HANDOFF.md

## Goal
No project state may depend on one editor/session.

## Codex first actions
```bash
git status
git rev-parse --is-inside-work-tree
gh auth status
```

If not a Git repo, initialize it on `main` and commit the bootstrap before feature development.

If GitHub auth exists, create/connect a private remote and push.

If GitHub auth is unavailable:
- keep all local commits,
- set status `REMOTE_PENDING` in `CURRENT_STATE.md`,
- leave `scripts/create_github_remote.ps1`,
- never claim remote backup is complete.

## TRAE without Git
TRAE works in the same repo, updates `TRAE_CHANGELOG.md`, and does not create a duplicate repository. Codex reviews and commits afterward.

## Current remote state (2026-08-15)

- Private repository created: `https://github.com/Yaoniguan-Money/shunde-12345-multi-frequency`
- `origin` is configured for fetch/push.
- Initial push was rejected because the authenticated OAuth token lacks the `workflow` scope required to create `.github/workflows/ci.yml`.
- Recovery:

```powershell
gh auth refresh -h github.com -s workflow
git push -u origin main
git ls-remote origin refs/heads/main
```

Do not delete the CI workflow to bypass this permission requirement.
