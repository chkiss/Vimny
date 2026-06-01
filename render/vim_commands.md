# Vim Commands Reference
#
# Canonical source for hint-bar display text (read by render/hint_bar.py).
# One row per command (or tight group). Columns:
#   keys     — exact keystroke(s) shown in the hint bar
#   token    — known_commands() token (omitted when identical to keys)
#   desc     — concise description, hint-bar style (2–4 words)
# Section headers group rows by curriculum level for humans; the parser keys
# rows by token, so section order/labels do not affect runtime.

## Always-on (never gated, shown at L0 only)

| keys  | token | desc                |
|-------|-------|---------------------|
| u     |       | undo                |
| :w    |       | write (save)        |
| :q    |       | quit                |
| :q!   |       | quit without saving |

## L0 — basic movement

| keys | token | desc  |
|------|-------|-------|
| h    |       | left  |
| j    |       | down  |
| k    |       | up    |
| l    |       | right |

## L1 — line motions

| keys | token | desc            |
|------|-------|-----------------|
| 0    |       | line start      |
| ^    |       | first non-blank |
| $    |       | end of line     |

## L1.1 — The Reliquary (delete char)

| keys | token | desc        |
|------|-------|-------------|
| x    |       | delete char |

## L2 — count prefix

| keys    | token | desc       |
|---------|-------|------------|
| [N]hjkl | count | count move |

## L3 — word motions

| keys | token | desc       |
|------|-------|------------|
| w    |       | word start |
| b    |       | word back  |
| e    |       | word end   |

## L4 — find char on line

| keys  | token | desc              |
|-------|-------|-------------------|
| f{c}  | f     | jump to char      |
| F{c}  | F     | jump back to char |
| t{c}  | t     | before next char  |
| T{c}  | T     | after prev char   |

## L5 — repeat find + paste

| keys | token | desc    |
|------|-------|---------|
| ;    |       | repeat  |
| ,    |       | reverse |
| p    |       | paste   |

## L6 — WORD motions

| keys | token | desc       |
|------|-------|------------|
| W    |       | WORD start |
| B    |       | WORD back  |
| E    |       | WORD end   |

## L7 — backward word-end

| keys | token | desc          |
|------|-------|---------------|
| ge   |       | word-end back |
| gE   |       | WORD-end back |

## L8 — first/last line

| keys  | token | desc          |
|-------|-------|---------------|
| G     |       | last line     |
| gg    |       | first line    |
| [N]G  |       | go to line N  |

## L9 — screen position

| keys | token | desc             |
|------|-------|------------------|
| H    |       | top of screen    |
| M    |       | middle of screen |
| L    |       | bottom of screen |

## L10 — bracket match

| keys | token | desc          |
|------|-------|---------------|
| %    |       | match bracket |

## L12 — paragraph / block jump

| keys | token | desc       |
|------|-------|------------|
| }    |       | next block |
| {    |       | prev block |

## L13 — sentence jump

| keys | token | desc          |
|------|-------|---------------|
| )    |       | next sentence |
| (    |       | prev sentence |

## L14 — visual mode

| keys | token  | desc        |
|------|--------|-------------|
| v    | visual | visual mode |

## L15 — search

| keys    | token | desc        |
|---------|-------|-------------|
| /{pat}  | /     | search      |
| ?{pat}  |       | search back |
| n       |       | next match  |
| N       |       | prev match  |
| *       |       | search word |

## L16 — marks

| keys  | token | desc      |
|-------|-------|-----------|
| m{a}  | mark  | set mark  |
| `{a}  |       | to mark   |
| '{a}  |       | to mark ↑ |

## L18 — operators

| keys   | token | desc       |
|--------|-------|------------|
| d{m}   | d     | delete     |
| dd     |       | delete line|
| c{m}   | c     | change     |
| cc     |       | change line|
| s      |       | substitute |

## L19 — substitute line

| keys | token | desc             |
|------|-------|------------------|
| S    |       | substitute line  |

## L20 — yank + named registers

| keys     | token    | desc           |
|----------|----------|----------------|
| y{m}     | y        | yank           |
| yy       |          | yank line      |
| P        |          | paste before   |
| "{r}{op} | register | named register |

## L22 — repeat last change

| keys | token | desc          |
|------|-------|---------------|
| .    | dot   | repeat change |

## L23 — insert mode

| keys | token  | desc           |
|------|--------|----------------|
| i    | insert | insert         |
| a    |        | append         |
| o    |        | new line below |
| O    |        | new line above |
| I    |        | insert at start|
| A    |        | append at end  |
| Esc  |        | exit insert    |

## L25 — replace

| keys  | token | desc         |
|-------|-------|--------------|
| r{c}  | r     | replace char |
| R     |       | replace mode |

## L26 — case change

| keys   | token | desc        |
|--------|-------|-------------|
| ~      |       | toggle case |
| gU{m}  | gU    | uppercase   |
| gu{m}  | gu    | lowercase   |
| g~{m}  | g~    | toggle case |

## L27 — join

| keys | token | desc           |
|------|-------|----------------|
| J    |       | join lines     |
| gJ   |       | join, no space |

## L28 — indent

| keys  | token | desc   |
|-------|-------|--------|
| >{m}  | >     | indent |
| <{m}  | <     | dedent |

## L30 — word text objects

| keys | token | desc       |
|------|-------|------------|
| iw   |       | inner word |
| aw   |       | a word     |

## L31 — paren text objects

| keys | token | desc    |
|------|-------|---------|
| i(   |       | inner ( |
| a(   |       | a ()    |

## L32 — bracket / brace text objects

| keys | token | desc    |
|------|-------|---------|
| i[   |       | inner [ |
| a[   |       | a []    |
| i{   |       | inner { |
| a{   |       | a {}    |

## L33 — quote text objects

| keys | token | desc       |
|------|-------|------------|
| i"   |       | inner "    |
| a"   |       | a ""       |
| i'   |       | inner '    |
| a'   |       | a ''       |

## L34 — tag text objects

| keys | token | desc      |
|------|-------|-----------|
| it   |       | inner tag |
| at   |       | a tag     |

## L35 — sentence text objects

| keys | token | desc           |
|------|-------|----------------|
| is   |       | inner sentence |
| as   |       | a sentence     |

## L36 — paragraph text objects

| keys | token | desc            |
|------|-------|-----------------|
| ip   |       | inner paragraph |
| ap   |       | a paragraph     |

## L38 — macros + named registers

| keys  | token     | desc         |
|-------|-----------|--------------|
| q{a}  | q         | record macro |
| @{a}  | @         | play macro   |
| @@    |           | repeat macro |
| "{a}  | reg_named | named reg    |
