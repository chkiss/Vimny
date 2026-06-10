import json, os, pwd, re, time
from pathlib import Path
from typing import Optional

def _home() -> Path:
    for var in ('SUDO_USER', 'DOAS_USER'):
        user = os.environ.get(var)
        if user and user != 'root':
            return Path(pwd.getpwnam(user).pw_dir)
    home = Path.home()
    if home == Path('/root'):
        raise RuntimeError(
            'Vimny refuses to write save files to /root/. '
            'Run as a non-root user or via sudo from a normal account.'
        )
    return home

SAVE_DIR    = _home() / '.Vimny'
SAVES_DIR   = SAVE_DIR / 'saves'
LAYOUTS_DIR = SAVE_DIR / 'layouts'
SCROLLS_DIR = SAVE_DIR / 'scrolls'


def _slug(name: str) -> str:
    """Safe filename slug derived from a player name."""
    s = re.sub(r'[^a-zA-Z0-9 ]', '', name).strip()
    return re.sub(r'\s+', '_', s).lower() or 'unnamed'


def _path(player_name: str) -> Path:
    return SAVES_DIR / f'{_slug(player_name)}.json'


# ── Per-player save I/O ────────────────────────────────────────────────────────

def save_for(player_name: str, data: dict) -> None:
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    with open(_path(player_name), 'w') as f:
        json.dump(data, f, indent=2)


def load_for(player_name: str) -> Optional[dict]:
    p = _path(player_name)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


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
    """
    if not SAVES_DIR.exists():
        return []
    loaded: list[tuple[float, dict]] = []
    for p in SAVES_DIR.glob('*.json'):
        try:
            with open(p) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
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
    """All saved layouts sorted alphabetically by layout_name."""
    if not LAYOUTS_DIR.exists():
        return []
    result = []
    for p in LAYOUTS_DIR.glob('*.json'):
        try:
            with open(p) as f:
                result.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    result.sort(key=lambda d: d.get('layout_name', '').lower())
    return result


def save_layout(name: str, data: dict) -> Path:
    """Write a serialised Room dict to ~/.Vimny/layouts/<slug>.json."""
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
    path = LAYOUTS_DIR / f'{_slug(name)}.json'
    payload = {'layout_name': name, **data}
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2)
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
    with open(src) as f:
        data = json.load(f)
    data['layout_name'] = new_name
    dst = LAYOUTS_DIR / f'{_slug(new_name)}.json'
    with open(dst, 'w') as f:
        json.dump(data, f, indent=2)
    if dst != src:
        src.unlink()
    return True


# ── Scroll text I/O (unsmudged full text, discoverable later) ─────────────────

def save_scroll_text(title: str, text: str) -> Path:
    """Write full unsmudged scroll text to ~/.Vimny/scrolls/<slug>.txt."""
    SCROLLS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCROLLS_DIR / f'{_slug(title)}.txt'
    with open(path, 'w') as f:
        f.write(text)
    return path
