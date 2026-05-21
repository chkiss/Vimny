#!/usr/bin/env python3
"""Vimny — entry point and main game loop."""
from __future__ import annotations
import sys, random, time, argparse
from blessed import Terminal
import render.colors as C
from render.renderer import render_all
import render.symbols as S
from render.utils import inner_w as _iw
from render.overworld import render_overworld
from render.title import render_title, render_save_select, select_quote, MENU_ITEMS as _TITLE_MENU, NAME_MAX as _NAME_MAX
from engine.player import Player
from engine.modes import Mode
from engine.budget import Budget
from engine.vim_parser import parse
from engine.command_guard import action_allowed as _action_allowed, guard_message as _guard_message
from engine.world import Entity, CellType, RuneCluster, Dungeon
from engine.motion import apply_motion, move_player, _apply_esc, _reveal_from, _cell_char
from engine.editor import (
    _merge_adjacent_runes, _ed_cut, _ed_snapshot, _ed_restore, _ed_subst,
    _ed_paste, _ed_row_items, _ed_clear_row, _ed_range_items, _ed_delete_range,
    _clip_desc, _serialize_room, _deserialize_room,
)
from generation.dungeon_gen import build_dungeon_0, build_dungeon_1, build_dungeon_1_1, build_dungeon_2, build_dungeon_3, build_dungeon_4, build_dungeon_5, build_dungeon_dummy
from content.levels import LEVELS, is_unlocked, is_reliquary, known_commands as _known_commands
import save.save_manager as SM


_WATER_SETTLE_SECS = 60   # stop animating water after this many idle seconds

# Explosion damage in half-hearts by Manhattan distance from centre
_EXPL_DAMAGE = {0: 3, 1: 3, 2: 2, 3: 1}   # 0-1: 1.5♥  2: 1♥  3: 0.5♥

_ALERT_RADIUS           = 5   # Manhattan dist at which goblins start chasing
_ATTACK_RADIUS          = 1   # Manhattan dist at which goblins attack each turn
_WARDEN_SUMMON_INTERVAL = 6   # turns between warden summons
_MSG_ROTATE_TTL         = 10  # ticks per combat message (~1 s at 0.1 s inkey timeout)

def _chest_loot(kind: str) -> str:
    """Return the item type yielded by looting a chest."""
    if kind == 'chest_key':
        return 'key'
    if kind == 'chest_scroll':
        return 'scroll'
    r = random.random()
    if r < 0.5:
        return 'key'
    if r < 0.8:
        return 'scroll'
    return 'heart'

# ── Scroll overlays ───────────────────────────────────────────────────────────

