"""Pure read-only renderer. Never mutates game state."""
from __future__ import annotations
import time
from blessed import Terminal
from engine.world import Dungeon, CellType, Room
from engine.player import Player
from engine.modes import Mode, MODE_LABELS
from engine.budget import Budget
import render.colors as C
import render.symbols as S
from render.utils import inner_w as _inner_w

# ── Water animation ────────────────────────────────────────────────────────────
# Each frame: (char, rgb, duration_seconds).
# ~ frames hold their full duration; ≈ is brief — a passing wave crest.
_WATER_FRAMES = [
    ('~',  (30,  95, 200), 8.0),   # calm — mid-blue
    ('≈',  (50, 130, 230), 0.8),   # passing wave — lighter blue (brief)
    ('~',  (15,  65, 170), 8.0),   # calm — deeper blue
    ('∼',  (40, 110, 215), 8.0),   # calm — medium
]
_WATER_PERIOD = sum(d for _, _, d in _WATER_FRAMES)  # 24.8 s


def _water_glyph(row: int, col: int) -> tuple[str, int, int, int]:
    """Return (char, r, g, b) for a water cell at the current instant."""
    # Diagonal spatial offset so adjacent cells are out of phase (÷4 wave density)
    offset = (row * 0.1375 + col * 0.045) % _WATER_PERIOD
    phase  = (time.time() + offset) % _WATER_PERIOD
    t = 0.0
    for char, rgb, dur in _WATER_FRAMES:
        t += dur
        if phase < t:
            return char, *rgb
    char, rgb, _ = _WATER_FRAMES[-1]
    return char, *rgb

def _reg_display(items: list) -> str:
    """Short visible string of \" register contents for statusline."""
    if not items:
        return ''
    parts = []
    for item in items:
        if item['type'] == 'rune':
            parts.extend(item['rune'].symbols)
        elif item['type'] == 'entity':
            k = item['entity'].kind
            parts.append({'dynamite': '!', 'exit': '◉', 'door': '▬',
                          'chest': '🞔', 'chest_key': '🞔', 'wanderer': '♟',
                          'locked_door': '⊞'}.get(k, '?'))
        elif item['type'] == 'cell':
            ct = item['cell_type']
            parts.append({CellType.WALL: '█', CellType.WATER: '~',
                          CellType.WOOD_WALL: '░'}.get(ct, ' '))
    s = ''.join(parts)
    return s[:7] + '…' if len(s) > 8 else s


def _pad(s: str, width: int) -> str:
    """Pad or truncate s to exactly width visible characters."""
    # strip ANSI for length calc is complex; use len of raw string for now
    # This works well when color codes are added outside pad calls
    if len(s) < width:
        return s + ' ' * (width - len(s))
    return s[:width]

