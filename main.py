#!/usr/bin/env python3
"""Vimny — entry point and main game loop."""
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
from engine.world import Entity, CellType
from engine.motion import apply_motion, move_player, _apply_esc, _reveal_from, _cell_char
from engine.editor import (
    _merge_adjacent_runes, _ed_cut, _ed_snapshot, _ed_restore, _ed_subst,
    _ed_paste, _ed_row_items, _ed_clear_row, _ed_range_items, _ed_delete_range,
    _clip_desc, _serialize_room,
)
from generation.dungeon_gen import build_dungeon_0, build_dungeon_1, build_dungeon_2, build_dungeon_3, build_dungeon_dummy
from content.levels import LEVELS, is_unlocked, known_commands as _known_commands
import save.save_manager as SM


_WATER_SETTLE_SECS = 60   # stop animating water after this many idle seconds

# Explosion damage in half-hearts by Manhattan distance from centre
_EXPL_DAMAGE = {0: 3, 1: 3, 2: 2, 3: 1}   # 0-1: 1.5♥  2: 1♥  3: 0.5♥

def _chest_loot(kind: str) -> str:
    """Return the item type yielded by looting a chest."""
    if kind == 'chest_key':
        return 'key'
    if kind == 'chest_scroll':
        return 'scroll'
    return 'key' if random.random() < 0.6 else 'scroll'

# ── Register tutorial overlay ─────────────────────────────────────────────────

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

def _keystroke_cost(count: int) -> int:
    return 1 if count == 1 else len(str(count)) + 1


def _calc_stars(won: bool, budget: Budget, room) -> int:
    if not won:
        return 0
    par = room.par or 0
    if par > 0 and budget.spent <= par:
        return 2
    return 1


def _build_dungeon(level: int, seed: int):
    if level == 99:
        return build_dungeon_dummy(seed)
    if level == 1:
        return build_dungeon_1(seed)
    if level == 2:
        return build_dungeon_2(seed)
    if level == 3:
        return build_dungeon_3(seed)
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
        'entities': [Entity(kind=e.kind, row=e.row, col=e.col, hp=e.hp, alive=e.alive)
                     for e in room.entities],
        'fog_cells': set(room.fog_cells),
        'keys':      player.keys,
    }


def _hint_bar(known: list) -> str:
    if 'w' in known:
        return 'w:jump to word start  b:jump back to word  e:jump to word end  [N]hjkl  :w write  :q quit'
    if 'count' in known:
        return '[N]hjkl:count move  0:jump to start of line  ^:first non-blank  $:jump to end of line  x:delete (cut) char  :w write  :q quit'
    if '$' in known:
        return 'hjkl:move cursor  0:jump to start of line  ^:first non-blank  $:jump to end of line  :w write  :q quit'
    return 'h/j/k/l:move cursor  :w write (save)  :q quit  :q! quit without saving'


# ── Dungeon game loop ──────────────────────────────────────────────────────────

