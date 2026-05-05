from blessed import Terminal

_term = None

def init(term: Terminal):
    global _term
    _term = term

def t():
    return _term

# Color helpers — call after init()
def wall_bg():       return _term.on_color_rgb(15, 15, 20)
def floor_bg():      return _term.on_color_rgb(28, 28, 35)
def player_fg():     return _term.bright_white
def enemy_fg():      return _term.color_rgb(220, 120, 20)
def enemy_frozen():  return _term.color_rgb(100, 180, 255)
def boss_fg():       return _term.color_rgb(200, 30, 30)
def heart_full():    return _term.color_rgb(220, 40, 40)
def heart_empty():   return _term.color_rgb(60, 60, 60)
def exit_fg():       return _term.bright_green
def chest_fg():      return _term.color_rgb(220, 180, 40)
def door_fg():       return _term.color_rgb(80, 80, 80)
def rune_ancient():  return _term.color_rgb(80, 80, 160)
def rune_verdant():  return _term.color_rgb(60, 130, 60)
def rune_void():     return _term.color_rgb(110, 60, 160)
def rune_ember():    return _term.color_rgb(160, 90, 40)

def budget_ok():     return _term.color_rgb(60, 200, 60)
def budget_low():    return _term.color_rgb(220, 200, 40)
def budget_crit():   return _term.color_rgb(220, 40, 40)

def mode_normal():   return _term.color_rgb(60, 200, 60)
def mode_insert():   return _term.color_rgb(220, 200, 40)
def mode_visual():   return _term.color_rgb(180, 60, 200)
def mode_command():  return _term.white

def hint_fg():       return _term.color_rgb(90, 90, 90)
def border_fg():     return _term.color_rgb(80, 80, 100)
def normal_fg():     return _term.normal

def statusline_bg(): return _term.on_color_rgb(40, 40, 55)
def statusline_fg(): return _term.color_rgb(180, 180, 200)
def error_bg():      return _term.on_color_rgb(180, 30, 30)
def error_fg():      return _term.bright_white