def render_all(term: Terminal, dungeon: Dungeon, player: Player,
               budget: Budget, message: str = ''):
    room   = dungeon.room
    iw     = _inner_w(term)
    output = []

    bfg = C.border_fg()
    rst = C.normal_fg()

    def border_h(left, right, fill=S.BOX_H):
        line = bfg + left + fill * iw + right + rst
        return line

    # ── Row 0: top border ──────────────────────────────────────────────────
    output.append(border_h(S.BOX_TL, S.BOX_TR))

    # ── Row 1: status bar ─────────────────────────────────────────────────
    full_h  = player.hp // 2
    half_h  = player.hp % 2
    empty_h = player.max_hp // 2 - full_h - half_h
    hp_str  = (C.heart_full()  + S.HEART_FULL  + rst) * full_h
    hp_str += (C.heart_half()  + S.HEART_HALF  + rst) * half_h
    hp_str += (C.heart_empty() + S.HEART_EMPTY + rst) * empty_h

    mode    = player.mode
    ml      = MODE_LABELS[mode]
    if mode == Mode.NORMAL:
        mode_s = C.mode_normal() + ml + rst
    elif mode == Mode.INSERT:
        mode_s = C.mode_insert() + ml + rst
    elif mode in (Mode.VISUAL, Mode.VISUAL_LINE, Mode.VISUAL_BLOCK):
        mode_s = C.mode_visual() + ml + rst
    else:
        mode_s = C.mode_command() + ml + rst

    par_val  = room.par or 0
    spent    = budget.spent
    if par_val > 0:
        if spent <= par_val:
            keys_color = C.budget_ok()
        elif spent <= int(par_val * 1.5):
            keys_color = C.budget_low()
        else:
            keys_color = C.budget_crit()
    else:
        keys_color = C.normal_fg()

    keys_s   = keys_color + f'Keys:{spent:2d}' + rst
    budget_s = C.hint_fg() + f' Budget:{budget.total:2d}' + rst
    par_s    = C.hint_fg() + f' Par:{room.par or "-"}' + rst

    inv_keys = player.keys
    key_s = (C.key_fg() + S.KEY * inv_keys + rst) if inv_keys else ''

    dname = dungeon.name[:24]
    # Build status line (visible chars only for padding, approximate)
    key_plain = S.KEY * inv_keys if inv_keys else ''
    status_plain = f'  {"♥"*full_h}{"♡"*half_h}{"░"*empty_h}  {key_plain}  {dname}  {ml}  Keys:{spent:2d} Budget:{budget.total:2d}  Par:{room.par or "-"}'
    padding = max(0, iw - len(status_plain))
    status_line = (bfg + S.BOX_V + rst +
                   f'  {hp_str}  ' +
                   key_s + ('  ' if inv_keys else '') +
                   C.normal_fg() + dname + '  ' +
                   mode_s + '  ' + keys_s + ' ' + budget_s + par_s +
                   ' ' * padding +
                   bfg + S.BOX_V + rst)
    output.append(status_line)

    # ── Row 2: separator ──────────────────────────────────────────────────
    output.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Game area ─────────────────────────────────────────────────────────
    # 7 rows: top_border, status, top_sep, [game_h rows], statusline, bot_sep, hint, bot_border
    game_h  = term.height - 7
    room_display_rows = min(room.rows, game_h)
    room_display_cols = min(room.cols, iw)

    # Viewport: centre on player
    vr_start = max(0, min(player.row - game_h // 2,  room.rows - game_h))
    vc_start = max(0, min(player.col - iw // 2,       room.cols - iw))
    vr_start = max(0, vr_start)
    vc_start = max(0, vc_start)

    floor_bg = C.floor_bg()
    wall_bg  = C.wall_bg()

    for screen_r in range(game_h):
        room_r = screen_r + vr_start
        line   = bfg + S.BOX_V + rst

        if room_r >= room.rows:
            line += ' ' * iw
        else:
            for screen_c in range(iw):
                room_c = screen_c + vc_start
                if room_c >= room.cols:
                    line += ' '
                    continue

                ct = room.cells[room_r][room_c]

                # Player?
                if room_r == player.row and room_c == player.col:
                    line += floor_bg + C.player_fg() + S.PLAYER + C.normal_fg()
                    continue

                # Fog?
                if (room_r, room_c) in room.fog_cells:
                    line += wall_bg + ' ' + C.normal_fg()
                    continue

                # Entity?
                ent = room.entity_at(room_r, room_c)
                if ent:
                    if ent.kind == 'exit':
                        line += floor_bg + C.exit_fg() + S.EXIT + C.normal_fg()
                    elif ent.kind in ('chest', 'chest_key', 'chest_scroll'):
                        line += floor_bg + C.chest_fg() + S.CHEST + C.normal_fg()
                    elif ent.kind == 'door':
                        line += floor_bg + C.door_fg() + S.DOOR_LOCKED + C.normal_fg()
                    elif ent.kind == 'locked_door':
                        line += floor_bg + C.locked_door_fg() + S.DOOR_LOCKED_KEY + C.normal_fg()
                    elif ent.kind == 'dynamite':
                        line += floor_bg + C.dynamite_fg() + S.DYNAMITE + C.normal_fg()
                    elif ent.kind == 'wanderer':
                        efg = C.enemy_frozen() if mode == Mode.VISUAL else C.enemy_fg()
                        line += floor_bg + efg + S.ENEMY_WANDERER + C.normal_fg()
                    elif ent.kind == 'entry_marker':
                        line += floor_bg + C.hint_fg() + S.PLAYER + C.normal_fg()
                    else:
                        line += floor_bg + '?' + C.normal_fg()
                    continue

                # Rune cluster?
                ru = room.rune_at(room_r, room_c)
                if ru:
                    idx = room_c - ru.col
                    sym = ru.symbols[idx]
                    rfg = {'ancient': C.rune_ancient(), 'verdant': C.rune_verdant(),
                           'void': C.rune_void(), 'ember': C.rune_ember()}.get(ru.kind, C.normal_fg())
                    line += floor_bg + rfg + sym + C.normal_fg()
                    continue

                # Cell type
                if ct == CellType.WATER:
                    ch, wr, wg, wb = _water_glyph(room_r, room_c)
                    line += C.water_bg() + C.water_fg(wr, wg, wb) + ch + C.normal_fg()
                elif ct == CellType.WALL:
                    line += wall_bg + ' ' + C.normal_fg()
                elif ct == CellType.WOOD_WALL:
                    if room.wood_damage.get((room_r, room_c), 0):
                        line += (C.wood_wall_damaged_bg() + C.wood_wall_damaged_fg()
                                 + S.WOOD_WALL_DAMAGED + C.normal_fg())
                    else:
                        line += C.wood_wall_bg() + ' ' + C.normal_fg()
                else:
                    line += floor_bg + ' ' + C.normal_fg()

        line += bfg + S.BOX_V + rst
        output.append(line)

    # ── Vim statusline / command line ─────────────────────────────────────
    pos_str  = f'{player.row},{player.col}'

    if room.rows <= game_h:
        scroll = 'All'
    elif vr_start == 0:
        scroll = 'Top'
    elif vr_start + game_h >= room.rows:
        scroll = 'Bot'
    else:
        pct    = int((vr_start + game_h // 2) / room.rows * 100)
        scroll = f'{pct}%'

    sl_bg  = C.statusline_bg()
    sl_fg  = C.statusline_fg()
    sl_w   = iw + 2

    if player.error:
        # Vim-style error: red background, white text
        err_pad = max(0, sl_w - len(player.error) - 1)
        output.append(C.error_bg() + C.error_fg() + ' ' + player.error +
                      ' ' * err_pad + rst)
    elif mode == Mode.COMMAND:
        # Command line: show typed command flush-left, no ruler
        cmd_text = ':' + player.cmd_line
        sl_pad   = max(0, sl_w - len(cmd_text))
        output.append(sl_bg + C.mode_command() + cmd_text +
                      sl_fg + ' ' * sl_pad + rst)
    else:
        # Statusline: mode label left, position+scroll right
        sl_label = MODE_LABELS[mode]
        if mode == Mode.NORMAL:
            sl_mode_color = C.mode_normal()
        elif mode == Mode.INSERT:
            sl_mode_color = C.mode_insert()
        else:
            sl_mode_color = C.mode_visual()
        sl_right = f'{pos_str}   {scroll} '
        if 'register' in player.known_commands:
            reg_content = _reg_display(player.register)
            reg_s   = C.key_fg() + f'  "{reg_content}' + sl_fg
            reg_vis = 3 + len(reg_content)  # len('  "') + content
        else:
            reg_s   = ''
            reg_vis = 0
        sl_mid   = max(0, sl_w - len(sl_label) - 2 - reg_vis - len(sl_right))
        output.append(sl_bg + sl_mode_color + ' ' + sl_label + ' ' +
                      sl_bg + sl_fg + reg_s + ' ' * sl_mid + sl_right + rst)

    # ── Bottom separator (answer sheet for admin) ─────────────────────────
    if room.answer:
        ans_text = f' ▸ {room.answer}'
        ans_pad  = max(0, iw - len(ans_text))
        output.append(bfg + S.BOX_LT + rst +
                      C.budget_ok() + ans_text[:iw] + rst +
                      ' ' * ans_pad +
                      bfg + S.BOX_RT + rst)
    else:
        output.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Hint bar ──────────────────────────────────────────────────────────
    known = player.known_commands
    if 'editor' in known:
        hint_text = 'x:delete (cut) char  s:toggle wall  dd/yy:delete/yank line  d/y{m}:cut/yank range  p/P:put (paste)  :q quit'
    elif 'count' in known:
        hint_text = '[N]hjkl:count move  0:jump to start of line  ^:first non-blank  $:jump to end of line  x:delete (cut) char  :w write  :q quit'
    elif '$' in known:
        hint_text = 'hjkl:move cursor  0:jump to start of line  ^:first non-blank  $:jump to end of line  :w write  :q quit'
    else:
        hint_text = 'h/j/k/l:move cursor  :w write (save)  :q quit  :q! quit without saving'
    if 'admin' in known:
        hint_text += '  :e refresh'
    hint_text = hint_text[:iw]
    hint = C.hint_fg() + hint_text + rst
    output.append(bfg + S.BOX_V + rst + hint +
                  ' ' * max(0, iw - len(hint_text)) + bfg + S.BOX_V + rst)

    # ── Bottom border ──────────────────────────────────────────────────────
    output.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(output), end='', flush=True)

    # ── Message overlay (last row of game area, printed separately) ────────
    if message:
        msg_row = term.height - 5
        print(term.move_yx(msg_row, 1) + C.budget_low() + _pad(message, iw) + rst,
              end='', flush=True)
