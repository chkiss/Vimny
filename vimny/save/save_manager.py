# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json, os, re, time
from pathlib import Path
from typing import Optional

try:                                  # POSIX only; absent on Windows
    import pwd
except ImportError:                   # pragma: no cover - platform-dependent
    pwd = None


def _home() -> Path:
    # Under sudo/doas, Path.home() is root's — resolve the invoking user's home
    # instead so saves don't land in /root. Windows has neither pwd nor sudo,
    # so the lookup is skipped and Path.home() is already correct there.
    for var in ('SUDO_USER', 'DOAS_USER'):
        user = os.environ.get(var)
        if user and user != 'root' and pwd is not None:
            try:
                return Path(pwd.getpwnam(user).pw_dir)
            except KeyError:
                break          # env names an unknown user — fall through to our own home
    return Path.home()


def _guard_writable_home() -> None:
    """Refuse to WRITE under /root — called by the write paths, never at
    import, so a root shell gets a clean message instead of every entry
    point dying before main()."""
    if _home() == Path('/root'):
        raise RuntimeError(
            'Vimny refuses to write save files to /root/. '
            'Run as a non-root user or via sudo from a normal account.'
        )

SAVE_DIR    = _home() / '.Vimny'
SAVES_DIR   = SAVE_DIR / 'saves'
LAYOUTS_DIR = SAVE_DIR / 'layouts'
SCROLLS_DIR = SAVE_DIR / 'scrolls'
DRAFTS_DIR  = SAVE_DIR / 'drafts'    # levels being authored, in the shipping format


def _slug(name: str) -> str:
    """Safe filename slug derived from a player name."""
    s = re.sub(r'[^a-zA-Z0-9 ]', '', name).strip()
    return re.sub(r'\s+', '_', s).lower() or 'unnamed'


def _path(player_name: str) -> Path:
    return SAVES_DIR / f'{_slug(player_name)}.json'


# ── Atomic write + backup-recovery reads ───────────────────────────────────────
# Every save/layout/scroll/draft byte reaches disk through here: write a tmp
# sibling, keep a `.bak` of the last good file, then rename over the target.
# A crash mid-write can therefore lose at most the newest change — never the
# whole player — and the readers below fall back to the `.bak`.

def atomic_write(path: Path, text: str) -> None:
    _guard_writable_home()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    if path.exists():
        try:
            bak = path.with_name(path.name + '.bak')
            bak.write_bytes(path.read_bytes())
        except OSError:
            pass                              # best-effort backup — never block the save
    os.replace(tmp, path)


def _read_json_or_bak(p: Path):
    """(data, error): read JSON at p, falling back to its `.bak`. Returns
    (None, reason) when both are gone or unreadable."""
    for cand in (p, p.with_name(p.name + '.bak')):
        try:
            with open(cand, encoding='utf-8') as f:
                return json.load(f), ''
        except FileNotFoundError:
            continue
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
    return None, 'could not read this file'


# ── Per-player save I/O ────────────────────────────────────────────────────────

def save_for(player_name: str, data: dict) -> None:
    atomic_write(_path(player_name), json.dumps(data, indent=2))


def load_for(player_name: str) -> Optional[dict]:
    data, _err = _read_json_or_bak(_path(player_name))
    return data


def touch_loaded(player_name: str) -> None:
    """Record that this adventurer was just loaded (for newest-loaded ordering)."""
    data = load_for(player_name)
    if data is None:
        return
    data['last_loaded'] = time.time()
    save_for(player_name, data)


def list_saves() -> list[dict]:
    """All saves sorted by most-recently-loaded first.

    Saves loaded since this ordering was introduced carry a 'last_loaded'
    epoch timestamp; older saves fall back to their file mtime.

    A save neither the file nor its `.bak` can answer is LISTED rather than
    skipped, marked '_corrupt' — a player who cannot see their adventurer
    cannot even ask what happened to them."""
    if not SAVES_DIR.exists():
        return []
    loaded: list[tuple[float, dict]] = []
    for p in sorted(SAVES_DIR.glob('*.json')):
        data, err = _read_json_or_bak(p)
        if data is None:
            loaded.append((p.stat().st_mtime if p.exists() else 0.0,
                           {'player_name': p.stem.replace('_', ' ').title(),
                            '_corrupt': err}))
            continue
        sort_key = data.get('last_loaded')
        if sort_key is None:
            try:
                sort_key = p.stat().st_mtime
            except OSError:
                sort_key = 0.0
        loaded.append((sort_key, data))
    loaded.sort(key=lambda t: -t[0])
    return [data for _, data in loaded]


