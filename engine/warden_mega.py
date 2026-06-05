"""The Warden Pathfinder's mega-attack (C-PF-2) + pillar refuges (C-PF-4).

The Act-1 survival mechanic and the Act IV cut/paste preview. On a cadence the
Warden telegraphs, then "tears the floor away" — every cell collapses except a
rotating handful of **pillar** refuges (`▣`), then it pastes the floor back.

Why it forces 2–4 marks: pillars are scattered, and only a random subset is safe
each cycle (revealed by the telegraph). The 3-turn warning is too short to *walk*
to whichever pillar is safe, so the player pre-marks several pillars and
`` ` ``-jumps to the lit one. One mark is never enough — the safe set rotates.

This module is pure (room + player + an rng), so the cut/strike/cadence is
unit-testable without the render/main loop. The main loop calls ``mega_tick``
once per player turn for the Pathfinder arena (``room.mega`` present); the
renderer pulses ``room.mega['safe']`` during the warning.

State lives in ``room.mega`` (a dict, seeded by ``init_mega``) and
``room.pillars`` (a set of (row, col)). See blueprints/act_3.md (L17.1).
"""
from __future__ import annotations

_MEGA_PERIOD = 8     # turns of calm between mega-attacks (cooldown)
_MEGA_WARN   = 3     # telegraph turns — the window to reach a lit pillar
_MEGA_DMG    = 4     # half-hearts lost if caught off a safe pillar (2 hearts — heavy)
_MEGA_SAFE_K = 1     # pillars that stay solid each cycle (rotates → forces many marks)


def init_mega(room, pillars) -> None:
    """Arm the mega-attack on a room. ``pillars`` is an iterable of (row, col)."""
    room.pillars = set(pillars)
    room.mega = {'phase': 'idle', 'cooldown': _MEGA_PERIOD, 'timer': 0, 'safe': set()}


def _pick_safe(room, rng) -> set:
    pillars = sorted(room.pillars)
    if not pillars:
        return set()
    k = min(_MEGA_SAFE_K, len(pillars))
    return set(rng.sample(pillars, k))


def _strike(room, player) -> list[str]:
    """Resolve the collapse: everything off a safe pillar falls; the Warden pastes
    the floor back. Goblins off the safe stones die; the player takes fall damage
    unless sheltered. The Warden itself rides its own attack (never harmed here)."""
    safe = room.mega['safe']
    for e in list(room.entities):
        if e.alive and e.kind == 'goblin' and (e.row, e.col) not in safe:
            room.kill_entity(e)
    msgs = ['The Warden tears the floor away!']
    if (player.row, player.col) in safe:
        msgs.append('You hold fast on the stone.')
    else:
        player.take_damage(_MEGA_DMG)
        msgs.append('The floor falls away beneath you!')
    msgs.append('…and the Warden slams it back into place.')
    return msgs


def mega_tick(room, player, rng) -> list[str]:
    """Advance the mega-attack one player turn. Returns banner messages (possibly
    empty). No-op on rooms without ``room.mega``."""
    m = getattr(room, 'mega', None)
    if not m:
        return []
    if m['phase'] == 'idle':
        m['cooldown'] -= 1
        if m['cooldown'] <= 0:
            m['phase'] = 'warn'
            m['timer'] = _MEGA_WARN
            m['safe'] = _pick_safe(room, rng)
            return ['THE WARDEN INHALES THE FLOOR — only the lit stones will hold!']
        return []
    # phase == 'warn'
    m['timer'] -= 1
    if m['timer'] <= 0:
        msgs = _strike(room, player)
        m['phase'] = 'idle'
        m['cooldown'] = _MEGA_PERIOD
        m['safe'] = set()
        return msgs
    return []
