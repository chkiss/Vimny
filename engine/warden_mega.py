"""The Warden Pathfinder's mega-attack (C-PF-2): he tears the arena floor away.

The Act-1 pressure mechanic and the Act IV cut/paste preview. On a cadence the
Warden winds up, then deletes a BAND of arena rows — simulating real Vim edits of
escalating size:

    level 0   dd          — just his own row
    level 1   d5k / d5j   — five rows up or down (random)
    level 2   dG / dgg    — everything to the top or bottom edge (random)

…then the band cycles back to dd. The torn floor stays gone for a few turns
(``room.torn`` — rendered as void, impassable, anyone caught on it falls) and then
the Warden **pastes it back** (p / P). The player survives by reading the 3-turn
telegraph and getting off the doomed rows — into the open hall around the columns.

Pure (room + player + rng), so the cadence/tear/restore is unit-testable. The main
loop calls ``mega_tick`` once per turn for the arena; the renderer flashes the warn
band and paints the torn cells. State lives in ``room.mega`` (see ``init_mega``) and
``room.torn`` (a set of (row, col)). See tests/test_warden_pathfinder.py.
"""
from __future__ import annotations

from engine.world import CellType

_MEGA_PERIOD = 7     # calm turns between attacks (cooldown)
_MEGA_WARN   = 3     # telegraph turns — the window to clear the doomed rows
_MEGA_TORN   = 3     # turns the floor stays gone before he pastes it back
_MEGA_DMG    = 4     # half-hearts lost if caught on the floor when it gives way

_VERBS = ('dd', 'd5k / d5j', 'dG / dgg')


_ECHO_SHADES = 8     # palette size in render/colors.py (impostor red variants)


def init_mega(room, bounds) -> None:
    """Arm the mega-attack. ``bounds`` = (r0, r1, c0, c1): the fight area whose
    floor can be torn (excludes the treasure room / border walls)."""
    room.mega = {'phase': 'idle', 'cooldown': _MEGA_PERIOD, 'timer': 0,
                 'band': set(), 'level': 0, 'bounds': tuple(bounds),
                 'hit_player': None, 'buried': []}
    room.torn = set()


def _warden_row(room):
    for e in room.entities:
        if e.alive and e.kind == 'warden' and e.tag == 'pathfinder':
            return e.row
    r0, r1, _, _ = room.mega['bounds']
    return (r0 + r1) // 2


def _band_rows(room, rng) -> set:
    """The rows this strike will tear, from the Warden's row outward by level."""
    r0, r1, _, _ = room.mega['bounds']
    wr = _warden_row(room)
    lvl = room.mega['level']
    if lvl == 0:                                   # dd — his row
        lo = hi = wr
    elif lvl == 1:                                 # d5k / d5j — five rows up or down
        lo, hi = (wr - 5, wr) if rng.random() < 0.5 else (wr, wr + 5)
    else:                                          # dG / dgg — to an edge
        lo, hi = (r0, wr) if rng.random() < 0.5 else (wr, r1)
    return set(range(max(r0, lo), min(r1, hi) + 1))


def _tear(room, player) -> list[str]:
    r0, r1, c0, c1 = room.mega['bounds']
    torn = {(r, c) for r in room.mega['band'] for c in range(c0, c1 + 1)
            if room.cells[r][c] in (CellType.FLOOR, CellType.CORRIDOR)}
    room.torn |= torn
    buried = []                                     # minions caught over the gap fall in…
    for e in list(room.entities):
        if e.alive and e.kind == 'goblin' and (e.row, e.col) in torn:
            buried.append(e.uid)                   # …and the Warden pastes them back later
            room.kill_entity(e)
    room.mega['buried'] = buried
    msgs = ['The Warden tears the floor away!']
    if (player.row, player.col) in torn:
        player.take_damage(_MEGA_DMG)
        room.mega['hit_player'] = (player.row, player.col)
        msgs.append('The floor gives way beneath you!')
    room.mega['phase'] = 'torn'
    room.mega['timer'] = _MEGA_TORN
    return msgs


def mega_tick(room, player, rng) -> list[str]:
    """Advance the mega-attack one turn. Returns banner messages (maybe empty)."""
    m = getattr(room, 'mega', None)
    if not m:
        return []
    m['hit_player'] = None                         # only set on a strike turn; read by the loop
    if m['phase'] == 'idle':
        m['cooldown'] -= 1
        if m['cooldown'] <= 0:
            m['phase'] = 'warn'
            m['timer'] = _MEGA_WARN
            m['band'] = _band_rows(room, rng)
            return [f'THE WARDEN WINDS UP — {_VERBS[m["level"]]}!  Off the lit rows!']
        return []
    if m['phase'] == 'warn':
        m['timer'] -= 1
        if m['timer'] <= 0:
            return _tear(room, player)
        return []
    if m['phase'] == 'torn':
        m['timer'] -= 1
        if m['timer'] <= 0:
            room.torn.clear()
            redisguised = _paste_back(room, player, rng)
            m['phase'] = 'idle'
            m['cooldown'] = _MEGA_PERIOD
            m['level'] = (m['level'] + 1) % 3      # escalate, then cycle
            if redisguised:
                return ['…and the Warden slams the floor back — his minions rise, '
                        'cloaked as Wardens once more!']
            return ['…and the Warden slams the floor back into place.']
        return []
    return []


def _paste_back(room, player, rng) -> bool:
    """The Warden pastes the floor back AND re-asserts his minions: the goblins he
    buried this strike are restored (where the cell is now clear), and EVERY live
    goblin is re-cloaked as a 2-HP false Warden (tag='echo'). So unmasked/half-cut
    minions revert — the player must finish them between strikes. Returns True if
    any goblin was (re)disguised."""
    buried = set(room.mega.get('buried', ()))
    for e in room.entities:                        # revive the ones that fell, if the cell is clear
        if e.uid in buried and not e.alive:
            if (room.is_passable(e.row, e.col)
                    and (player.row, player.col) != (e.row, e.col)
                    and room.entity_at(e.row, e.col) is None):
                e.alive = True
    room.mega['buried'] = []
    n = 0
    for e in room.entities:                        # re-cloak every live goblin into a false Warden
        if e.alive and e.kind == 'goblin':
            e.tag = 'echo'
            e.hp = e.max_hp = 2
            e.shade = rng.randrange(_ECHO_SHADES)
            n += 1
    room.rebuild_indexes()
    return n > 0
