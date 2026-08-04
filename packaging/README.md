# Packaging

How Vimny is released. Nothing here is needed to play the game or work on it.

**PyPI is the only distribution channel**, and it covers Linux and macOS
equally: `uvx vimny`, or `pipx install vimny`. uv fetches its own Python, so
neither platform needs one preinstalled.

A Homebrew tap and a Scoop bucket were written and then dropped: both install
*from* PyPI, so neither reaches a user that `uvx` doesn't, and both add a
per-release chore plus a build that has to be verified on a machine we don't
have. If someone wants to maintain a tap, `git log -- packaging/` has the
formula with working hashes.

## Why no macOS .app / Windows .exe

A frozen bundle (PyInstaller and friends) is the obvious "one-click" answer and
the wrong one here:

- Vimny is a **TUI**. A `.app` cannot render it — the bundle's only job would be
  to shell out to Terminal.app, with no control over the 80-column minimum and
  none of the user's shell configuration.
- An unsigned bundle on Apple Silicon does not warn, it **refuses**. Clearing
  that needs an Apple Developer account (~$99/yr) plus notarization in CI.
- The audience for a double-clickable icon is people who avoid terminals, who
  are not the people learning Vim.

If the goal is ever to reach genuinely non-terminal users, the answer is a
browser-playable demo, not a bundle.

## Release runbook

1. **Bump the version** in `pyproject.toml` — the single source.

2. **Build and check.**
   ```bash
   rm -rf dist build *.egg-info
   python3 -m build
   python3 -m twine check dist/*
   ```
   The sdist should be ~660 KB with no `tests/`, `docs/` or `agents/`
   (`MANIFEST.in` prunes them), and the wheel should claim exactly one
   top-level name: `vimny`.

3. **Tag and push.** `.github/workflows/release.yml` builds, runs the suite,
   checks the tag against `pyproject.toml`, and only then publishes:
   ```bash
   git tag v1.2.3 && git push origin v1.2.3
   ```
   No API token exists: the workflow uses PyPI Trusted Publishing, so GitHub
   mints a short-lived credential per run.

   **PyPI never permits re-uploading a version.** A bad release is fixed by
   bumping the version, not by overwriting.

4. **Confirm** the install a stranger would do:
   ```bash
   uvx vimny
   ```

## Trusted publishing

Configured once at <https://pypi.org/manage/account/publishing/>. All five
fields must match exactly or the credential mint fails:

| Field | Value |
|---|---|
| PyPI Project Name | `vimny` |
| Owner | `chkiss` |
| Repository name | `Vimny` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

- **`invalid-publisher`** — one of the five does not match. The workflow
  *filename* is `release.yml`, not the `name:` inside it.
- **Missing OIDC token** — the `id-token: write` permission was removed from
  the publish job.
- **`File already exists`** — bump the version and tag again.

## Don't pin wcwidth

An install is ~12 MB, over half of it `wcwidth`'s Unicode tables. `wcwidth<0.8`
cuts that to ~5.2 MB with a green suite — but blessed 1.45+ requires
`wcwidth>=0.8.1`, so the pin backtracks blessed to 1.44 and freezes it there,
trading terminal-compatibility fixes for disk. It also saves only ~215 KB of
*download*; the rest is bytecode built locally. Tried, reverted, not worth it.

## Windows

**Untested.** blessed reaches the Windows console through `jinxed`, so Vimny is
expected to work in Windows Terminal, but no one has confirmed it. `pip install
vimny` is the path to try. Treat the first Windows bug report as new
information, not a regression.
