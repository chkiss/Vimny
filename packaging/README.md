# Packaging

Vimny's install story, and how to cut a release. Nothing in here is needed to
*play* the game or to work on it — this directory exists for shipping.

| File | Goes where | Gives you |
|---|---|---|
| `homebrew/vimny.rb` | `chkiss/homebrew-tap` → `Formula/vimny.rb` | `brew install chkiss/tap/vimny` |
| `scoop/vimny.json` | `chkiss/scoop-bucket` → `bucket/vimny.json` | `scoop install chkiss/vimny` |

Both of these install *from PyPI*, so **publishing to PyPI is the first step and
everything else depends on it.** The name `vimny` was unclaimed as of the last
check.

## Why no macOS .app / Windows .exe

A frozen bundle (PyInstaller and friends) is the obvious "one-click" answer and
it is the wrong one here, for a reason worth writing down so it does not get
re-litigated every six months:

- Vimny is a **TUI**. A `.app` cannot render it. The bundle's entire job would be
  to shell out to Terminal.app — two windows on launch, no control over the
  80-column minimum, and none of the user's shell configuration.
- An unsigned bundle on Apple Silicon does not warn, it **refuses**. Clearing
  that needs an Apple Developer account (~$99/yr) plus notarization in CI.
- The audience for a double-clickable icon is people who avoid terminals, and
  they are not the people who want to learn Vim.

Homebrew sidesteps all of it by building on the user's machine: no signing, no
notarization, no Gatekeeper. If the goal is ever to reach genuinely
non-terminal users, the answer is a browser-playable demo, not a bundle.

## Release runbook

1. **Bump the version** in `pyproject.toml`. It is the single source — the
   formula and the manifest both track PyPI, and Scoop's `checkver` picks the
   new version up on its own.

2. **Build and check.**
   ```bash
   rm -rf dist build *.egg-info
   python3 -m build                 # produces dist/*.whl and dist/*.tar.gz
   python3 -m twine check dist/*
   ```
   The sdist should be ~660 KB and contain no `tests/`, `docs/` or `agents/`
   (`MANIFEST.in` prunes them). The wheel should contain exactly one top-level
   name: `vimny`.

3. **Publish.** Tag it and let CI do the upload — `.github/workflows/release.yml`
   builds, runs the suite, checks the tag matches `pyproject.toml`, and only
   then publishes:
   ```bash
   git tag v1.0.0 && git push origin v1.0.0
   ```
   There is no API token anywhere: the workflow uses PyPI Trusted Publishing, so
   GitHub mints a short-lived credential per run. **First release needs a
   one-time registration on PyPI — see "First publish" below.**

   PyPI does not permit re-uploading a version. If a release is bad, bump the
   version and publish again; you cannot overwrite.

4. **Refresh the Homebrew formula.** Take the new `url` and `sha256` from PyPI
   and update them at the top of `homebrew/vimny.rb`:
   ```bash
   python3 - <<'PY'
   import json, urllib.request
   d = json.load(urllib.request.urlopen("https://pypi.org/pypi/vimny/json"))
   f = next(f for f in d["urls"] if f["packagetype"] == "sdist")
   print(f'url "{f["url"]}"\nsha256 "{f["digests"]["sha256"]}"')
   PY
   ```
   Then `brew install --build-from-source ./vimny.rb` and `brew test vimny`
   locally before pushing the tap.

5. **Scoop** needs nothing on a routine release — `checkver`/`autoupdate` follow
   PyPI. Only touch it if the launcher shim changes.

## First publish (one-time)

`vimny` does not exist on PyPI yet, so there is no project to attach a publisher
to. PyPI handles this with a **pending publisher**: you register the trust
relationship first, and it activates when the first upload arrives. This means
you never create an API token at all.

1. **Make a PyPI account** (username `chkiss`) and turn on 2FA — it is mandatory
   for uploads: <https://pypi.org/account/register/>

2. **Add the pending publisher** at
   <https://pypi.org/manage/account/publishing/>, filling in exactly:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `vimny` |
   | Owner | `chkiss` |
   | Repository name | `Vimny` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

   All five must match or the mint fails at publish time with a
   `invalid-publisher` error. The environment name is the one in
   `release.yml`'s `environment: name: pypi` — GitHub creates it on first use,
   so there is nothing to set up on that side.

3. **Tag and push.**
   ```bash
   git tag v1.0.0 && git push origin v1.0.0
   ```
   Watch it at `https://github.com/chkiss/Vimny/actions`. The build job runs the
   full suite before the publish job starts.

4. **Confirm** <https://pypi.org/project/vimny/> exists, then check the install
   path a stranger would use:
   ```bash
   uvx vimny            # or: pipx install vimny
   ```

After the first successful upload the pending publisher becomes a normal one,
and every later release is just step 3.

### If it fails

- **`invalid-publisher`** — one of the five fields above does not match. The
  workflow *filename* is `release.yml`, not the `name:` inside it.
- **`Permission denied` / missing OIDC token** — the `id-token: write`
  permission on the publish job was removed.
- **`File already exists`** — PyPI never allows re-uploading a version. Bump the
  version in `pyproject.toml`, tag again.

## Don't pin wcwidth

An install is ~12 MB, over half of it `wcwidth`'s Unicode tables. `wcwidth<0.8`
cuts that to ~5.2 MB with a green suite — but blessed 1.45+ requires
`wcwidth>=0.8.1`, so the pin backtracks blessed to 1.44 and freezes it there,
trading terminal-compatibility fixes for disk. It also saves only ~215 KB of
*download*; the rest is bytecode built locally. Tried, reverted, not worth it.

## Windows

Windows is **untested**. blessed reaches the Windows console through `jinxed`,
so Vimny is expected to work in Windows Terminal, but no one has confirmed it.
The Scoop manifest says so in its `notes`, and ships it anyway so that someone
willing to try has a one-command path to trying. Treat the first Windows bug
report as new information, not a regression.
