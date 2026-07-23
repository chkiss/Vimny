# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Palette B — The Buffer. The dungeon IS a terminal: cold-dark backgrounds, phosphor UI,
amber only where the wizard's world bleeds through. Stone is syntax. Data streams run cyan."""

from blessed import Terminal

_term = None

def init(term: Terminal):
    global _term
    _term = term

def t():
    return _term

# Color helpers — call after init()
def wall_bg():       return _term.on_color_rgb(12, 12, 20)       # void-black, screen off
def floor_bg():      return _term.on_color_rgb(24, 24, 32)       # dark slate, terminal idle
def visual_sel_bg(): return _term.on_color_rgb(30, 50, 90)       # cold selection, vim-blue
def threat_sel_bg(): return _term.on_color_rgb(95, 20, 28)       # warden's gaze, blood-crimson
def search_hl_bg():  return _term.on_color_rgb(70, 60, 12)       # hlsearch — dim amber glow
def search_cur_bg(): return _term.on_color_rgb(150, 120, 18)     # incsearch target — bright amber
def player_fg():     return _term.bright_white                    # cursor: sharp, no warmth
def enemy_fg():      return _term.color_rgb(100, 155, 80)        # muted olive, enemy life
def zombie_fg():     return _term.color_rgb(120, 190, 95)        # sickly green, the risen dead
def ally_fg():       return _term.color_rgb(90, 175, 235)        # loyal blue, a hound on your side
def critter_fg():    return _term.color_rgb(200, 180, 140)       # warm tan, a harmless cat
def enemy_frozen():  return _term.color_rgb(80, 200, 240)        # ice-blue, frozen state
def boss_fg():       return _term.color_rgb(210, 35, 45)         # hard red, critical threat
# Impostor Wardens (goblin tag='echo') — a spread of reds centred on the Warden's own
# boss_fg (210,35,45). Index 0 is a near-perfect copy; the rest drift a shade off, so a
# crowd of them reads as "a myriad of Wardens" with the real one hidden among them.
_ECHO_SHADES = [
    (210,  35,  45),   # 0 — the perfect impostor (= boss_fg)
    (195,  55,  60),   # 1 — duskier
    (225,  60,  50),   # 2 — hotter
    (180,  40,  55),   # 3 — crimson-leaning
    (205,  30,  70),   # 4 — rose-tinted
    (170,  60,  48),   # 5 — brick
    (220,  80,  72),   # 6 — washed pink
    (160,  38,  46),   # 7 — deep oxblood
]
def boss_echo_fg(shade=0):                                       # a false Warden (Hunt impostor)
    r, g, b = _ECHO_SHADES[shade % len(_ECHO_SHADES)]
    return _term.color_rgb(r, g, b)
def heart_full():    return _term.color_rgb(215, 45, 45)         # arterial red, full HP
def heart_half():    return _term.color_rgb(210, 135, 25)        # ember amber, half HP
def heart_empty():   return _term.color_rgb(50, 50, 60)          # dim grey, spent HP
def dynamite_fg():   return _term.color_rgb(250, 85, 10)         # hot orange, unstable
def expl_near():     return _term.bold + _term.bright_white       # blast core, maximum
def expl_mid():      return _term.color_rgb(255, 150, 20) + _term.bold  # mid-ring amber
def expl_far():      return _term.color_rgb(190, 65, 10)         # outer bloom, cooling
def exit_fg():       return _term.color_rgb(0, 230, 160)         # cyan-green, portal open
def chest_fg():        return _term.color_rgb(215, 175, 35)      # old gold, wizard treasure
def door_fg():         return _term.color_rgb(65, 75, 90)        # blue-grey, inert door
def locked_door_fg():  return _term.color_rgb(145, 115, 25)      # tarnished gold, locked
def key_fg():          return _term.color_rgb(215, 175, 35)      # matches chest, same loot tier
def key_gold_fg():     return _term.color_rgb(250, 190, 15)      # bright gold, master key
def key_red_fg():      return _term.color_rgb(205, 50, 50)       # danger red, restricted zone
def key_blue_fg():     return _term.color_rgb(70, 135, 225)      # cold blue, data-locked
def rune_ancient():  return _term.color_rgb(90, 95, 175)         # indigo-slate, old glyphs
def rune_verdant():  return _term.color_rgb(70, 145, 75)         # moss amber, living rune
def rune_void():     return _term.color_rgb(125, 55, 170)        # deep violet, erasure
def rune_ember():    return _term.color_rgb(175, 100, 35)        # sepia amber, wizard warmth
def rune_pedestal(): return _term.color_rgb(120, 70, 30)         # dying embers, a cold brazier
def rgb_fg(rgb):     return _term.color_rgb(*rgb)                # animated colors (flame flicker)

