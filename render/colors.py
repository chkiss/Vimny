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
def mega_safe_bg():  return _term.on_color_rgb(18, 70, 45)       # the lit refuge stone — safe green (Warden Pathfinder)
def player_fg():     return _term.bright_white                    # cursor: sharp, no warmth
def enemy_fg():      return _term.color_rgb(100, 155, 80)        # muted olive, enemy life
def enemy_frozen():  return _term.color_rgb(80, 200, 240)        # ice-blue, frozen state
def boss_fg():       return _term.color_rgb(210, 35, 45)         # hard red, critical threat
def boss_echo_fg():  return _term.color_rgb(150, 80, 90)         # washed-out red, a false Warden (Hunt impostor)
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

def water_bg():              return _term.on_color_rgb(5, 15, 55)        # deep data-stream blue
def water_fg(r, g, b):       return _term.color_rgb(r, g, b)

def wood_wall_bg():          return _term.on_color_rgb(80, 45, 14)       # dark timber, warm intruder
def wood_wall_damaged_bg():  return _term.on_color_rgb(48, 24, 5)        # charred, near-void
def wood_wall_damaged_fg():  return _term.color_rgb(150, 95, 38)         # splinter amber, damage

def dir_fg():    return _term.color_rgb(80, 145, 220)    # electric netrw blue, directory
def entry_fg():  return _term.color_rgb(205, 210, 215)   # cool near-white, file entry
def sel_bg():    return _term.on_color_rgb(20, 28, 45)   # cold cursor line, screen glow
