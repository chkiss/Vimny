# Vim Commands Reference
#
# Canonical source for hint-bar display text (read by render/hint_bar.py).
# Command set + wording follow the Vim cheat sheet at https://vim.rtorr.com/.
# One row per command (or tight group). Columns:
#   keys     — exact keystroke(s) shown in the hint bar
#   token    — known_commands() token (omitted when identical to keys)
#   desc     — concise description, hint-bar style (2–4 words)
# Section headers group rows by level SLUG for humans (identity is the slug, never
# a level number); the parser keys rows by token, so headers do not affect runtime.

## Always-on (never gated)

| keys  | token | desc                |
|-------|-------|---------------------|
| u     |       | undo                |
| :w    |       | write (save)        |
| :q    |       | quit                |
| :q!   |       | quit without saving |

## first_cave — basic movement

| keys | token | desc  |
|------|-------|-------|
| h    |       | left  |
| j    |       | down  |
| k    |       | up    |
| l    |       | right |

## line_halls — line motions

| keys | token | desc            |
|------|-------|-----------------|
| 0    |       | line start      |
| ^    |       | first non-blank |
| $    |       | end of line     |

## reliquary — delete char

| keys | token | desc        |
|------|-------|-------------|
| x    |       | delete char |

## counting_crypts — count prefix

| keys    | token | desc       |
|---------|-------|------------|
| [N]hjkl | count | count move |

## rune_halls — word motions

| keys | token | desc       |
|------|-------|------------|
| w    |       | word start |
| b    |       | word back  |
| e    |       | word end   |

## character_cataracts — find char on line

| keys  | token | desc              |
|-------|-------|-------------------|
| f{c}  | f     | jump to char      |
| F{c}  | F     | jump back to char |
| t{c}  | t     | before next char  |
| T{c}  | T     | after prev char   |

## goblin_gauntlet — repeat find + paste

| keys | token | desc    |
|------|-------|---------|
| ;    |       | repeat  |
| ,    |       | reverse |
| p    |       | paste   |

## word_forge — WORD motions

| keys | token | desc       |
|------|-------|------------|
| W    |       | WORD start |
| B    |       | WORD back  |
| E    |       | WORD end   |

## backward_vaults — backward word-end

| keys | token | desc          |
|------|-------|---------------|
| ge   |       | word-end back |
| gE   |       | WORD-end back |

## lineheads — first/last line

| keys  | token | desc          |
|-------|-------|---------------|
| G     |       | last line     |
| gg    |       | first line    |
| [N]G  |       | go to line N  |

## screen_vault — screen position

| keys | token | desc             |
|------|-------|------------------|
| H    |       | top of screen    |
| M    |       | middle of screen |
| L    |       | bottom of screen |

## bracket_vaults — bracket match

| keys | token | desc          |
|------|-------|---------------|
| %    |       | match bracket |

## runic_archives — paragraph / block jump

