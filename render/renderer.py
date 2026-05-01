"""Pure read-only renderer. Never mutates game state."""
from __future__ import annotations
from blessed import Terminal
from engine.world import Dungeon, CellType, Room
from engine.player import Player
from engine.modes import Mode, MODE_LABELS
from engine.budget import Budget
import render.colors as C
import render.symbols as S

FRAME_W = 80   # minimum; expands up to 120

def _inner_w(term: Terminal) -> int:
    return min(max(term.width, FRAME_W), 120) - 2

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
    hp_str  = (C.heart_full()  + S.HEART_FULL  + rst) * player.hp
    hp_str += (C.heart_empty() + S.HEART_EMPTY + rst) * (player.max_hp - player.hp)

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

    dname = dungeon.name[:24]
    # Build status line (visible chars only for padding, approximate)
    status_plain = f'  {"♥"*player.hp}{"░"*(player.max_hp-player.hp)}  {dname}  {ml}  Keys:{spent:2d} Budget:{budget.total:2d}  Par:{room.par or "-"}'
    padding = max(0, iw - len(status_plain))
    status_line = (bfg + S.BOX_V + rst +
                   f'  {hp_str}  ' +
                   C.normal_fg() + dname + '  ' +
                   mode_s + '  ' + keys_s + ' ' + budget_s + par_s +
                   ' ' * padding +
                   bfg + S.BOX_V + rst)
    output.append(status_line)

    # ── Row 2: separator ──────────────────────────────────────────────────
    output.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Game area ─────────────────────────────────────────────────────────
    # 6 chrome rows: top_border, status, top_sep, bot_sep, hint, bot_border
    game_h  = term.height - 6
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
                if room.fog_col >= 0 and room_c >= room.fog_col:
                    line += wall_bg + ' ' + C.normal_fg()
                    continue

                # Entity?
                ent = room.entity_at(room_r, room_c)
                if ent:
                    if ent.kind == 'exit':
                        line += floor_bg + C.exit_fg() + S.EXIT + C.normal_fg()
                    elif ent.kind == 'chest':
                        line += floor_bg + C.chest_fg() + S.CHEST + C.normal_fg()
                    elif ent.kind == 'door':
                        line += floor_bg + C.door_fg() + S.DOOR_LOCKED + C.normal_fg()
                    elif ent.kind == 'wanderer':
                        efg = C.enemy_frozen() if mode == Mode.VISUAL else C.enemy_fg()
                        line += floor_bg + efg + S.ENEMY_WANDERER + C.normal_fg()
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
                if ct == CellType.WALL:
                    line += wall_bg + ' ' + C.normal_fg()
                else:
                    line += floor_bg + ' ' + C.normal_fg()

        line += bfg + S.BOX_V + rst
        output.append(line)

    # ── Bottom separator ───────────────────────────────────────────────────
    output.append(border_h(S.BOX_LT, S.BOX_RT))

    # ── Hint / command bar ─────────────────────────────────────────────────
    if mode == Mode.COMMAND:
        cmd_text = ':' + player.cmd_line
        output.append(C.mode_command() + cmd_text +
                      ' ' * max(0, term.width - len(cmd_text)) + rst)
    else:
        known = player.known_commands
        if 'count' in known:
            hint_text = '[N]hjkl:count-move  0:line-start  ^:first-rune  $:end  x:open  :w save  :q quit'
        elif '$' in known:
            hint_text = 'hjkl:move  0:line-start  ^:first-rune  $:end  :w save  :q quit'
        else:
            hint_text = 'h/j/k/l:move  :w save  :q quit  :q! force-quit'
        hint = C.hint_fg() + hint_text + rst
        output.append(bfg + S.BOX_V + rst + hint +
                      ' ' * max(0, iw - len(hint_text)) + bfg + S.BOX_V + rst)

    # ── Bottom border ──────────────────────────────────────────────────────
    output.append(border_h(S.BOX_BL, S.BOX_BR))

    print(term.home + '\n'.join(output), end='', flush=True)

    # ── Message overlay (last row of game area, printed separately) ────────
    if message:
        msg_row = term.height - 4
        print(term.move_yx(msg_row, 1) + C.budget_low() + _pad(message, iw) + rst,
              end='', flush=True)
