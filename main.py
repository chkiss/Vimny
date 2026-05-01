#!/usr/bin/env python3
"""Vimny — entry point and main game loop."""
import sys, random, time, argparse
from blessed import Terminal
import render.colors as C
from render.renderer import render_all
from render.overworld import render_overworld
from render.title import render_title, render_save_select, MENU_ITEMS as _TITLE_MENU, NAME_MAX as _NAME_MAX
from engine.player import Player
from engine.modes import Mode
from engine.budget import Budget
from engine.vim_parser import parse
from engine.world import CellType
from generation.dungeon_gen import build_dungeon_0, build_dungeon_1, build_dungeon_2
from content.levels import LEVELS, is_unlocked
import save.save_manager as SM

# ── Motion / movement helpers ─────────────────────────────────────────────────

def _apply_esc(player: Player) -> None:
    player.mode = Mode.NORMAL


def move_player(player, dr, dc, room):
    nr, nc = player.row + dr, player.col + dc
    if not room.is_passable(nr, nc):
        return False
    if room.fog_col >= 0 and nc >= room.fog_col:
        return False
    player.row, player.col = nr, nc
    return True


def _update_fog(room) -> None:
    """Advance fog_col to just past the next closed door, or clear fog if none remain."""
    closed_cols = sorted(set(e.col for e in room.entities
                             if e.kind == 'door' and e.alive))
    room.fog_col = closed_cols[0] + 1 if closed_cols else -1


def apply_motion(player, motion, count, room, target=None):
    moved = False
    for _ in range(count):
        if motion == 'h':
            moved |= move_player(player, 0, -1, room)
        elif motion == 'j':
            moved |= move_player(player, 1,  0, room)
        elif motion == 'k':
            moved |= move_player(player, -1, 0, room)
        elif motion == 'l':
            moved |= move_player(player, 0,  1, room)
        elif motion == '0':
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not room.is_passable(row, c):
                    break
                left = c
            if left != player.col:
                player.col = left
                moved = True
        elif motion == '$':
            row = player.row
            best = None
            for c in range(player.col + 1, room.cols):
                if not room.is_passable(row, c):
                    break
                if room.fog_col >= 0 and c >= room.fog_col:
                    break
                best = c
            if best is not None:
                player.col = best
                moved = True
        elif motion == '^':
            row = player.row
            left = player.col
            for c in range(player.col - 1, -1, -1):
                if not room.is_passable(row, c):
                    break
                left = c
            right = player.col
            for c in range(player.col + 1, room.cols):
                if not room.is_passable(row, c):
                    break
                if room.fog_col >= 0 and c >= room.fog_col:
                    break
                right = c
            target = left
            for c in range(left, right + 1):
                if room.rune_at(row, c):
                    target = c
                    break
            if target != player.col:
                player.col = target
                moved = True
        elif motion == 'G':
            if room.exit_pos:
                player.row, player.col = room.exit_pos
                moved = True
        elif motion == 'gg':
            player.row, player.col = room.entry
            moved = True
    return moved


# ── Animations ────────────────────────────────────────────────────────────────

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

def _iw(term):
    return min(max(term.width, 80), 120) - 2


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
    if level == 1:
        return build_dungeon_1(seed)
    if level == 2:
        return build_dungeon_2(seed)
    return build_dungeon_0(seed)


def _known_commands(level: int) -> list:
    cmds = ['h', 'j', 'k', 'l']
    if level >= 1:
        cmds += ['^', '$', '0']
    if level >= 2:
        cmds += ['count', 'x']
    return cmds


def _hint_bar(known: list) -> str:
    if 'count' in known:
        return '[N]hjkl:count-move  0:line-start  ^:first-rune  $:end  :w save  :q quit'
    if '$' in known:
        return 'hjkl:move  0:line-start  ^:first-rune  $:end  :w save  :q quit'
    return 'h/j/k/l:move  :w save  :q quit  :q! force-quit'


