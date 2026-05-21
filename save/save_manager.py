import json, os, pwd, re
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


def list_saves() -> list[dict]:
    """All saves sorted newest-first by file mtime."""
    if not SAVES_DIR.exists():
        return []
    result = []
    for p in sorted(SAVES_DIR.glob('*.json'), key=lambda f: -f.stat().st_mtime):
        try:
            with open(p) as f:
                result.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return result


# ── Progress helpers ───────────────────────────────────────────────────────────

def save_progress(progress: dict, player_name: str) -> None:
    existing = load_for(player_name) or {}
    existing['player_name'] = player_name
    existing['progress'] = {str(k): v for k, v in progress.items() if isinstance(k, int)}
    existing['extras']   = progress.get('extras', [])
    existing['flags']    = progress.get('flags', {})
    save_for(player_name, existing)


def load_progress(data: Optional[dict]) -> dict:
    if data is None:
        return {}
    raw    = data.get('progress', {})
    result = {int(k): v for k, v in raw.items()}
    extras = data.get('extras', [])
    if extras:
        result['extras'] = extras
    flags = data.get('flags', {})
    if flags:
        result['flags'] = flags
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
