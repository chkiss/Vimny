# Packaging

How Vimny is released. Nothing here is needed to play the game or work on it.

PyPI is the only channel: `uvx vimny`, `pipx install vimny`, or `pip install
vimny`. Linux, macOS and Windows.

## Release runbook

1. **Bump the version** in `pyproject.toml` — the single source.

2. **Build and check.**
   ```bash
   rm -rf dist build *.egg-info
   python3 -m build
   python3 -m twine check dist/*
   ```
   Expect an sdist of ~660 KB with no `tests/`, `docs/` or `agents/`
   (`MANIFEST.in` prunes them), and a wheel claiming one top-level name:
   `vimny`.

3. **Tag and push.** `.github/workflows/release.yml` builds, runs the suite,
   checks the tag against `pyproject.toml`, then publishes:
   ```bash
   git tag v1.2.3 && git push origin v1.2.3
   ```

4. **Confirm.**
   ```bash
   uvx vimny
   ```

**PyPI never permits re-uploading a version.** Fix a bad release by bumping the
version.

## Trusted publishing

The workflow authenticates by OIDC — no API token exists anywhere in this repo
or its settings. Registered once at
<https://pypi.org/manage/account/publishing/>; all five fields must match or the
credential mint fails:

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

## Constraints

- **Don't pin `wcwidth<0.8`.** It cuts the ~12 MB install to ~5.2 MB, but
  blessed 1.45+ requires `wcwidth>=0.8.1`, so the pin freezes blessed at 1.44.
  Saves only ~215 KB of download; the rest is locally-built bytecode.
- **Keep the GitHub Actions current.** They are pinned by major version and go
  stale when GitHub retires a Node runtime; a stale action fails the release.

## Windows

Confirmed working by a player, 2026-08-05. `pip install vimny` then `vimny`;
from a clone, `py main.py` or `py -m vimny`.

CI does not build on Windows and nobody develops there, so it rests on one
report.

## Not doing

- **Homebrew tap / Scoop bucket** — written and dropped. Both install from
  PyPI, so neither reaches anyone `uvx` doesn't. `git log -- packaging/` has the
  formula with working hashes.
- **Frozen `.app` / `.exe`** (PyInstaller and friends) — a bundle can't render a
  TUI; it would only shell out to a terminal it doesn't control. Signing for
  Apple Silicon also needs a $99/yr developer account. For non-terminal users
  the answer is a browser build, not a bundle.
