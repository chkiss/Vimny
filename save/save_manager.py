import json, re
from pathlib import Path
from typing import Optional

SAVE_DIR  = Path.home() / '.Vimny'
SAVES_DIR = SAVE_DIR / 'saves'


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
    existing['progress'] = {str(k): v for k, v in progress.items()}
    save_for(player_name, existing)


def load_progress(data: Optional[dict]) -> dict:
    if data is None:
        return {}
    raw = data.get('progress', {})
    return {int(k): v for k, v in raw.items()}


def load_player_name(data: Optional[dict]) -> str:
    if data is None:
        return 'Normand'
    return data.get('player_name', 'Normand')