def _show_reliquary_scroll(term: Terminal, iw: int, game_h: int) -> None:
    """Amber floating box showing the reliquary chest poem. Blocks until any key."""
    BOX_IW = 54
    BOX_BW = BOX_IW + 4

    box_bg  = term.on_color_rgb(10, 8, 2)
    amber_b = term.color_rgb(220, 175, 35) + term.bold
    amber   = term.color_rgb(220, 175, 35)
    dim     = term.color_rgb(100, 80, 15)
    hi      = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal

    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    row_off = 3 + max(0, (game_h - 12) // 2)

    bdr = box_bg + amber_b
    inn = box_bg

    def center_row(vis: int, colored: str) -> str:
        lpad = (BOX_IW - vis) // 2
        rpad = BOX_IW - vis - lpad
        return (bdr + '║ ' + rst +
                inn + ' ' * lpad + colored + inn + ' ' * rpad +
                bdr + ' ║' + rst)

    blank = center_row(0, '')

    T = '◈   A Scroll   ◈'
    title = center_row(len(T), hi + T + rst)

    l1 = "You've already learned the lesson from this chest —"
    line1 = center_row(len(l1), amber + l1 + rst)

    l2 = "x doesn't just cut, it saves to your vest!"
    line2 = center_row(len(l2),
                       hi + 'x' + rst + inn + amber + l2[1:] + rst)

    l3 = "You have joined the halls of adventurers who possess"
    line3 = center_row(len(l3), amber + l3 + rst)

    l4 = 'the " buffer.'
    line4 = center_row(len(l4),
                       amber + 'the ' + rst + inn + hi + '"' + rst + inn + amber + ' buffer.' + rst)

    AK     = '[ any key ]'
    footer = center_row(len(AK), dim + AK + rst)

    sep_h = '═' * (BOX_IW + 2)
    lines = [
        bdr + '╔' + sep_h + '╗' + rst,
        blank,
        title,
        blank,
        line1,
        line2,
        line3,
        line4,
        blank,
        footer,
        blank,
        bdr + '╚' + sep_h + '╝' + rst,
    ]

    for i, line in enumerate(lines):
        print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

    term.inkey()


def _show_register_tutorial(term: Terminal, iw: int, game_h: int) -> None:
    """Amber floating box explaining the \" register. Blocks until any key."""
    BOX_IW = 54               # visible inner width
    BOX_BW = BOX_IW + 4      # ║[sp][54][sp]║

    box_bg  = term.on_color_rgb(10, 8, 2)
    amber_b = term.color_rgb(220, 175, 35) + term.bold
    amber   = term.color_rgb(220, 175, 35)
    dim     = term.color_rgb(100, 80, 15)
    hi      = term.color_rgb(255, 220, 60) + term.bold
    rst     = term.normal

    col_off = max(1, (iw + 2 - BOX_BW) // 2)
    row_off = 3 + max(0, (game_h - 17) // 2)

    bdr = box_bg + amber_b   # border: dark bg + bold amber fg
    inn = box_bg              # inner: dark bg only (fg unchanged)

    def row(vis: int, colored: str) -> str:
        """Build one box content line. vis = visible width of colored."""
        return (bdr + '║ ' + rst +
                inn + colored +
                inn + ' ' * max(0, BOX_IW - vis) +
                bdr + ' ║' + rst)

    blank = row(0, '')

    T   = '◈   The Unnamed Register   ◈'
    lT  = (BOX_IW - len(T)) // 2
    rT  = BOX_IW - len(T) - lT
    title = row(BOX_IW, ' ' * lT + hi + T + rst + ' ' * rT)

    def kv(key: str, desc: str) -> str:
        d25   = desc.ljust(25)[:25]
        sep   = '  ────→  '   # 9 chars
        suf   = 'lands in  '  # 10 chars
        sym   = '"'
        # visible = 4 + 1 + 9 + 25 + 10 + 1 = 50
        colored = ('    ' + hi + key + rst +
                   inn + dim + sep + d25 + suf + rst +
                   inn + amber + sym + rst + inn)
        return row(50, colored)

    def dim_row(s: str) -> str:
        return row(len(s), dim + s + rst)

    # " line — no mention of p (not yet known); tease that a use exists
    p_plain = ' "  holds all you delete — there must be some use...'
    p_col   = (dim + ' ' + rst +
               inn + amber + '"' + rst +
               inn + dim + '  holds all you delete — there must be some use...' + rst + inn)
    p_row   = row(len(p_plain), p_col)

    AK   = '[ any key ]'
    lAK  = (BOX_IW - len(AK)) // 2
    footer = row(BOX_IW, ' ' * lAK + dim + AK + rst + ' ' * (BOX_IW - len(AK) - lAK))

    sep_h = '═' * (BOX_IW + 2)
    lines = [
        bdr + '╔' + sep_h + '╗' + rst,
        blank,
        title,
        blank,
        dim_row('  Scrawled on the scroll: a revelation.'),
        blank,
        kv('x', 'deletes a character  '),
        kv('d', 'deletes a range      '),
        kv('c', 'changes text         '),
        blank,
        p_row,
        blank,
        dim_row('  Your cuts are visible in the statusline.'),
        blank,
        footer,
        blank,
        bdr + '╚' + sep_h + '╝' + rst,
    ]

    for i, line in enumerate(lines):
        print(term.move_yx(row_off + i, col_off) + line, end='', flush=True)

    term.inkey()   # consume keypress; already inside term.cbreak()


def _unlock_animation(term: Terminal, room, player,
                      door_r: int, door_c: int, iw: int, game_h: int) -> None:
    """Flash key icon at door position, then blank it — door + key both vanish."""
    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
    vc_start = max(0, min(player.col - iw    // 2,  room.cols - iw))
    scr_r = door_r - vr_start + 3
    scr_c = door_c - vc_start + 1
    if not (0 <= scr_r < term.height and 0 <= scr_c < iw):
        return
    gold = C.key_fg()
    rst  = term.normal
    fbg  = C.floor_bg()
    print(term.move_yx(scr_r, scr_c) + fbg + gold + S.KEY + rst, end='', flush=True)
    time.sleep(0.35)
    print(term.move_yx(scr_r, scr_c) + fbg + '  ' + rst, end='', flush=True)
    time.sleep(0.08)


# ── Animations ────────────────────────────────────────────────────────────────

def _explosion_animation(term, room, expl_r, expl_c, scr_r, scr_c, iw, game_h):
    """Expanding * rings centred on screen position (scr_r, scr_c) = room (expl_r, expl_c).

    Walls stop the visual rings (no * drawn on a wall cell) but do not shift
    or re-centre the pattern — each ring remains anchored to (expl_r, expl_c).
    """
    # Each frame: {distance: color}  — inner rings dim as the wave expands outward
    frames = [
        ({0: term.bold + term.bright_white},                                         0.05),
        ({0: term.color_rgb(255, 200, 50) + term.bold,
          1: term.bold + term.bright_white},                                          0.07),
        ({0: term.color_rgb(220,  80, 10),
          1: term.color_rgb(255, 170, 40) + term.bold,
          2: term.bold + term.bright_white},                                          0.08),
        ({0: term.color_rgb(120,  30,  5),
          1: term.color_rgb(200,  70, 15),
          2: term.color_rgb(255, 140, 30) + term.bold,
          3: term.bold + term.bright_white},                                          0.10),
        ({1: term.color_rgb( 80,  15,  0),
          2: term.color_rgb(160,  50, 10),
          3: term.color_rgb(230, 110, 25) + term.bold},                              0.10),
    ]
    for colors, delay in frames:
        max_d = max(colors)
        for dr in range(-max_d, max_d + 1):
            for dc in range(-max_d, max_d + 1):
                dist = abs(dr) + abs(dc)
                color = colors.get(dist)
                if not color:
                    continue
                rr, rc = expl_r + dr, expl_c + dc
                if not (0 <= rr < room.rows and 0 <= rc < room.cols):
                    continue
                if room.cells[rr][rc] == CellType.WALL:
                    continue
                sr, sc = scr_r + dr, scr_c + dc
                if not (3 <= sr < 3 + game_h and 1 <= sc < 1 + iw):
                    continue
                print(term.move_yx(sr, sc) + color + '*' + term.normal,
                      end='', flush=True)
        time.sleep(delay)


def _void_fall_animation(term, screen_r, screen_c):
    frames = [
        (term.color_rgb(110, 60, 160) + term.bold, '@'),
        (term.color_rgb(80,  30, 120) + term.bold, '◉'),
        (term.color_rgb(60,  20,  90),              'o'),
        (term.color_rgb(40,  10,  60),              '·'),
        (term.color_rgb(20,   5,  30),              '˙'),
        (term.normal,                               ' '),
    ]
    for color, sym in frames:
        print(term.move_yx(screen_r, screen_c) + color + sym + term.normal,
              end='', flush=True)
        time.sleep(0.12)


def _drown_animation(term, screen_r, screen_c):
    frames = [
        (term.color_rgb(60, 140, 210) + term.bold, '@'),
        (term.color_rgb(40, 100, 175) + term.bold, '◉'),
        (term.color_rgb(20,  70, 145),              'o'),
        (term.color_rgb(10,  45, 110),              '·'),
        (term.color_rgb( 5,  25,  75),              '˙'),
        (term.normal,                               ' '),
    ]
    for color, sym in frames:
        print(term.move_yx(screen_r, screen_c) + color + sym + term.normal,
              end='', flush=True)
        time.sleep(0.12)


def _win_animation(term, iw):
    rows_text = [
        '✦  ★  ✦  ★  ✦  ★  ✦  ★  ✦',
        ' D U N G E O N   C L E A R E D ',
        '★  ✦  ★  ✦  ★  ✦  ★  ✦  ★',
    ]
    palettes = [
        (term.bright_yellow + term.bold, term.bright_green  + term.bold),
        (term.bright_white  + term.bold, term.bright_yellow + term.bold),
        (term.bright_green  + term.bold, term.bright_white  + term.bold),
    ]
    center = term.height // 2 - 1
    for frame in range(16):
        star_col, text_col = palettes[frame % 3]
        for i, line in enumerate(rows_text):
            pad     = max(0, (iw - len(line)) // 2)
            content = ' ' * pad + line + ' ' * max(0, iw - pad - len(line))
            color   = text_col if i == 1 else star_col
            print(term.move_yx(center + i, 1) + color + content + term.normal,
                  end='', flush=True)
        time.sleep(0.1)


def _fireworks_animation(term, iw):
    h       = term.height
    bursts  = [
        (h // 4,     iw // 6),
        (h // 3,     iw * 5 // 6),
        (h // 2 - 1, iw // 2),
        (h * 2 // 3, iw // 4),
        (h * 2 // 3, iw * 3 // 4),
    ]
    star_chars = ['*', '+', '·', '˙', ' ']
    offsets    = [(0,-2),(0,2),(-1,-1),(-1,0),(-1,1),(1,-1),(1,0),(1,1),(-2,0),(2,0)]
    colors     = [
        term.color_rgb(255, 220,  60) + term.bold,
        term.color_rgb(255, 100, 100) + term.bold,
        term.color_rgb(100, 255, 150) + term.bold,
        term.color_rgb(120, 180, 255) + term.bold,
        term.color_rgb(255, 140, 255) + term.bold,
    ]
    banner_rows = [
        '✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦',
        '  V I M   M A S T E R Y   A C H I E V E D  ',
        '  Par excellence! Your keystrokes are art.  ',
        '★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★ ✦ ★',
    ]
    banner_palettes = [
        (term.bright_yellow + term.bold, term.bright_white  + term.bold, term.color_rgb(180,255,180) + term.bold),
        (term.bright_white  + term.bold, term.bright_green  + term.bold, term.bright_yellow + term.bold),
        (term.bright_green  + term.bold, term.bright_yellow + term.bold, term.bright_white  + term.bold),
    ]
    center = h // 2 - 2
    for frame in range(20):
        sc = star_chars[min(frame // 4, len(star_chars) - 1)]
        for bi, (br, bc_) in enumerate(bursts):
            color = colors[bi % len(colors)]
            for dr, dc in offsets:
                rr = br + dr * (1 + frame // 5)
                cc = bc_ + dc * (1 + frame // 4)
                if 3 <= rr < h - 3 and 1 <= cc < iw:
                    print(term.move_yx(rr, cc) + color + sc + term.normal,
                          end='', flush=True)
        sp, tc, mc = banner_palettes[frame % 3]
        for i, line in enumerate(banner_rows):
            pad     = max(0, (iw - len(line)) // 2)
            content = ' ' * pad + line + ' ' * max(0, iw - pad - len(line))
            col     = tc if i == 1 else (mc if i == 2 else sp)
            print(term.move_yx(center + i, 1) + col + content + term.normal,
                  end='', flush=True)
        time.sleep(0.1)


# ── Small helpers ──────────────────────────────────────────────────────────────

_ATTACK_FLASH_TTL = 3   # no-key ticks per frame (~0.3 s at 0.1 s timeout)

_SPEAR_DIRS = {
    ( 1,  0): '↓',   # attacker above → attack comes downward
    (-1,  0): '↑',   # attacker below → attack comes upward
    ( 0,  1): '→',   # attacker left  → attack comes rightward
    ( 0, -1): '←',   # attacker right → attack comes leftward
}


def _keystroke_cost(count: int, motion: str = '') -> int:
    base = 1 if count == 1 else len(str(count)) + 1
    # multi-character motions: one extra keypress per extra character required
    if motion in ('f', 'F', 't', 'T', 'gg'):
        base += 1
    return base


def _calc_stars(won: bool, budget: Budget, room, player, level: int = 0) -> int:
    if not won:
        return 0
    if is_reliquary(level):
        return 0
    par = room.par or 0
    if par > 0 and budget.spent <= par and player.hp >= 6:
        return 2
    return 1


def _build_dungeon(level: int, seed: int):
    if level == 99:
        return build_dungeon_dummy(seed)
    if level == 1:
        return build_dungeon_1(seed)
    if level == 11:
        return build_dungeon_1_1(seed)
    if level == 2:
        return build_dungeon_2(seed)
    if level == 3:
        return build_dungeon_3(seed)
    if level == 4:
        return build_dungeon_4(seed)
    if level == 5:
        return build_dungeon_5(seed)
    return build_dungeon_0(seed)


def _snapshot(room, player, budget, *, row=None, col=None, spent=None) -> dict:
    """Undo/redo snapshot of all mutable game state.

    Pass row/col/spent explicitly only when the player has already moved and
    the snapshot must record the *previous* position (dynamite upgrade path).
    All entity-killing actions must call this before mutating state so that
    'u' can fully restore the world, including player inventory.
    """
    return {
        'row':      player.row  if row   is None else row,
        'col':      player.col  if col   is None else col,
        'spent':    budget.spent if spent is None else spent,
        'entities': [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp, alive=e.alive,
                            max_hp=e.max_hp, ai=e.ai, ai_speed=e.ai_speed,
                            ai_tick=e.ai_tick, summon_timer=e.summon_timer)
                     for e in room.entities],
        'fog_cells': set(room.fog_cells),
        'keys':      player.keys,
    }


def _pop_history_step(src: list, dst: list, room, player, budget) -> bool:
    """Pop one normal-mode undo/redo entry from src, restore state, push inverse to dst."""
    if not src:
        return False
    item = src.pop()
    if isinstance(item, dict):
        dst.append(_snapshot(room, player, budget))
        player.row, player.col = item['row'], item['col']
        budget.spent  = item['spent']
        room.entities = item['entities']
        room.fog_cells = item['fog_cells']
        player.keys   = item.get('keys', player.keys)
        room.rebuild_indexes()
    else:
        dst.append((player.row, player.col, budget.spent))
        player.row, player.col, budget.spent = item
    return True


def _ed_step_n(src: list, dst: list, n: int, room, player) -> int:
    """Apply up to n editor undo/redo steps (src→dst). Returns how many were applied."""
    done = 0
    for _ in range(n):
        if not src:
            break
        dst.append(_ed_snapshot(room, player))
        _ed_restore(room, player, src.pop())
        done += 1
    return done


def _manhattan(r1, c1, r2, c2) -> int:
    return abs(r1 - r2) + abs(c1 - c2)


def _kill_door_group(room, row: int, col: int, kind: str = 'door') -> None:
    """Kill the entity at (row, col) and all contiguous adjacent entities of the same kind.

    Uses BFS so a 2-cell horizontal connector or N-cell vertical barrier are
    each treated as one unit — but matching entities in a non-adjacent row/col
    are left untouched.
    """
    from collections import deque
    seen: set = set()
    q: deque = deque([(row, col)])
    while q:
        r, c = q.popleft()
        if (r, c) in seen:
            continue
        seen.add((r, c))
        ent = room.entity_at(r, c)
        if ent and ent.kind == kind:
            room.kill_entity(ent)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (r + dr, c + dc)
                if nb not in seen:
                    q.append(nb)


def _spawn_goblin(room, row, col) -> None:
    for c in (col, col - 1, col + 1):
        if 0 <= c < room.cols and room.is_passable(row, c) and not room.entity_at(row, c):
            room.add_entity(Entity('goblin', row, c, max_hp=1, ai='chase', ai_speed=1))
            return


def _on_kill(ent, player, room=None, level: int = 0) -> str:
    if ent.kind == 'warden':
        player.keys += 1
        return 'The Warden falls! He dropped a key. 🗝'
    if ent.kind == 'goblin' and level == 5 and room is not None:
        if not any(e.alive and e.kind == 'goblin' for e in room.entities):
            player.keys += 1
            return 'Last goblin down! A key clatters to the floor. 🗝'
    return ''


def _enemy_tick(room, player) -> list:
    msgs = []
    for ent in list(room.entities):
        if not ent.alive:
            continue
        dist = _manhattan(player.row, player.col, ent.row, ent.col)
        if ent.kind == 'warden' and dist <= _ALERT_RADIUS:
            if ent.summon_timer == 0:
                _spawn_goblin(room, ent.row, ent.col + random.choice((-1, 1)) * 3)
                _spawn_goblin(room, ent.row, ent.col + random.choice((-1, 1)) * 4)
                ent.summon_timer = _WARDEN_SUMMON_INTERVAL
                msgs.append('The Warden summoned his goblin minions!')
            else:
                ent.summon_timer -= 1
                if ent.summon_timer == 0:
                    _spawn_goblin(room, ent.row, ent.col + random.choice((-1, 1)) * 3)
                    _spawn_goblin(room, ent.row, ent.col + random.choice((-1, 1)) * 4)
                    ent.summon_timer = _WARDEN_SUMMON_INTERVAL
                    msgs.append('The Warden summoned his goblin minions!')
        if not ent.ai:
            continue
        if dist > _ALERT_RADIUS:
            continue
        ent.ai_tick += 1
        if ent.ai_tick % ent.ai_speed != 0:
            continue
        dr = player.row - ent.row
        dc = player.col - ent.col
        # Orthogonal step: dominant axis wins; row-first on tie
        if abs(dr) >= abs(dc):
            nr, nc = ent.row + ((dr > 0) - (dr < 0)), ent.col
        else:
            nr, nc = ent.row, ent.col + ((dc > 0) - (dc < 0))
        if (nr, nc) == (player.row, player.col):
            continue  # don't step onto player's cell
        if room.is_passable(nr, nc) and not room.entity_at(nr, nc):
            room.move_entity(ent, nr, nc)
    return msgs


def _hint_bar(known: list) -> str:
    if 'f' in known:
        return 'f{c}:jump to char  t{c}:jump before char  F/T:backward  w b e  [N]hjkl  :w write  :q quit'
    if 'w' in known:
        return 'w:jump to word start  b:jump back to word  e:jump to word end  [N]hjkl  :w write  :q quit'
    if 'count' in known:
        return '[N]hjkl:count move  0:jump to start of line  ^:first non-blank  $:jump to end of line  x:delete (cut) char  :w write  :q quit'
    if '$' in known:
        return 'hjkl:move cursor  0:jump to start of line  ^:first non-blank  $:jump to end of line  :w write  :q quit'
    return 'h/j/k/l:move cursor  :w write (save)  :q quit  :q! quit without saving'


# ── Dungeon game loop ──────────────────────────────────────────────────────────

def run_dungeon(term: Terminal, level: int, progress: dict,
                player_name: str = 'Normand',
                _dungeon: Dungeon | None = None,
                _start_edit: bool = False) -> dict:
    """Run one dungeon level.

    Returns {'won': bool, 'stars': int, 'action': 'wq'|'quit'}.
    _dungeon: pre-built Dungeon (used for custom layouts from the overworld).
    _start_edit: if True, enter edit mode immediately (admin custom levels).
    """
    if _dungeon is not None:
        dungeon = _dungeon
        seed    = dungeon.seed or 0
    else:
        seed    = random.randint(0, 2**31)
        dungeon = _build_dungeon(level, seed)
    room    = dungeon.room
    if player_name != 'admin':
        room.answer = ''

    player  = Player(row=room.entry[0], col=room.entry[1])
    player.known_commands = _known_commands(level)
    if player_name == 'admin':
        player.known_commands = player.known_commands + ['admin', 'register']
    for _cmd in progress.get('extras', []):
        if _cmd not in player.known_commands:
            player.known_commands = player.known_commands + [_cmd]
    budget  = Budget(room.budget or 20)

    key_buf  = ''
    message  = ''
    msg_ttl  = 0
    undo_stack: list[tuple[int, int, int]] = []
    redo_stack: list[tuple[int, int, int]] = []
    edit_mode  = _start_edit
    ed_undo:   list = []
    ed_redo:   list = []
    count_tutorial_shown = False
    at_exit  = False   # player has stepped on the exit at some point
    last_saved_stars = progress.get(level, {}).get('stars', 0)
    won             = False  # win animation has been triggered
    spotted_goblins: set = set()   # id(ent) of goblins the player has seen
    spotted_wardens: set = set()   # id(ent) of wardens the player has seen
    engaged_entities: set = set()  # id(ent) of entities currently co-located with player
    door_hint_shown: set = set()   # id(ent) of locked doors that showed "requires a key"
    door_open_hint_shown: set = set()  # id(ent) of locked doors that showed "type p"
    msg_pool: list = []            # combat messages for this turn (rotation buffer)
    msg_idx:  int  = 0             # current rotation index into msg_pool
    attack_flash_sym: str   = ''      # directional arrow; '' = no flash active
    attack_flash_pos: tuple = (0, 0)  # goblin cell to flash on
    attack_flash_on:  bool  = True    # True → show arrow, False → show normal g
    attack_flash_ttl: int   = 0

    def _attack_sym() -> str:
        return attack_flash_sym if (attack_flash_sym and attack_flash_on) else ''

    def _attack_pos() -> tuple | None:
        return attack_flash_pos if attack_flash_sym else None

    def _pool_msg() -> str:
        if not msg_pool:
            return ''
        n = len(msg_pool)
        return (f'({msg_idx+1}/{n}) ' if n > 1 else '') + msg_pool[msg_idx]

    def _push(text: str) -> None:
        if text not in msg_pool:
            msg_pool.append(text)

    if _start_edit:
        room.passable_walls = True
        if 'editor' not in player.known_commands:
            player.known_commands = player.known_commands + ['editor']

    if level == 1:
        message = 'The Line Halls — navigate to the corridor, then use $ and ^'
        msg_ttl = 50
    elif level == 11:
        message = 'The Reliquary — Reap the rewards of your adventures!'
        msg_ttl = 50
    elif level == 2:
        message = 'The Counting Crypts — type [N] before hjkl: try 5j or 3l'
        msg_ttl = 50
    elif level == 3:
        message = 'The Rune Halls — w:next cluster  b:prev cluster  e:end of cluster'
        msg_ttl = 60
    elif level == 4:
        message = 'The Character Cataracts — f{c}:jump to char  t{c}:just before  F/T:backward'
        msg_ttl = 60
    elif level == 99:
        message = 'Sandbox — all mechanics active. Type :edit to enter editor mode.'
        msg_ttl = 60

    any_water     = any(ct == CellType.WATER for row in room.cells for ct in row)
    last_activity = time.time()

    def _goblin_msg(base: str) -> str:
        """Append 'Cut them down!' the very first time goblins are ever spotted."""
        if not progress.get('flags', {}).get('seen_goblins'):
            progress.setdefault('flags', {})['seen_goblins'] = True
            return base + ' Cut them down!'
        return base

    # Spot any enemies already visible at level entry
    _entry_goblins = [e for e in room.entities
                      if e.alive and e.kind == 'goblin'
                      and (e.row, e.col) not in room.fog_cells]
    for e in _entry_goblins:
        spotted_goblins.add(id(e))
    if len(_entry_goblins) == 1:
        msg_pool.append(_goblin_msg('You spotted a goblin!'))
    elif len(_entry_goblins) > 1:
        msg_pool.append(_goblin_msg(f'You see {len(_entry_goblins)} goblins!'))
    for e in room.entities:
        if e.alive and e.kind == 'warden' and (e.row, e.col) not in room.fog_cells:
            spotted_wardens.add(id(e))
            msg_pool.append('You spotted a Warden!')
    if msg_pool:
        message = _pool_msg()
        msg_ttl = _MSG_ROTATE_TTL

    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())

    while True:
        key = term.inkey(timeout=0.1)

        prev_message = message
        if player.is_dead:
            message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
            msg_ttl = 2
        elif msg_ttl > 0:
            msg_ttl -= 1
            if msg_ttl == 0:
                if msg_pool:
                    msg_idx = (msg_idx + 1) % len(msg_pool)
                    message = _pool_msg()
                    msg_ttl = _MSG_ROTATE_TTL
                else:
                    message = ''

        if not key:
            water_active  = any_water and (time.time() - last_activity < _WATER_SETTLE_SECS)
            needs_render  = message != prev_message or water_active
            if attack_flash_sym:
                attack_flash_ttl -= 1
                if attack_flash_ttl <= 0:
                    attack_flash_on  = not attack_flash_on
                    attack_flash_ttl = _ATTACK_FLASH_TTL
                    needs_render     = True
            if needs_render:
                render_all(term, dungeon, player, budget, message,
                           attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        last_activity = time.time()
        player.error = ''   # clear any statusline error on the next keypress

        # ── Command mode ──────────────────────────────────────────────────────
        if player.mode == Mode.COMMAND:
            if key.name == 'KEY_ESCAPE':
                player.mode = Mode.NORMAL
                player.cmd_line = ''
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd = player.cmd_line.strip()
                player.mode    = Mode.NORMAL
                player.cmd_line = ''
                msg_pool.clear()
                msg_idx = 0

                if cmd == 'w':
                    if edit_mode and player_name == 'admin':
                        path = SM.save_layout(dungeon.name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    else:
                        if won:
                            stars = _calc_stars(won, budget, room, player, level)
                            prev  = progress.get(level, {}).get('stars', 0)
                            progress[level] = {'complete': True,
                                               'stars': max(stars, prev)}
                            last_saved_stars = max(stars, last_saved_stars)
                        SM.save_progress(progress, player_name)
                        _push('Saved.')

                elif cmd == 'wq':
                    if edit_mode and player_name == 'admin':
                        path = SM.save_layout(dungeon.name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    stars = _calc_stars(won, budget, room, player, level)
                    return {'won': won, 'stars': stars, 'action': 'wq'}

                elif cmd == 'q':
                    stars = _calc_stars(won, budget, room, player, level)
                    if (player_name != 'admin'
                            and won and stars > last_saved_stars):
                        player.error = 'E37: No write since last change (add ! to override)'
                    else:
                        return {'won': won, 'stars': stars, 'action': 'quit'}

                elif cmd == 'q!':
                    return {'won': False, 'stars': 0, 'action': 'quit'}

                elif cmd == 'e' and (player_name == 'admin' or player.is_dead):
                    seed    = random.randint(0, 2**31)
                    dungeon = _build_dungeon(level, seed)
                    room    = dungeon.room
                    if player_name != 'admin':
                        room.answer = ''
                    player  = Player(row=room.entry[0], col=room.entry[1])
                    player.known_commands = _known_commands(level)
                    if player_name == 'admin':
                        player.known_commands = player.known_commands + ['admin', 'register']
                    budget  = Budget(room.budget or 20)
                    undo_stack.clear()
                    redo_stack.clear()
                    edit_mode = False
                    player.register.clear()
                    ed_undo.clear()
                    ed_redo.clear()
                    key_buf         = ''
                    at_exit         = False
                    won             = False
                    spotted_goblins      = set()
                    spotted_wardens      = set()
                    engaged_entities     = set()
                    door_hint_shown      = set()
                    door_open_hint_shown = set()
                    msg_pool             = []
                    msg_idx              = 0
                    _push('Dungeon restarted. Good luck.' if player_name != 'admin' else 'New dungeon loaded.')

                elif cmd == 'edit' and player_name == 'admin':
                    edit_mode = not edit_mode
                    room.passable_walls = edit_mode
                    if edit_mode:
                        if 'editor' not in player.known_commands:
                            player.known_commands = player.known_commands + ['editor']
                        _push('EDIT mode ON — x:cut  s:subst  dd/yy  d/y{m}  p/P  :save <name>')
                    else:
                        player.known_commands = [c for c in player.known_commands if c != 'editor']
                        _push('EDIT mode OFF.')

                elif cmd.startswith('save ') and player_name == 'admin':
                    name = cmd[5:].strip()
                    if name:
                        path = SM.save_layout(name, _serialize_room(room))
                        _push(f'Layout saved: {path.name}')
                    else:
                        _push('Usage:  :save <name>')

                elif cmd.startswith('rune ') and edit_mode and player_name == 'admin':
                    _RUNE_SYMS = {'ancient': '∘', 'verdant': '·', 'void': '○', 'ember': '◦'}
                    kind = cmd[5:].strip().lower()
                    if kind not in _RUNE_SYMS:
                        _push(f'Unknown rune kind: {kind}  (ancient|verdant|void|ember)')
                    else:
                        r, c = player.row, player.col
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                        existing = room.rune_at(r, c)
                        if existing:
                            room.remove_rune(existing)
                        room.add_rune(RuneCluster(row=r, col=c,
                                                  symbols=(_RUNE_SYMS[kind],), kind=kind))
                        _merge_adjacent_runes(room, r)
                        _push(f'Placed {kind} rune.')

                elif cmd.startswith('entity ') and edit_mode and player_name == 'admin':
                    _ENTITY_PRESETS = {
                        'exit':         dict(hp=1, alive=True),
                        'door':         dict(hp=1, alive=True),
                        'locked_door':  dict(hp=1, alive=True),
                        'chest':        dict(hp=1, alive=True),
                        'chest_key':    dict(hp=1, alive=True),
                        'chest_scroll': dict(hp=1, alive=True),
                        'dynamite':     dict(hp=1, alive=True),
                        'wanderer':     dict(hp=1, alive=True, max_hp=1, ai='chase', ai_speed=2),
                        'goblin':       dict(hp=1, alive=True, max_hp=1, ai='chase', ai_speed=1),
                        'warden':       dict(hp=5, alive=True, max_hp=5, ai='',      ai_speed=1),
                    }
                    kind = cmd[7:].strip().lower()
                    if kind not in _ENTITY_PRESETS:
                        kinds_str = '|'.join(_ENTITY_PRESETS)
                        _push(f'Unknown entity kind: {kind}  ({kinds_str})')
                    else:
                        r, c = player.row, player.col
                        ed_undo.append(_ed_snapshot(room, player))
                        ed_redo.clear()
                        existing = room.entity_at(r, c)
                        if existing:
                            room.entities.remove(existing)
                            room.rebuild_indexes()
                        room.add_entity(Entity(kind=kind, row=r, col=c,
                                               **_ENTITY_PRESETS[kind]))
                        _push(f'Placed {kind}.')

                else:
                    _push(f'Unknown command: :{cmd}')

            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                player.cmd_line = player.cmd_line[:-1]
            else:
                player.cmd_line += str(key)
            if msg_pool:
                msg_idx = 0
                message = _pool_msg()
                msg_ttl = _MSG_ROTATE_TTL
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── INSERT mode (admin text placement) ───────────────────────────────
        if player.mode == Mode.INSERT:
            if key.name == 'KEY_ESCAPE':
                player.mode = Mode.NORMAL
                key_buf = ''
            elif edit_mode:
                r, c = player.row, player.col
                if key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                    if c > 0:
                        ed_undo.append(_ed_snapshot(room, player))
                        player.col -= 1
                        _ed_cut(room, r, player.col)
                        _merge_adjacent_runes(room, r)
                elif not key.is_sequence:
                    ch = str(key)
                    if ch.isprintable() and len(ch) == 1:
                        ed_undo.append(_ed_snapshot(room, player))
                        _ed_cut(room, r, c)
                        room.add_rune(RuneCluster(row=r, col=c,
                                                  symbols=(ch,), kind='ember'))
                        _merge_adjacent_runes(room, r)
                        if c + 1 < room.cols:
                            player.col += 1
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # ── Normal mode ───────────────────────────────────────────────────────
        if key.name == 'KEY_ESCAPE':
            _apply_esc(player)
            key_buf = ''
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        raw     = str(key) if not key.is_sequence else ''
        key_buf += raw
        action, key_buf = parse(key_buf, player.mode)

        if action is None:
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        # Dead players may only enter command mode to type :e
        if player.is_dead and not (action['type'] == 'enter_mode'
                                   and action.get('mode') == 'command'):
            render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
            continue

        cur_combat_target = room.entity_at(player.row, player.col)
        if not (cur_combat_target and cur_combat_target.max_hp > 0):
            cur_combat_target = None

        # New turn: clear rotation pool and attack flash
        msg_pool.clear()
        msg_idx = 0
        attack_flash_sym = ''
        attack_flash_pos = (0, 0)
        attack_flash_on  = True
        attack_flash_ttl = 0

        prev_pos = (player.row, player.col, budget.spent)
        prev_adjacent_ids = {
            id(e) for e in room.entities
            if e.alive and e.max_hp
            and _manhattan(player.row, player.col, e.row, e.col) <= _ATTACK_RADIUS
        }
        count    = action.get('count', 1)

        if action['type'] == 'motion':
            motion = action['motion']
            target = action.get('target')

            if not edit_mode and not _action_allowed(action, player.known_commands):
                _push(_guard_message(action))
                message = _pool_msg(); msg_ttl = _MSG_ROTATE_TTL
                render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                continue

            moved = apply_motion(player, motion, count, room, target)
            if moved:
                if not edit_mode:
                    budget.spend(_keystroke_cost(count, motion))
                    undo_stack.append(prev_pos)
                    redo_stack.clear()

                if count > 1 and not count_tutorial_shown and not edit_mode and level == 2:
                    count_tutorial_shown = True
                    _push(f'{count}{motion} moved {count} steps in 2 keystrokes — count is efficient!')

                # Void rune: fall animation, lose heart, respawn (skip in edit mode)
                ru = room.rune_at(player.row, player.col)
                if not edit_mode and ru and ru.kind == 'void':
                    iw    = _iw(term)
                    game_h = term.height - 7
                    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
                    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
                    scr_r    = player.row - vr_start + 3
                    scr_c    = player.col - vc_start + 1
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _void_fall_animation(term, scr_r, scr_c)
                    player.take_damage(2)  # 1 full heart
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                    else:
                        h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                        message = f'You fell into the void!  ({h}{hh} ♥ remaining)'
                        msg_ttl = 25
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue

                # Water: drown if landed on water cell (e.g. via $, 0, ^)
                if not edit_mode and room.cells[player.row][player.col] == CellType.WATER:
                    iw    = _iw(term)
                    game_h = term.height - 7
                    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
                    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
                    scr_r    = player.row - vr_start + 3
                    scr_c    = player.col - vc_start + 1
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _drown_animation(term, scr_r, scr_c)
                    player.take_damage(2)  # 1 full heart
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                    else:
                        h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                        message = f'You drowned!  ({h}{hh} ♥ remaining)'
                        msg_ttl = 25
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    continue

                # Dynamite: explode if stepped on
                ent = room.entity_at(player.row, player.col)
                if not edit_mode and ent and ent.kind == 'dynamite':
                    if undo_stack and isinstance(undo_stack[-1], tuple):
                        pr, pc, ps = undo_stack.pop()
                        undo_stack.append(_snapshot(room, player, budget,
                                                    row=pr, col=pc, spent=ps))
                    expl_r, expl_c = ent.row, ent.col
                    room.kill_entity(ent)
                    iw_now     = _iw(term)
                    game_h_now = term.height - 7
                    vr = max(0, min(player.row - game_h_now // 2, room.rows - game_h_now))
                    vc = max(0, min(player.col - iw_now     // 2, room.cols - iw_now))
                    vr, vc = max(0, vr), max(0, vc)
                    scr_r = 3 + (expl_r - vr)
                    scr_c = 1 + (expl_c - vc)
                    render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _explosion_animation(term, room, expl_r, expl_c, scr_r, scr_c, iw_now, game_h_now)
                    for _dr in range(-3, 4):
                        for _dc in range(-3, 4):
                            _dist = abs(_dr) + abs(_dc)
                            if _dist not in _EXPL_DAMAGE:
                                continue
                            _wr, _wc = expl_r + _dr, expl_c + _dc
                            if (0 <= _wr < room.rows and 0 <= _wc < room.cols
                                    and room.cells[_wr][_wc] == CellType.WOOD_WALL):
                                room.damage_wood_wall(_wr, _wc, _EXPL_DAMAGE[_dist])
                    dmg = _EXPL_DAMAGE.get(0, 0)  # player is at the centre
                    player.take_damage(dmg)
                    if player.is_dead:
                        message = 'You set off a dynamite charge!  GAME OVER  (:e to reload)'
                        msg_ttl = 2
                    else:
                        h, hh = player.hp // 2, '½' if player.hp % 2 else ''
                        message = f'BOOM! Dynamite!  ({h}{hh} ♥ remaining)'
                        msg_ttl = 30
                    ent = None  # consumed; fall through to normal render

                # Win / exit check
                if ent is None:
                    ent = room.entity_at(player.row, player.col)
                if ent and ent.kind == 'exit' and not won:
                    won = True
                    at_exit = True
                    render_all(term, dungeon, player, budget, '', attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    iw  = _iw(term)
                    par = room.par or 0
                    if par > 0 and budget.spent <= par:
                        _fireworks_animation(term, iw)
                        message = 'Par achieved! Flawless Vim mastery. Type :wq to return to the overworld.'
                    else:
                        _win_animation(term, iw)
                        message = 'Dungeon cleared!  Type :wq to return to the overworld.'
                    msg_ttl = 200

        elif action['type'] == 'enter_mode':
            m = action['mode']
            if m == 'command':
                player.mode     = Mode.COMMAND
                player.cmd_line = ''
            elif m == 'insert':
                if 'insert' in player.known_commands or 'admin' in player.known_commands:
                    player.mode = Mode.INSERT
                else:
                    _push('INSERT mode not learned yet.')
            elif m in ('visual', 'visual_line', 'visual_block'):
                if 'visual' in player.known_commands or 'admin' in player.known_commands:
                    player.mode = {'visual': Mode.VISUAL,
                                   'visual_line': Mode.VISUAL_LINE,
                                   'visual_block': Mode.VISUAL_BLOCK}[m]
                else:
                    _push('VISUAL mode not learned yet.')

        elif action['type'] == 'undo':
            if edit_mode:
                done = _ed_step_n(ed_undo, ed_redo, count, room, player)
            else:
                done = sum(_pop_history_step(undo_stack, redo_stack, room, player, budget)
                           for _ in range(count))
            _push(f'{done} change(s) undone.' if done else 'Nothing to undo.')

        elif action['type'] == 'redo':
            if edit_mode:
                done = _ed_step_n(ed_redo, ed_undo, count, room, player)
            else:
                done = sum(_pop_history_step(redo_stack, undo_stack, room, player, budget)
                           for _ in range(count))
            _push(f'{done} change(s) redone.' if done else 'Nothing to redo.')

        elif action['type'] == 'interact':
            if edit_mode:
                ed_undo.append(_ed_snapshot(room, player))
                ed_redo.clear()
                cut_items = []
                for _ci in range(count):
                    item = _ed_cut(room, player.row, player.col + _ci)
                    if item:
                        cut_items.append(item)
                if cut_items:
                    player.register = cut_items
                    descs = ', '.join(_clip_desc(i) for i in cut_items)
                    _push(f'Cut {len(cut_items)}: {descs}')
                else:
                    ed_undo.pop()
                    _push('Nothing to cut here.')
            else:
                interacted = False
                cur = room.entity_at(player.row, player.col)
                if cur and cur.kind in ('chest', 'chest_key', 'chest_scroll'):
                    undo_stack.append(_snapshot(room, player, budget))
                    redo_stack.clear()
                    item = _chest_loot(cur.kind)
                    room.kill_entity(cur)
                    budget.spend(1)
                    if item == 'key':
                        player.keys += 1
                        _push('You found a key!')
                    elif item == 'heart':
                        player.heal(2)
                        _push('You found a heart! HP restored.')
                    else:
                        _push('You found a scroll!')
                    interacted = True
                    if level == 11:
                        if 'register' not in player.known_commands:
                            player.known_commands = player.known_commands + ['register']
                            extras = progress.get('extras', [])
                            if 'register' not in extras:
                                progress['extras'] = extras + ['register']
                        render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                        _show_reliquary_scroll(term, _iw(term), term.height - 7)
                    elif 'register' not in player.known_commands:
                        player.known_commands = player.known_commands + ['register']
                        extras = progress.get('extras', [])
                        if 'register' not in extras:
                            progress['extras'] = extras + ['register']
                        render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                        _show_register_tutorial(term, _iw(term), term.height - 7)
                elif cur and cur.kind == 'door':
                    undo_stack.append(_snapshot(room, player, budget))
                    redo_stack.clear()
                    _kill_door_group(room, cur.row, cur.col)
                    _reveal_from(room, player.row, player.col)
                    budget.spend(1)
                    _push('Door opened.')
                    interacted = True
                elif cur and cur.kind in ('goblin', 'warden'):
                    cur.hp -= 1
                    budget.spend(1)
                    interacted = True
                    if cur.hp <= 0:
                        room.kill_entity(cur)
                        player.register = [{'type': 'entity', 'entity': cur}]
                        _push(_on_kill(cur, player, room, level) or 'Enemy defeated!')
                    else:
                        _push(f'Hit! ({cur.hp}/{cur.max_hp} HP)')
                elif cur and cur.kind == 'shield':
                    room.kill_entity(cur)
                    player.register = [{'type': 'entity', 'entity': cur}]
                    budget.spend(1)
                    _push('Shield destroyed!')
                    interacted = True
                elif cur and cur.kind == 'heart_container':
                    player.max_hp += 2
                    player.hp      = player.max_hp
                    room.kill_entity(cur)
                    player.register = [{'type': 'entity', 'entity': cur}]
                    budget.spend(1)
                    _push('Max HP increased!  ♥')
                    interacted = True
                if not interacted:
                    cut_items = []
                    for _ci in range(count):
                        item = _ed_cut(room, player.row, player.col + _ci)
                        if item:
                            cut_items.append(item)
                    if cut_items:
                        undo_stack.append(_snapshot(room, player, budget))
                        redo_stack.clear()
                        player.register = cut_items
                        budget.spend(1)
                        descs = ', '.join(_clip_desc(i) for i in cut_items)
                        _push(f'Cut {len(cut_items)}: {descs}')

        elif edit_mode and action['type'] == 'substitute':
            ed_undo.append(_ed_snapshot(room, player))
            ed_redo.clear()
            all_items: list = []
            for _si in range(count):
                all_items.extend(_ed_subst(room, player.row, player.col + _si))
            player.register = all_items
            _push('Substituted: ' + ', '.join(_clip_desc(i) for i in all_items))

        elif not edit_mode and action['type'] == 'paste' and _action_allowed(action, player.known_commands):
            before = action.get('before', False)
            dc = -1 if before else 1          # P → left, p → right
            target = room.entity_at(player.row, player.col + dc)
            if target and target.kind == 'locked_door':
                if player.keys > 0:
                    undo_stack.append(_snapshot(room, player, budget))
                    redo_stack.clear()
                    player.keys -= 1
                    render_all(term, dungeon, player, budget, _pool_msg(), attack_pos=_attack_pos(), attack_sym=_attack_sym())
                    _unlock_animation(term, room, player,
                                      target.row, target.col,
                                      _iw(term), term.height - 7)
                    _kill_door_group(room, target.row, target.col, kind='locked_door')
                    _reveal_from(room, player.row, player.col)
                    budget.spend(1)
                    _push('Door unlocked!')
                else:
                    player.error = 'E: No key in inventory'
            else:
                _push('Nothing to paste here.')

        elif edit_mode and action['type'] == 'paste':
            if player.register:
                ed_undo.append(_ed_snapshot(room, player))
                ed_redo.clear()
                before = action.get('before', False)
                reg    = player.register
                items  = reg * count
                r      = player.row

                def _col_open(c, _r=r):
                    return (0 <= c < room.cols and
                            room.cells[_r][c] not in (CellType.WALL, CellType.WOOD_WALL))

                if before:  # P: left primary (cursor inclusive), overflow right
                    left_cols = []
                    for _c in range(player.col, -1, -1):
                        if _col_open(_c): left_cols.append(_c)
                        else: break
                    right_cols = []
                    for _c in range(player.col + 1, room.cols):
                        if _col_open(_c): right_cols.append(_c)
                        else: break
                    lc = min(count, len(left_cols))
                    rc = min(count - lc, len(right_cols))
                    if lc > 0:
                        _ed_paste(room, r, left_cols[lc - 1], list(reversed(items[:lc])))
                    if rc > 0:
                        _ed_paste(room, r, player.col + 1, items[lc:lc + rc])
                        new_c = player.col + rc + 1
                        while new_c < room.cols and not _col_open(new_c):
                            new_c += 1
                        if new_c < room.cols:
                            player.col = new_c
                else:  # p: right primary (cursor+1), overflow left
                    right_cols = []
                    for _c in range(player.col + 1, room.cols):
                        if _col_open(_c): right_cols.append(_c)
                        else: break
                    left_cols = []
                    for _c in range(player.col, -1, -1):
                        if _col_open(_c): left_cols.append(_c)
                        else: break
                    rc = min(count, len(right_cols))
                    lc = min(count - rc, len(left_cols))
                    if rc > 0:
                        _ed_paste(room, r, player.col + 1, items[:rc])
                    if lc > 0:
                        _ed_paste(room, r, left_cols[lc - 1],
                                  list(reversed(items[rc:rc + lc])))
                        new_c = player.col - lc
                        while new_c >= 0 and not _col_open(new_c):
                            new_c -= 1
                        if new_c >= 0:
                            player.col = new_c

                _push(f'Pasted {lc + rc} item(s) {"before" if before else "after"} cursor.')
            else:
                _push('Clipboard is empty.')

        elif edit_mode and action['type'] == 'operator':
            op     = action['op']
            motion = action['motion']
            ed_undo.append(_ed_snapshot(room, player))
            ed_redo.clear()
            if motion == 'line':
                all_items: list = []
                for dr in range(count):
                    r = player.row + dr
                    if r >= room.rows:
                        break
                    all_items.extend(_ed_row_items(room, r))
                    if op in ('d', 'c'):
                        _ed_clear_row(room, r)
                player.register = all_items
                verb    = 'Cut' if op in ('d', 'c') else 'Yanked'
                _push(f'{verb} {len(all_items)} item(s) from {count} row(s).')
            else:
                orig_r, orig_c = player.row, player.col
                mc = action.get('motion_count', 1)
                apply_motion(player, motion, mc, room, action.get('target'))
                new_r, new_c = player.row, player.col
                player.row, player.col = orig_r, orig_c
                if op in ('d', 'c'):
                    items = _ed_delete_range(room, orig_r, orig_c, new_r, new_c)
                else:
                    items = _ed_range_items(room, orig_r, orig_c, new_r, new_c)
                player.register = items
                verb    = 'Cut' if op in ('d', 'c') else 'Yanked'
                _push(f'{verb} {len(items)} item(s).')
            if op == 'y':
                ed_undo.pop()

        # ── Combat: enemy movement then adjacency attacks ────────────────────
        if not edit_mode:
            xd_id     = (id(cur_combat_target)
                         if action['type'] == 'interact' and cur_combat_target
                         else None)
            tick_msgs = _enemy_tick(room, player)

            # Any enemy now adjacent attacks (except the one the player just hit,
            # and except enemies that only became adjacent this turn — player gets
            # one free turn when landing next to a new enemy via fg/motion).
            attackers = []
            for ent in room.entities:
                if not ent.alive or not ent.max_hp:
                    continue
                if id(ent) == xd_id:
                    continue
                if id(ent) not in prev_adjacent_ids:
                    continue
                if _manhattan(player.row, player.col, ent.row, ent.col) <= _ATTACK_RADIUS:
                    attackers.append(ent)
                    player.take_damage(1)
                    if player.is_dead:
                        message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
                        msg_ttl = 2
                        break
            if attackers and not player.is_dead:
                ent = attackers[0]
                dr  = player.row - ent.row
                dc  = player.col - ent.col
                attack_flash_sym = _SPEAR_DIRS.get((dr, dc), '✕')
                attack_flash_pos = (ent.row, ent.col)
                attack_flash_on  = True
                attack_flash_ttl = _ATTACK_FLASH_TTL

            # Warden summon message
            if tick_msgs and not player.is_dead:
                _push(tick_msgs[0])

            # Engagement: fire for any attacker now adjacent
            if attackers:
                for _ae in attackers:
                    if id(_ae) not in engaged_entities:
                        engaged_entities.add(id(_ae))
                        _aname = 'Warden' if _ae.kind == 'warden' else _ae.kind
                        _push(f'The {_aname} is engaging you in combat!')
            else:
                engaged_entities.clear()

            # Spotted: new enemies now visible (not in fog)
            if not player.is_dead:
                new_g = [e for e in room.entities
                         if e.alive and e.kind == 'goblin'
                         and id(e) not in spotted_goblins
                         and (e.row, e.col) not in room.fog_cells]
                for e in new_g:
                    spotted_goblins.add(id(e))
                if len(new_g) == 1:
                    _push(_goblin_msg('You spotted a goblin!'))
                elif len(new_g) > 1:
                    _push(_goblin_msg(f'You see {len(new_g)} goblins!'))

                for e in room.entities:
                    if (e.alive and e.kind == 'warden'
                            and id(e) not in spotted_wardens
                            and (e.row, e.col) not in room.fog_cells):
                        spotted_wardens.add(id(e))
                        _push('You spotted a Warden!')

        if not edit_mode and budget.is_over:
            _push('Over budget! Try a more efficient path. (u to undo)')

        # Locked-door proximity hints (first time within 1 cell of each door)
        if not edit_mode and not player.is_dead:
            for ent in room.entities:
                if (ent.alive and ent.kind == 'locked_door'
                        and abs(ent.row - player.row) + abs(ent.col - player.col) <= 1):
                    if player.keys > 0 and id(ent) not in door_open_hint_shown:
                        door_open_hint_shown.add(id(ent))
                        _push('Type p to put the key in the lock.')
                    elif player.keys == 0 and id(ent) not in door_hint_shown:
                        door_hint_shown.add(id(ent))
                        _push('This door requires a key.')

        # ── Pool finalization: display rotation or clear message ──────────────
        if not player.is_dead and not won:
            if msg_pool:
                msg_idx = 0
                message = _pool_msg()
                msg_ttl = _MSG_ROTATE_TTL
            else:
                message = ''
                msg_ttl = 0

        render_all(term, dungeon, player, budget, message, attack_pos=_attack_pos(), attack_sym=_attack_sym())


# ── Save-select screen loop ───────────────────────────────────────────────────

def run_save_select(term: Terminal) -> tuple[str, str]:
    """Show the save-selection screen.

    Returns ('load', player_name) or ('back', '').
    """
    saves    = SM.list_saves()
    cursor   = 0
    pending_d = False

    render_save_select(term, saves, cursor)

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        raw = str(key) if not key.is_sequence else ''

        if pending_d:
            pending_d = False
            if raw == 'd' and saves:
                name = SM.load_player_name(saves[cursor])
                SM.delete_save(name)
                saves  = SM.list_saves()
                cursor = min(cursor, max(0, len(saves) - 1))
                render_save_select(term, saves, cursor)
                continue
            # fall through to handle the key normally

        if key.name == 'KEY_ESCAPE':
            return ('back', '')
        elif raw == 'j':
            cursor = min(cursor + 1, max(0, len(saves) - 1))
        elif raw == 'k':
            cursor = max(cursor - 1, 0)
        elif raw == 'd' and saves:
            pending_d = True
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            if saves:
                name = SM.load_player_name(saves[cursor])
                return ('load', name)

        render_save_select(term, saves, cursor, deleting=pending_d)


# ── Title screen loop ─────────────────────────────────────────────────────────

def run_title(term: Terminal, has_save: bool) -> tuple[str, str]:
    """Show the title screen.

    Returns ('new', name), ('load', name), or ('quit', '').
    'new'  — player chose "begin new journey" and entered a name; progress wiped.
    'load' — player chose "load saved game" and selected a save.
    'quit' — player quit.
    """
    state        = 'menu'   # 'menu' | 'naming' | 'confirm'
    cursor       = 0
    cmd_buf      = ''       # ':' + chars typed in command mode
    name_buf     = ''       # chars typed in naming state
    pending_name = ''       # name awaiting overwrite confirmation
    _blink       = False    # current eye state; updated by timer

    # Pick a wisdom quote filtered to levels unlocked in any existing save
    _max_level = 0
    for _sd in SM.list_saves():
        _prog = SM.load_progress(_sd)
        for _lv in LEVELS:
            if is_unlocked(_lv['id'], _prog):
                _max_level = max(_max_level, _lv['id'])
    _quote_lines = select_quote(_max_level)

    def _render():
        cl = cmd_buf[1:]  if cmd_buf.startswith(':') else None
        np = name_buf     if state == 'naming'        else None
        cn = pending_name if state == 'confirm'       else None
        render_title(term, cursor, has_save, cmd_line=cl, name_prompt=np,
                     confirm_name=cn, blink=_blink, quote_lines=_quote_lines)

    _blink = (time.time() % 5) < 0.5
    _render()

    while True:
        key = term.inkey(timeout=0.1)

        # Blink: eyes closed for 0.5 s once every 5 s
        new_blink = (time.time() % 5) < 0.5
        if new_blink != _blink:
            _blink = new_blink
            _render()

        if not key:
            continue

        raw = str(key) if not key.is_sequence else ''

        # ── Confirm overwrite state ───────────────────────────────────────────
        if state == 'confirm':
            if raw in ('y', 'Y'):
                SM.save_for(pending_name, {'player_name': pending_name, 'progress': {}})
                return ('new', pending_name)
            elif raw in ('n', 'N') or key.name == 'KEY_ESCAPE':
                name_buf     = pending_name
                pending_name = ''
                state        = 'naming'
            _render()
            continue

        # ── Naming state ──────────────────────────────────────────────────────
        if state == 'naming':
            if key.name == 'KEY_ESCAPE':
                state    = 'menu'
                name_buf = ''
            elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                name = name_buf.strip() or 'Normand'
                if SM.load_for(name) is not None:
                    pending_name = name
                    state        = 'confirm'
                else:
                    SM.save_for(name, {'player_name': name, 'progress': {}})
                    return ('new', name)
            elif key.name == 'KEY_BACKSPACE' or raw == '\x7f':
                name_buf = name_buf[:-1]
            elif raw and raw.isprintable() and len(name_buf) < _NAME_MAX:
                name_buf += raw
            _render()
            continue

        # ── Command-line mode (:q, :q!, :wq all quit) ────────────────────────
        if cmd_buf.startswith(':'):
            if key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
                cmd     = cmd_buf[1:].strip()
                cmd_buf = ''
                if cmd in ('q', 'q!', 'wq'):
                    return ('quit', '')
            elif key.name == 'KEY_ESCAPE':
                cmd_buf = ''
            elif key.name == 'KEY_BACKSPACE' or raw == '\x7f':
                cmd_buf = cmd_buf[:-1]
            elif raw:
                cmd_buf += raw
            _render()
            continue

        # ── Normal menu navigation ────────────────────────────────────────────
        if raw == ':':
            cmd_buf = ':'
        elif key.name == 'KEY_ESCAPE':
            cmd_buf = ''
        elif raw == 'j':
            cursor = (cursor + 1) % len(_TITLE_MENU)
        elif raw == 'k':
            cursor = (cursor - 1) % len(_TITLE_MENU)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            _, action = _TITLE_MENU[cursor]
            if action == 'quit':
                return ('quit', '')
            elif action == 'load' and not has_save:
                pass  # dimmed — ignore
            elif action == 'load':
                sel_action, sel_name = run_save_select(term)
                if sel_action == 'load':
                    return ('load', sel_name)
                # 'back' — fall through and re-render title
            elif action == 'new':
                state    = 'naming'
                name_buf = ''

        _render()


# ── Overworld loop ─────────────────────────────────────────────────────────────

def run_overworld(term: Terminal, player: Player, progress: dict) -> dict:
    """Show the netrw overworld.

    Returns {'action': 'enter', 'level': N},
            {'action': 'open_custom', 'layout': dict}, or
            {'action': 'quit'}.
    """
    visible   = [l for l in LEVELS if not l.get('admin_only') or player.name == 'admin']
    customs   = SM.list_layouts() if player.name == 'admin' else []
    total     = len(visible) + len(customs)
    cursor_row = 0
    cmd_active = False
    cmd_line   = ''
    pending_d  = False

    def _render(deleting=False):
        render_overworld(term, player, progress, cursor_row,
                         cmd_line if cmd_active else None,
                         levels=visible, custom_layouts=customs,
                         deleting=deleting)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        # ── Command mode ──────────────────────────────────────────────────────
        if cmd_active:
            if key.name == 'KEY_ESCAPE':
                cmd_active = False
                cmd_line   = ''
            elif key.name == 'KEY_ENTER' or str(key) in ('\n', '\r'):
                cmd = cmd_line.strip()
                cmd_active = False
                cmd_line   = ''
                if cmd in ('q', 'q!', 'wq'):
                    if cmd == 'wq':
                        SM.save_progress(progress, player.name)
                    return {'action': 'quit'}
                # Unknown overworld commands are silently ignored
            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                cmd_line = cmd_line[:-1]
            else:
                cmd_line += str(key)
            _render()
            continue

        # ── Navigation ────────────────────────────────────────────────────────
        raw = str(key) if not key.is_sequence else ''

        on_custom = cursor_row >= len(visible)

        if pending_d:
            pending_d = False
            if raw == 'd' and on_custom:
                layout = customs[cursor_row - len(visible)]
                SM.delete_layout(layout.get('layout_name', ''))
                customs    = SM.list_layouts()
                total      = len(visible) + len(customs)
                cursor_row = min(cursor_row, max(len(visible), total) - 1)
                _render()
                continue
            # fall through and handle the key normally

        if raw == ':':
            cmd_active = True
            cmd_line   = ''
        elif raw == 'j':
            cursor_row = min(cursor_row + 1, total - 1)
        elif raw == 'k':
            cursor_row = max(cursor_row - 1, 0)
        elif raw == 'd' and on_custom:
            pending_d = True
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            if cursor_row < len(visible):
                level_id = visible[cursor_row]['id']
                if is_unlocked(level_id, progress, player.name):
                    return {'action': 'enter', 'level': level_id}
                # Locked level: flash hint (no action)
            else:
                layout = customs[cursor_row - len(visible)]
                return {'action': 'open_custom', 'layout': layout}

        _render(deleting=pending_d)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Vimny — Vim dungeon crawler')
    ap.add_argument('--level', type=int, default=None, choices=[0, 1, 11, 2, 3, 4, 5, 99],
                    help='skip overworld and start at this level (debug)')
    args = ap.parse_args()

    term = Terminal()
    C.init(term)
    S.init(term)

    player    = Player()
    progress: dict = {}

    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        start_level = args.level  # None → show title then overworld

        # Show title screen unless jumping straight to a level for debugging.
        if start_level is None:
            has_save = bool(SM.list_saves())
            title_action, player_name = run_title(term, has_save)
            if title_action == 'quit':
                return
            player.name = player_name or 'Normand'
            if title_action == 'load':
                save_data = SM.load_for(player.name) or {}
                progress  = SM.load_progress(save_data)
            # 'new': progress stays empty (fresh save already written in run_title)

        while True:
            if start_level is not None:
                ow_result  = {'action': 'enter', 'level': start_level}
                start_level = None
            else:
                ow_result = run_overworld(term, player, progress)

            if ow_result['action'] == 'quit':
                break

            if ow_result['action'] == 'open_custom':
                layout  = ow_result['layout']
                room    = _deserialize_room(layout)
                dungeon = Dungeon(name=layout.get('layout_name', 'Custom'), seed=0)
                dungeon.rooms        = [room]
                dungeon.current_room = 0
                run_dungeon(term, 0, progress, player.name,
                            _dungeon=dungeon, _start_edit=True)
                continue

            level = ow_result['level']
            dung_result = run_dungeon(term, level, progress, player.name)

            # Persist progress only when the player explicitly saved (:wq).
            # (:w mid-dungeon already updated progress and saved inline.)
            if dung_result['won'] and dung_result['action'] == 'wq':
                prev_stars = progress.get(level, {}).get('stars', 0)
                progress[level] = {
                    'complete': True,
                    'stars': max(dung_result['stars'], prev_stars),
                }
                SM.save_progress(progress, player.name)



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