# ── Progress helpers ───────────────────────────────────────────────────────────

# Non-level top-level progress fields — excluded from the slug-keyed 'progress'
# sub-dict (each gets its own JSON field below).
_SPECIAL_KEYS = {'extras', 'scrolls_seen', 'flags', 'max_hp', 'collected_hearts'}


def save_progress(progress: dict, player_name: str) -> None:
    existing = load_for(player_name) or {}
    existing['player_name']       = player_name
    existing['progress']          = {k: v for k, v in progress.items() if k not in _SPECIAL_KEYS}
    existing['extras']            = progress.get('extras', [])
    existing['scrolls_seen']      = progress.get('scrolls_seen', [])
    existing['flags']             = progress.get('flags', {})
    existing['max_hp']            = progress.get('max_hp', 6)
    existing['collected_hearts']  = progress.get('collected_hearts', [])
    save_for(player_name, existing)


def load_progress(data: Optional[dict]) -> dict:
    if data is None:
        return {}
    raw    = data.get('progress', {})
    # Level records are keyed by slug (a one-off migration converted the old
    # int-keyed saves). Load them as-is.
    result: dict = dict(raw)
    extras = data.get('extras', [])
    if extras:
        result['extras'] = extras
    scrolls_seen = data.get('scrolls_seen', [])
    if scrolls_seen:
        result['scrolls_seen'] = scrolls_seen
    flags = data.get('flags', {})
    if flags:
        result['flags'] = flags
    max_hp = data.get('max_hp', 6)
    if max_hp != 6:
        result['max_hp'] = max_hp
    collected_hearts = data.get('collected_hearts', [])
    if collected_hearts:
        result['collected_hearts'] = collected_hearts
    return result


def load_player_name(data: Optional[dict]) -> str:
    if data is None:
        return 'Normand'
    return data.get('player_name', 'Normand')


def delete_save(player_name: str) -> bool:
    """Delete the save file for player_name. Returns True if deleted."""
    p = _path(player_name)
    if p.exists():
        p.unlink()
        return True
    return False


# ── Layout I/O (admin level-design tool) ──────────────────────────────────────

def list_layouts() -> list[dict]:
    """All saved layouts sorted alphabetically by layout_name. Unreadable
    layouts are skipped — there is no UI channel to show them here."""
    if not LAYOUTS_DIR.exists():
        return []
    result = []
    for p in sorted(LAYOUTS_DIR.glob('*.json')):
        data, _err = _read_json_or_bak(p)
        if data is not None and isinstance(data, dict):
            result.append(data)
    result.sort(key=lambda d: d.get('layout_name', '').lower())
    return result


def save_layout(name: str, data: dict) -> Path:
    """Write a serialised Room dict to ~/.Vimny/layouts/<slug>.json."""
    path = LAYOUTS_DIR / f'{_slug(name)}.json'
    payload = {'layout_name': name, **data}
    atomic_write(path, json.dumps(payload, indent=2))
    return path


def delete_layout(name: str) -> bool:
    """Delete the layout file for the given layout_name. Returns True if deleted."""
    p = LAYOUTS_DIR / f'{_slug(name)}.json'
    if p.exists():
        p.unlink()
        return True
    return False


def rename_layout(old_name: str, new_name: str) -> bool:
    """Rename a saved layout (netrw R). Returns True on success."""
    new_name = new_name.strip()
    src = LAYOUTS_DIR / f'{_slug(old_name)}.json'
    if not new_name or not src.exists():
        return False
    data, _err = _read_json_or_bak(src)
    if data is None:
        return False
    data['layout_name'] = new_name
    dst = LAYOUTS_DIR / f'{_slug(new_name)}.json'
    atomic_write(dst, json.dumps(data, indent=2))
    if dst != src:
        src.unlink()
    return True


# ── Scroll text I/O (unsmudged full text, discoverable later) ─────────────────

def save_scroll_text(title: str, text: str) -> Path:
    """Write full unsmudged scroll text to ~/.Vimny/scrolls/<slug>.txt."""
    path = SCROLLS_DIR / f'{_slug(title)}.txt'
    atomic_write(path, text)
    return path