def run_dungeon(term: Terminal, level: int, progress: dict,
                player_name: str = 'Normand') -> dict:
    """Run one dungeon level.

    Returns {'won': bool, 'stars': int, 'action': 'wq'|'quit'}.
    """
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

    key_buf  = ''
    message  = ''
    msg_ttl  = 0
    undo_stack: list[tuple[int, int, int]] = []
    redo_stack: list[tuple[int, int, int]] = []
    edit_mode  = False
    ed_undo:   list = []
    ed_redo:   list = []
    count_tutorial_shown = False
    at_exit  = False   # player has stepped on the exit at some point
    last_saved_stars = progress.get(level, {}).get('stars', 0)
    won      = False   # win animation has been triggered

    if level == 1:
        message = 'The Line Halls — navigate to the corridor, then use $ and ^'
        msg_ttl = 50
    elif level == 2:
        message = 'The Counting Crypts — type [N] before hjkl: try 5j or 3l'
        msg_ttl = 50
    elif level == 3:
        message = 'The Rune Halls — w:next cluster  b:prev cluster  e:end of cluster'
        msg_ttl = 60
    elif level == 99:
        message = 'Sandbox — all mechanics active. Type :edit to enter editor mode.'
        msg_ttl = 60

    any_water     = any(ct == CellType.WATER for row in room.cells for ct in row)
    last_activity = time.time()

    render_all(term, dungeon, player, budget, message)

    while True:
        key = term.inkey(timeout=0.1)

        prev_message = message
        if player.is_dead:
            message = '** GAME OVER ** Type  :e  to re-load the dungeon.'
            msg_ttl = 2
        elif msg_ttl > 0:
            msg_ttl -= 1
            if msg_ttl == 0:
                message = ''

        if not key:
            water_active = any_water and (time.time() - last_activity < _WATER_SETTLE_SECS)
            if message != prev_message or water_active:
                render_all(term, dungeon, player, budget, message)
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

                if cmd == 'w':
                    if won:
                        stars = _calc_stars(won, budget, room)
                        prev  = progress.get(level, {}).get('stars', 0)
                        progress[level] = {'complete': True,
                                           'stars': max(stars, prev)}
                        last_saved_stars = max(stars, last_saved_stars)
                    SM.save_progress(progress, player_name)
                    message = 'Saved.'
                    msg_ttl = 30

                elif cmd == 'wq':
                    stars = _calc_stars(won, budget, room)
                    return {'won': won, 'stars': stars, 'action': 'wq'}

                elif cmd == 'q':
                    stars = _calc_stars(won, budget, room)
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
                    key_buf  = ''
                    at_exit  = False
                    won      = False
                    message  = 'Dungeon restarted. Good luck.' if player_name != 'admin' else 'New dungeon loaded.'
                    msg_ttl  = 30

                elif cmd == 'edit' and player_name == 'admin':
                    edit_mode = not edit_mode
                    room.passable_walls = edit_mode
                    if edit_mode:
                        if 'editor' not in player.known_commands:
                            player.known_commands = player.known_commands + ['editor']
                        message = 'EDIT mode ON — x:cut  s:subst  dd/yy  d/y{m}  p/P  :save <name>'
                    else:
                        player.known_commands = [c for c in player.known_commands if c != 'editor']
                        message = 'EDIT mode OFF.'
                    msg_ttl = 40

                elif cmd.startswith('save ') and player_name == 'admin':
                    name = cmd[5:].strip()
                    if name:
                        path = SM.save_layout(name, _serialize_room(room))
                        message = f'Layout saved: {path.name}'
                    else:
                        message = 'Usage:  :save <name>'
                    msg_ttl = 40

                else:
                    message = f'Unknown command: :{cmd}'
                    msg_ttl = 30

            elif key.name == 'KEY_BACKSPACE' or str(key) == '\x7f':
                player.cmd_line = player.cmd_line[:-1]
            else:
                player.cmd_line += str(key)
            render_all(term, dungeon, player, budget, message)
            continue

        # ── Normal mode ───────────────────────────────────────────────────────
        if key.name == 'KEY_ESCAPE':
            _apply_esc(player)
            key_buf = ''
            render_all(term, dungeon, player, budget, message)
            continue

        raw     = str(key) if not key.is_sequence else ''
        key_buf += raw
        action, key_buf = parse(key_buf, player.mode)

        if action is None:
            render_all(term, dungeon, player, budget, message)
            continue

        # Dead players may only enter command mode to type :e
        if player.is_dead and not (action['type'] == 'enter_mode'
                                   and action.get('mode') == 'command'):
            render_all(term, dungeon, player, budget, message)
            continue

        prev_pos = (player.row, player.col, budget.spent)

        if action['type'] == 'motion':
            motion = action['motion']
            count  = action.get('count', 1)
            target = action.get('target')

            if count > 1 and 'count' not in player.known_commands and not edit_mode:
                message = "You haven't learned count motions yet."
                msg_ttl = 20
                render_all(term, dungeon, player, budget, message)
                continue

            if motion in ('G', 'gg') and 'G' not in player.known_commands and 'admin' not in player.known_commands:
                message = "You haven't learned G/gg yet."
                msg_ttl = 20
                render_all(term, dungeon, player, budget, message)
                continue

            moved = apply_motion(player, motion, count, room, target)
            if moved:
                if not edit_mode:
                    budget.spend(_keystroke_cost(count))
                    undo_stack.append(prev_pos)
                    redo_stack.clear()

                if count > 1 and not count_tutorial_shown and not edit_mode:
                    count_tutorial_shown = True
                    message = f'{count}{motion} moved {count} steps in 2 keystrokes — count is efficient!'
                    msg_ttl = 40

                # Void rune: fall animation, lose heart, respawn (skip in edit mode)
                ru = room.rune_at(player.row, player.col)
                if not edit_mode and ru and ru.kind == 'void':
                    iw    = _iw(term)
                    game_h = term.height - 7
                    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
                    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
                    scr_r    = player.row - vr_start + 3
                    scr_c    = player.col - vc_start + 1
                    render_all(term, dungeon, player, budget, message)
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
                    render_all(term, dungeon, player, budget, message)
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
                    render_all(term, dungeon, player, budget, message)
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
                    render_all(term, dungeon, player, budget, '')
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
                    message = 'INSERT mode not learned yet.'
                    msg_ttl = 20
            elif m in ('visual', 'visual_line', 'visual_block'):
                if 'visual' in player.known_commands or 'admin' in player.known_commands:
                    player.mode = {'visual': Mode.VISUAL,
                                   'visual_line': Mode.VISUAL_LINE,
                                   'visual_block': Mode.VISUAL_BLOCK}[m]
                else:
                    message = 'VISUAL mode not learned yet.'
                    msg_ttl = 20

        elif action['type'] == 'undo':
            if edit_mode:
                if ed_undo:
                    ed_redo.append(_ed_snapshot(room, player))
                    _ed_restore(room, player, ed_undo.pop())
                    message = 'Undone.'
                else:
                    message = 'Nothing to undo.'
                msg_ttl = 15
            elif undo_stack:
                item = undo_stack.pop()
                if isinstance(item, dict):
                    redo_stack.append(_snapshot(room, player, budget))
                    player.row, player.col = item['row'], item['col']
                    budget.spent = item['spent']
                    room.entities = item['entities']
                    room.fog_cells = item['fog_cells']
                    player.keys   = item.get('keys', player.keys)
                    room.rebuild_indexes()
                else:
                    redo_stack.append((player.row, player.col, budget.spent))
                    pr, pc, ps = item
                    player.row, player.col = pr, pc
                    budget.spent = ps
                message = 'Undone.'
                msg_ttl = 15
            else:
                message = 'Nothing to undo.'
                msg_ttl = 15

        elif action['type'] == 'redo':
            if edit_mode:
                if ed_redo:
                    ed_undo.append(_ed_snapshot(room, player))
                    _ed_restore(room, player, ed_redo.pop())
                    message = 'Redone.'
                else:
                    message = 'Nothing to redo.'
                msg_ttl = 15
            elif redo_stack:
                item = redo_stack.pop()
                if isinstance(item, dict):
                    undo_stack.append(_snapshot(room, player, budget))
                    player.row, player.col = item['row'], item['col']
                    budget.spent = item['spent']
                    room.entities = item['entities']
                    room.fog_cells = item['fog_cells']
                    player.keys   = item.get('keys', player.keys)
                    room.rebuild_indexes()
                else:
                    undo_stack.append((player.row, player.col, budget.spent))
                    pr, pc, ps = item
                    player.row, player.col = pr, pc
                    budget.spent = ps

        elif action['type'] == 'interact':
            if edit_mode:
                ed_undo.append(_ed_snapshot(room, player))
                ed_redo.clear()
                item = _ed_cut(room, player.row, player.col)
                if item:
                    player.register = [item]
                    message   = f'Cut: {_clip_desc(item)}'
                else:
                    ed_undo.pop()
                    message = 'Nothing to cut here.'
                msg_ttl = 25
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
                        message = 'You found a key!'
                    else:
                        message = 'You found a scroll!'
                    msg_ttl = 30
                    interacted = True
                    if 'register' not in player.known_commands:
                        player.known_commands = player.known_commands + ['register']
                        render_all(term, dungeon, player, budget, message)
                        _show_register_tutorial(term, _iw(term), term.height - 7)
                elif cur and cur.kind == 'door':
                    undo_stack.append(_snapshot(room, player, budget))
                    redo_stack.clear()
                    col = cur.col
                    for e in room.entities:
                        if e.kind == 'door' and e.col == col:
                            room.kill_entity(e)
                    _reveal_from(room, player.row, player.col)
                    budget.spend(1)
                    message = 'Door opened.'
                    msg_ttl = 20
                    interacted = True
                if not interacted:
                    message = 'Nothing to open here.'
                    msg_ttl = 15

        elif edit_mode and action['type'] == 'substitute':
            ed_undo.append(_ed_snapshot(room, player))
            ed_redo.clear()
            items     = _ed_subst(room, player.row, player.col)
            player.register = items
            message   = 'Substituted: ' + ', '.join(_clip_desc(i) for i in items)
            msg_ttl   = 25

        elif not edit_mode and action['type'] == 'paste':
            before = action.get('before', False)
            dc = -1 if before else 1          # P → left, p → right
            target = room.entity_at(player.row, player.col + dc)
            if target and target.kind == 'locked_door':
                if player.keys > 0:
                    undo_stack.append(_snapshot(room, player, budget))
                    redo_stack.clear()
                    player.keys -= 1
                    render_all(term, dungeon, player, budget, message)
                    _unlock_animation(term, room, player,
                                      target.row, target.col,
                                      _iw(term), term.height - 7)
                    for e in room.entities:
                        if e.kind == 'locked_door' and e.col == target.col:
                            room.kill_entity(e)
                    _reveal_from(room, player.row, player.col)
                    budget.spend(1)
                    message = 'Door unlocked!'
                    msg_ttl = 25
                else:
                    player.error = 'E: No key in inventory'
            else:
                message = 'Nothing to paste here.'
                msg_ttl = 15

        elif edit_mode and action['type'] == 'paste':
            if player.register:
                ed_undo.append(_ed_snapshot(room, player))
                ed_redo.clear()
                before  = action.get('before', False)
                start_c = player.col if before else player.col + 1
                _ed_paste(room, player.row, start_c, player.register)
                message = f'Pasted {"before" if before else "after"} cursor.'
            else:
                message = 'Clipboard is empty.'
            msg_ttl = 20

        elif edit_mode and action['type'] == 'operator':
            op     = action['op']
            motion = action['motion']
            count  = action.get('count', 1)
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
                message = f'{verb} {len(all_items)} item(s) from {count} row(s).'
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
                message = f'{verb} {len(items)} item(s).'
            if op == 'y':
                ed_undo.pop()
            msg_ttl = 25

        if not edit_mode and budget.is_over:
            message = 'Over budget! Try a more efficient path. (u to undo)'
            msg_ttl = 30

        render_all(term, dungeon, player, budget, message)