# The Warden Eternal's aura + the worn-hat cursor: a slow "breathing" shimmer
# cycling violet → periwinkle → white → blue. `phase` (float, wraps at 1.0)
# is driven off time in the renderer; stops are interpolated for a smooth glow.
_SHIMMER = [
    (150,  90, 220),   # violet
    (150, 160, 235),   # periwinkle
    (235, 240, 255),   # near-white
    ( 80, 140, 235),   # blue
]
def shimmer_fg(phase=0.0):
    n = len(_SHIMMER)
    x = (phase % 1.0) * n
    i = int(x); f = x - i
    r0, g0, b0 = _SHIMMER[i % n]
    r1, g1, b1 = _SHIMMER[(i + 1) % n]
    return _term.color_rgb(int(r0 + (r1 - r0) * f),
                           int(g0 + (g1 - g0) * f),
                           int(b0 + (b1 - b0) * f))

def budget_ok():     return _term.color_rgb(0, 210, 90)          # phosphor green, plenty left
def budget_low():    return _term.color_rgb(215, 195, 35)        # amber caution, watch it
def budget_crit():   return _term.color_rgb(215, 40, 40)         # hard red, nearly spent

def mode_normal():   return _term.color_rgb(0, 210, 90)          # phosphor green, vim NORMAL
def mode_insert():   return _term.color_rgb(215, 195, 35)        # amber, INSERT alert
def mode_visual():   return _term.color_rgb(80, 155, 230)        # cool blue, VISUAL select
def mode_command():  return _term.color_rgb(185, 185, 195)       # cool silver, command line

def answer_consumed(): return _term.color_rgb(60, 65, 75)        # near-invisible, spent hint
def answer_warn():     return _term.color_rgb(215, 100, 10)      # orange, budget risk

def hint_fg():       return _term.color_rgb(85, 95, 115)         # blue-grey, ambient hint
def border_fg():     return _term.color_rgb(45, 55, 80)          # dim terminal frame
def normal_fg():     return _term.normal

def statusline_bg(): return _term.on_color_rgb(12, 12, 20)       # matches wall — blends with surround
def statusline_fg(): return _term.color_rgb(160, 170, 190)       # cool silver, readable
def error_bg():      return _term.on_color_rgb(170, 25, 25)      # dark red, error state
def error_fg():      return _term.bright_white                    # sharp contrast on error
def cmd_cursor_bg(): return _term.on_color_rgb(185, 185, 195)    # the cmdline block cursor
def cmd_cursor_fg(): return _term.color_rgb(12, 12, 20)          # dark glyph under the block

def water_bg():              return _term.on_color_rgb(5, 15, 55)        # deep data-stream blue
def water_fg(r, g, b):       return _term.color_rgb(r, g, b)

def wood_wall_bg():          return _term.on_color_rgb(80, 45, 14)       # dark timber, warm intruder
def wood_wall_damaged_bg():  return _term.on_color_rgb(48, 24, 5)        # charred, near-void
def wood_wall_damaged_fg():  return _term.color_rgb(150, 95, 38)         # splinter amber, damage

def horse_fg():  return _term.color_rgb(178, 150, 110)   # dun roan, the wizard's old horse

def dir_fg():    return _term.color_rgb(80, 145, 220)    # electric netrw blue, directory
def entry_fg():  return _term.color_rgb(205, 210, 215)   # cool near-white, file entry
def sel_bg():    return _term.on_color_rgb(20, 28, 45)   # cold cursor line, screen glow