| keys | token | desc       |
|------|-------|------------|
| }    |       | next block |
| {    |       | prev block |

## sentence_corridor — sentence jump

| keys | token | desc          |
|------|-------|---------------|
| )    |       | next sentence |
| (    |       | prev sentence |

## sight_sanctum — visual mode

| keys      | token     | desc                 |
|-----------|-----------|----------------------|
| v         | visual    | visual mode          |
| v{m} d/c/~/p/r/J | visual_op | act on the selection |

## selection_halls — line & block selection

| keys      | token        | desc                  |
|-----------|--------------|-----------------------|
| V         | visual_line  | select whole lines    |
| <C-v>     | visual_block | select a block        |

## binders_reliquary — the Codex

| keys      | token | desc                     |
|-----------|-------|--------------------------|
| :h {name} | help  | open the Codex to a page |
| za        |       | unfold / fold a section  |
| :q        |       | close the book           |

## seekers_labyrinth — search

| keys    | token | desc        |
|---------|-------|-------------|
| /{pat}  | /     | search      |
| ?{pat}  |       | search back |
| n       |       | next match  |
| N       |       | prev match  |
| *       |       | search word |

## waypoint_sanctum — marks

| keys  | token | desc      |
|-------|-------|-----------|
| m{a}  | mark  | set mark  |
| `{a}  |       | to mark   |
| '{a}  |       | to mark ↑ |

## archivists_library — buffers, wrap, save-as

| keys      | token   | desc        |
|-----------|---------|-------------|
| :set wrap | setwrap | wrap lines  |
| :e!       | reload  | reload file |
| :w {file} | writeas | save as     |

## operators_vault — operators

| keys     | token | desc        |
|----------|-------|-------------|
| d{m}  dd | d     | delete      |
| c{m}     | c     | change      |
| cc       |       | change line |

## cipher_cell — replace + line-end delete

| keys | token | desc               |
|------|-------|--------------------|
| r{c} | r     | replace char       |
| D    | D     | delete to line end |
| X    | X     | delete before cursor |

## whole_line_annex — change (substitute char)

| keys     | token | desc       |
|----------|-------|------------|
| c{m}  cc | c     | change     |
| s        |       | substitute |

## change_extension — change shorthands

| keys | token | desc            |
|------|-------|-----------------|
| S    |       | substitute line |
| C    |       | change to end   |
| Y    | Y     | yank line       |

## quartermaster — yank + paste before

| keys     | token    | desc           |
|----------|----------|----------------|
| y{m}  yy | y        | yank           |
| P        |          | paste before   |

## echo_vault — repeat last change

| keys | token | desc          |
|------|-------|---------------|
| .    | dot   | repeat change |

## inscription_halls — insert mode

| keys | token  | desc        |
|------|--------|-------------|
| i    | insert | insert      |
| a    |        | append      |
| Esc  |        | exit insert |

## sculpting_chambers — line-open / line-anchored insert

| keys | token | desc            |
|------|-------|-----------------|
| I    |       | insert at start |
| A    |       | append at end   |
| o    |       | new line below  |
| O    |       | new line above  |

## overwrite_halls — replace mode

| keys  | token | desc         |
|-------|-------|--------------|
| R     | R     | replace mode |

## case_chambers — case change

| keys   | token | desc        |
|--------|-------|-------------|
| ~      |       | toggle case |
| gU{m}  | gU    | uppercase   |
| gu{m}  | gu    | lowercase   |
| g~{m}  | g~    | toggle case |

## joiners_gate — join

| keys | token | desc           |
|------|-------|----------------|
| J    |       | join lines     |
| gJ   |       | join, no space |

## alignment_halls — indent

| keys  | token | desc   |
|-------|-------|--------|
| >{m}  | >     | indent |
| <{m}  | <     | dedent |

## indentation_sanctum — the law

| keys  | token | desc          |
|-------|-------|---------------|
| ={m}  | =     | apply the law |

## word_enclosure — word text objects

| keys | token | desc         |
|------|-------|--------------|
| iw   |       | inner word   |
| aw   |       | a word       |
| iW   |       | inner WORD   |
| aW   |       | a WORD       |

## bracket_enclosure — paren text objects

| keys | token | desc    |
|------|-------|---------|
| i(   |       | inner ( |
| a(   |       | a ()    |

## brace_square_enclosure — bracket / brace text objects

| keys | token | desc    |
|------|-------|---------|
| i[   |       | inner [ |
| a[   |       | a []    |
| i{   |       | inner { |
| a{   |       | a {}    |

## quote_enclosure — quote text objects

| keys | token | desc       |
|------|-------|------------|
| i"   |       | inner "    |
| a"   |       | a ""       |
| i'   |       | inner '    |
| a'   |       | a ''       |

## tag_enclosure — tag text objects

| keys | token | desc      |
|------|-------|-----------|
| it   |       | inner tag |
| at   |       | a tag     |

## sentence_enclosure — sentence text objects

| keys | token | desc           |
|------|-------|----------------|
| is   |       | inner sentence |
| as   |       | a sentence     |

## paragraph_enclosure — paragraph text objects

| keys | token | desc            |
|------|-------|-----------------|
| ip   |       | inner paragraph |
| ap   |       | a paragraph     |

## spellwrights_forge — substitute & global

| keys        | token | desc            |
|-------------|-------|-----------------|
| :s/old/new/ | subst | substitute      |
| :%s//g      |       | substitute all  |
| :g/pat/d    |       | global delete   |
| &           |       | repeat last :s  |

## hall_of_echoes — macros + named registers

| keys  | token     | desc         |
|-------|-----------|--------------|
| q{a}  | q         | record macro |
| @{a}  | @         | play macro   |
| @@    |           | repeat macro |
| "{a}  | reg_named | named reg    |