# ── Dungeon game loop ──────────────────────────────────────────────────────────

def run_dungeon(term: Terminal, level: int, progress: dict,
                player_name: str = 'Normand') -> dict:
    """Run one dungeon level.

    Returns {'won': bool, 'stars': int, 'action': 'wq'|'quit'|'force_quit'}.
    """
    seed    = random.randint(0, 2**31)
    dungeon = _build_dungeon(level, seed)
    room    = dungeon.room

    player  = Player(row=room.entry[0], col=room.entry[1])
    player.known_commands = _known_commands(level)
    budget  = Budget(room.budget or 20)

    key_buf  = ''
    message  = ''
    msg_ttl  = 0
    undo_stack: list[tuple[int, int, int]] = []
    redo_stack: list[tuple[int, int, int]] = []
    count_tutorial_shown = False
    at_exit  = False   # player has stepped on the exit at some point
    won      = False   # win animation has been triggered

    if level == 1:
        message = 'The Line Halls — navigate to the corridor, then use $ and ^'
        msg_ttl = 50
    elif level == 2:
        message = 'The Counting Crypts — type [N] before hjkl: try 5j or 3l'
        msg_ttl = 50

    render_all(term, dungeon, player, budget, message)

    while True:
        key = term.inkey(timeout=0.1)

        if msg_ttl > 0:
            msg_ttl -= 1
            if msg_ttl == 0:
                message = ''

        if not key:
            continue

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
                    SM.save_progress(progress, player_name)
                    message = 'Saved.'
                    msg_ttl = 30

                elif cmd == 'wq':
                    stars = _calc_stars(won, budget, room)
                    return {'won': won, 'stars': stars, 'action': 'wq'}

                elif cmd == 'q':
                    stars = _calc_stars(won, budget, room)
                    return {'won': won, 'stars': stars, 'action': 'quit'}

                elif cmd == 'q!':
                    return {'won': False, 'stars': 0, 'action': 'force_quit'}

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

        prev_pos = (player.row, player.col, budget.spent)

        if action['type'] == 'motion':
            motion = action['motion']
            count  = action.get('count', 1)
            target = action.get('target')

            if count > 1 and 'count' not in player.known_commands:
                message = "You haven't learned count motions yet."
                msg_ttl = 20
                render_all(term, dungeon, player, budget, message)
                continue

            moved = apply_motion(player, motion, count, room, target)
            if moved:
                budget.spend(_keystroke_cost(count))
                undo_stack.append(prev_pos)
                redo_stack.clear()

                if count > 1 and not count_tutorial_shown:
                    count_tutorial_shown = True
                    message = f'{count}{motion} moved {count} steps in 2 keystrokes — count is efficient!'
                    msg_ttl = 40

                # Void rune: fall animation, lose heart, respawn
                ru = room.rune_at(player.row, player.col)
                if ru and ru.kind == 'void':
                    iw    = _iw(term)
                    game_h = term.height - 6
                    vr_start = max(0, min(player.row - game_h // 2, room.rows - game_h))
                    vc_start = max(0, min(player.col - iw  // 2,    room.cols - iw))
                    scr_r    = player.row - vr_start + 3
                    scr_c    = player.col - vc_start + 1
                    render_all(term, dungeon, player, budget, message)
                    _void_fall_animation(term, scr_r, scr_c)
                    player.take_damage()
                    player.row, player.col = prev_pos[0], prev_pos[1]
                    if player.is_dead:
                        message = '** GAME OVER ** You ran out of hearts. Press r to restart.'
                        render_all(term, dungeon, player, budget, message)
                        while True:
                            k = term.inkey(timeout=None)
                            if k and str(k) == 'r':
                                break
                        seed    = random.randint(0, 2**31)
                        dungeon = _build_dungeon(level, seed)
                        room    = dungeon.room
                        player  = Player(row=room.entry[0], col=room.entry[1])
                        player.known_commands = _known_commands(level)
                        budget  = Budget(room.budget or 80)
                        undo_stack.clear()
                        redo_stack.clear()
                        key_buf = ''
                        at_exit = False
                        won     = False
                        message = 'Dungeon restarted. Good luck.'
                        msg_ttl = 20
                    else:
                        message = f'You fell into the void!  ({player.hp} ♥ remaining)'
                        msg_ttl = 25
                    render_all(term, dungeon, player, budget, message)
                    continue

                # Win / exit check
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
                message = 'INSERT mode — not needed yet. Press Esc.'
                player.mode = Mode.INSERT
                msg_ttl = 20
            elif m == 'visual':
                player.mode = Mode.VISUAL
            elif m == 'visual_line':
                player.mode = Mode.VISUAL_LINE
            elif m == 'visual_block':
                player.mode = Mode.VISUAL_BLOCK

        elif action['type'] == 'undo':
            if undo_stack:
                redo_stack.append((player.row, player.col, budget.spent))
                pr, pc, ps = undo_stack.pop()
                player.row, player.col = pr, pc
                budget.spent = ps
                message = 'Undone.'
                msg_ttl = 15
            else:
                message = 'Nothing to undo.'
                msg_ttl = 15

        elif action['type'] == 'redo':
            if redo_stack:
                undo_stack.append((player.row, player.col, budget.spent))
                pr, pc, ps = redo_stack.pop()
                player.row, player.col = pr, pc
                budget.spent = ps

        elif action['type'] == 'interact':
            interacted = False
            cur = room.entity_at(player.row, player.col)
            if cur and cur.kind == 'chest':
                cur.alive = False
                budget.spend(1)
                message = 'You looted the chest!'
                msg_ttl = 30
                interacted = True
            elif cur and cur.kind == 'door':
                col = cur.col
                for e in room.entities:
                    if e.kind == 'door' and e.col == col:
                        e.alive = False
                _update_fog(room)
                budget.spend(1)
                message = 'Door opened.'
                msg_ttl = 20
                interacted = True
            if not interacted:
                message = 'Nothing to open here.'
                msg_ttl = 15

        if budget.is_over:
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

    def _render():
        cl = cmd_buf[1:]  if cmd_buf.startswith(':') else None
        np = name_buf     if state == 'naming'        else None
        cn = pending_name if state == 'confirm'       else None
        render_title(term, cursor, has_save, cmd_line=cl, name_prompt=np, confirm_name=cn)

    _render()

    while True:
        key = term.inkey(timeout=0.1)
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
    cursor_row = 0
    cmd_active = False
    cmd_line   = ''

    render_overworld(term, player, progress, cursor_row)

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
            render_overworld(term, player, progress, cursor_row, cmd_line)
            continue

        # ── Navigation ────────────────────────────────────────────────────────
        raw = str(key) if not key.is_sequence else ''

        if raw == ':':
            cmd_active = True
            cmd_line   = ''
        elif raw == 'j':
            cursor_row = min(cursor_row + 1, len(LEVELS) - 1)
        elif raw == 'k':
            cursor_row = max(cursor_row - 1, 0)
        elif key.name == 'KEY_ENTER' or raw in ('\n', '\r'):
            level_id = LEVELS[cursor_row]['id']
            if is_unlocked(level_id, progress):
                return {'action': 'enter', 'level': level_id}
            # Locked level: flash hint (no action)

        render_overworld(term, player, progress, cursor_row,
                         cmd_line if cmd_active else None)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Vimny — Vim dungeon crawler')
    ap.add_argument('--level', type=int, default=None, choices=[0, 1, 2],
                    help='skip overworld and start at this level (debug)')
    args = ap.parse_args()

    term = Terminal()
    C.init(term)

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

            level       = ow_result['level']
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

            # :q! from inside a dungeon exits the whole game
            if dung_result['action'] == 'force_quit':
                break


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