# ── Save-select screen loop ───────────────────────────────────────────────────

def run_save_select(term: Terminal) -> tuple[str, str]:
    """Show the save-selection screen.

    Returns ('load', player_name) or ('back', '').
    """
    saves  = SM.list_saves()
    cursor = 0

    render_save_select(term, saves, cursor)

    while True:
        key = term.inkey(timeout=0.1)
        if not key:
            continue

        raw = str(key) if not key.is_sequence else ''

        if key.name == 'KEY_ESCAPE':
            return ('back', '')
        elif raw == 'j':
            cursor = min(cursor + 1, max(0, len(saves) - 1))
        elif raw == 'k':
            cursor = max(cursor - 1, 0)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            if saves:
                name = SM.load_player_name(saves[cursor])
                return ('load', name)

        render_save_select(term, saves, cursor)


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

    Returns {'action': 'enter', 'level': N} or {'action': 'quit'}.
    """
    visible    = [l for l in LEVELS if not l.get('admin_only') or player.name == 'admin']
    cursor_row = 0
    cmd_active = False
    cmd_line   = ''

    render_overworld(term, player, progress, cursor_row, levels=visible)

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
            render_overworld(term, player, progress, cursor_row,
                             cmd_line if cmd_active else None, levels=visible)
            continue

        # ── Navigation ────────────────────────────────────────────────────────
        raw = str(key) if not key.is_sequence else ''

        if raw == ':':
            cmd_active = True
            cmd_line   = ''
        elif raw == 'j':
            cursor_row = min(cursor_row + 1, len(visible) - 1)
        elif raw == 'k':
            cursor_row = max(cursor_row - 1, 0)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            level_id = visible[cursor_row]['id']
            if is_unlocked(level_id, progress, player.name):
                return {'action': 'enter', 'level': level_id}
            # Locked level: flash hint (no action)

        render_overworld(term, player, progress, cursor_row,
                         cmd_line if cmd_active else None, levels=visible)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Vimny — Vim dungeon crawler')
    ap.add_argument('--level', type=int, default=None, choices=[0, 1, 2, 3, 99],
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
