"""Tests for engine/vim_parser.py — two-char sequences, operators, standalone commands."""
import pytest
from engine.vim_parser import parse
from engine.modes import Mode


# ── Incomplete sequences → None ───────────────────────────────────────────────

class TestIncomplete:
    def test_empty_buffer(self):
        action, buf = parse('', Mode.NORMAL)
        assert action is None
        assert buf == ''

    def test_count_only_is_incomplete(self):
        action, buf = parse('3', Mode.NORMAL)
        assert action is None

    def test_f_without_target_is_incomplete(self):
        action, buf = parse('f', Mode.NORMAL)
        assert action is None

    def test_F_without_target_is_incomplete(self):
        action, buf = parse('F', Mode.NORMAL)
        assert action is None

    def test_t_without_target_is_incomplete(self):
        action, buf = parse('t', Mode.NORMAL)
        assert action is None

    def test_T_without_target_is_incomplete(self):
        action, buf = parse('T', Mode.NORMAL)
        assert action is None

    def test_g_alone_is_incomplete(self):
        action, buf = parse('g', Mode.NORMAL)
        assert action is None

    def test_operator_alone_is_incomplete(self):
        for op in ('d', 'y', 'c'):
            action, buf = parse(op, Mode.NORMAL)
            assert action is None, f"'{op}' should be incomplete"

    def test_operator_with_count_only_is_incomplete(self):
        action, buf = parse('d3', Mode.NORMAL)
        assert action is None


# ── f / F / t / T two-char sequences ─────────────────────────────────────────

class TestFindChar:
    def test_f_target(self):
        action, remaining = parse('fx', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'f', 'target': 'x', 'count': 1}
        assert remaining == ''

    def test_F_target(self):
        action, remaining = parse('F∘', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'F', 'target': '∘', 'count': 1}

    def test_t_target(self):
        action, remaining = parse('ta', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 't', 'target': 'a', 'count': 1}

    def test_T_target(self):
        action, remaining = parse('Tb', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'T', 'target': 'b', 'count': 1}

    def test_count_before_f(self):
        action, remaining = parse('3f∘', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'f', 'target': '∘', 'count': 3}

    def test_f_leaves_remaining(self):
        action, remaining = parse('fxl', Mode.NORMAL)
        assert action['motion'] == 'f'
        assert remaining == 'l'

    def test_f_with_space_target(self):
        action, _ = parse('f ', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'f', 'target': ' ', 'count': 1}


# ── gg ────────────────────────────────────────────────────────────────────────

class TestGG:
    def test_gg_motion(self):
        action, remaining = parse('gg', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'gg', 'count': 1}
        assert remaining == ''

    def test_count_gg(self):
        action, _ = parse('5gg', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'gg', 'count': 5}

    def test_gg_leaves_remaining(self):
        action, remaining = parse('ggl', Mode.NORMAL)
        assert action['motion'] == 'gg'
        assert remaining == 'l'

    def test_ge_motion(self):
        action, remaining = parse('ge', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'ge', 'count': 1}
        assert remaining == ''

    def test_gE_motion(self):
        action, _ = parse('gE', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'gE', 'count': 1}

    def test_count_ge(self):
        action, _ = parse('3ge', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'ge', 'count': 3}

    def test_unknown_g_sequence(self):
        action, remaining = parse('gx', Mode.NORMAL)
        assert action == {'type': 'unknown'}
        assert remaining == ''

    def test_operator_with_ge_motion(self):
        action, _ = parse('dge', Mode.NORMAL)
        assert action['op'] == 'd'
        assert action['motion'] == 'ge'

    def test_operator_with_gE_motion(self):
        action, _ = parse('ygE', Mode.NORMAL)
        assert action['op'] == 'y'
        assert action['motion'] == 'gE'


# ── Operators: d / y / c ─────────────────────────────────────────────────────

class TestOperators:
    def test_dd_line_operator(self):
        action, _ = parse('dd', Mode.NORMAL)
        assert action == {'type': 'operator', 'op': 'd', 'motion': 'line', 'count': 1}

    def test_yy_line_operator(self):
        action, _ = parse('yy', Mode.NORMAL)
        assert action == {'type': 'operator', 'op': 'y', 'motion': 'line', 'count': 1}

    def test_cc_line_operator(self):
        action, _ = parse('cc', Mode.NORMAL)
        assert action == {'type': 'operator', 'op': 'c', 'motion': 'line', 'count': 1}

    def test_dw_operator_motion(self):
        action, _ = parse('dw', Mode.NORMAL)
        assert action['type'] == 'operator'
        assert action['op'] == 'd'
        assert action['motion'] == 'w'

    def test_d_dollar_operator_motion(self):
        action, _ = parse('d$', Mode.NORMAL)
        assert action['op'] == 'd'
        assert action['motion'] == '$'

    def test_count_before_operator(self):
        action, _ = parse('2dd', Mode.NORMAL)
        assert action['count'] == 2
        assert action['motion'] == 'line'

    def test_operator_with_motion_count(self):
        action, _ = parse('d3w', Mode.NORMAL)
        assert action['op'] == 'd'
        assert action['motion'] == 'w'
        assert action['motion_count'] == 3

    def test_D_shortcut(self):
        action, _ = parse('D', Mode.NORMAL)
        assert action == {'type': 'operator', 'op': 'd', 'motion': '$', 'count': 1}

    def test_C_shortcut(self):
        action, _ = parse('C', Mode.NORMAL)
        assert action == {'type': 'operator', 'op': 'c', 'motion': '$', 'count': 1}

    def test_operator_with_f_motion(self):
        action, _ = parse('dfx', Mode.NORMAL)
        assert action['op'] == 'd'
        assert action['motion'] == 'f'
        assert action['target'] == 'x'

    def test_operator_with_gg_motion(self):
        action, _ = parse('dgg', Mode.NORMAL)
        assert action['op'] == 'd'
        assert action['motion'] == 'gg'


# ── Standalone commands ───────────────────────────────────────────────────────

class TestStandaloneCommands:
    def test_x_interact(self):
        action, _ = parse('x', Mode.NORMAL)
        assert action == {'type': 'interact', 'count': 1}

    def test_x_interact_count(self):
        action, _ = parse('5x', Mode.NORMAL)
        assert action == {'type': 'interact', 'count': 5}

    def test_u_undo(self):
        action, _ = parse('u', Mode.NORMAL)
        assert action == {'type': 'undo', 'count': 1}

    def test_u_undo_count(self):
        action, _ = parse('5u', Mode.NORMAL)
        assert action == {'type': 'undo', 'count': 5}

    def test_ctrl_r_redo(self):
        action, _ = parse('\x12', Mode.NORMAL)
        assert action == {'type': 'redo', 'count': 1}

    def test_ctrl_r_redo_count(self):
        action, _ = parse('3\x12', Mode.NORMAL)
        assert action == {'type': 'redo', 'count': 3}

    def test_p_paste(self):
        action, _ = parse('p', Mode.NORMAL)
        assert action == {'type': 'paste', 'before': False, 'count': 1}

    def test_P_paste_before(self):
        action, _ = parse('P', Mode.NORMAL)
        assert action == {'type': 'paste', 'before': True, 'count': 1}

    def test_s_substitute(self):
        action, _ = parse('s', Mode.NORMAL)
        assert action == {'type': 'substitute', 'count': 1}

    def test_count_s(self):
        action, _ = parse('3s', Mode.NORMAL)
        assert action == {'type': 'substitute', 'count': 3}

    def test_colon_command_mode(self):
        action, _ = parse(':', Mode.NORMAL)
        assert action == {'type': 'enter_mode', 'mode': 'command'}

    def test_ctrl_v_visual_block(self):
        action, _ = parse('\x16', Mode.NORMAL)
        assert action == {'type': 'enter_mode', 'mode': 'visual_block'}


# ── Unknown sequences ─────────────────────────────────────────────────────────

class TestUnknown:
    def test_unknown_char(self):
        action, _ = parse('Q', Mode.NORMAL)
        assert action == {'type': 'unknown'}

    def test_g_non_g(self):
        action, _ = parse('gx', Mode.NORMAL)
        assert action == {'type': 'unknown'}


# ── Plain motions ─────────────────────────────────────────────────────────────

class TestPlainMotions:
    @pytest.mark.parametrize("key", list('hjklwbe0^${}G()HML%'))
    def test_single_motion(self, key):
        action, remaining = parse(key, Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': key, 'count': 1, 'count_given': False}
        assert remaining == ''

    def test_count_motion(self):
        action, _ = parse('5j', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'j', 'count': 5, 'count_given': True}

    def test_multi_digit_count(self):
        action, _ = parse('12h', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'h', 'count': 12, 'count_given': True}

    def test_trailing_zero_in_count(self):
        action, _ = parse('30l', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'l', 'count': 30, 'count_given': True}

    def test_zero_alone_is_motion(self):
        action, _ = parse('0', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': '0', 'count': 1, 'count_given': False}


# ── Text objects (operator + i/a + obj) ──────────────────────────────────────

class TestTextObjects:
    def test_diw(self):
        action, rem = parse('diw', Mode.NORMAL)
        assert action == {'type': 'operator', 'op': 'd', 'textobj': 'iw',
                          'count': 1, 'motion_count': 1}
        assert rem == ''

    def test_ci_paren(self):
        action, _ = parse('ci(', Mode.NORMAL)
        assert action['op'] == 'c' and action['textobj'] == 'i('

    def test_da_quote(self):
        action, _ = parse('da"', Mode.NORMAL)
        assert action['op'] == 'd' and action['textobj'] == 'a"'

    def test_yip(self):
        action, _ = parse('yip', Mode.NORMAL)
        assert action['op'] == 'y' and action['textobj'] == 'ip'

    @pytest.mark.parametrize("keys,canon", [
        ('dib', 'i('), ('dab', 'a('), ('di)', 'i('),
        ('diB', 'i{'), ('di}', 'i{'), ('di]', 'i['), ('di>', 'i<'),
    ])
    def test_alias_normalisation(self, keys, canon):
        action, _ = parse(keys, Mode.NORMAL)
        assert action['textobj'] == canon

    def test_incomplete_textobj_needs_obj_char(self):
        action, buf = parse('di', Mode.NORMAL)
        assert action is None          # waiting for the object char

    def test_count_textobj(self):
        action, _ = parse('2daw', Mode.NORMAL)
        assert action['textobj'] == 'aw' and action['count'] == 2


# ── Named registers ("a "0 "_ "A) ────────────────────────────────────────────

class TestNamedRegisters:
    def test_quote_needs_register(self):
        assert parse('"', Mode.NORMAL)[0] is None

    def test_register_yank_line(self):
        assert parse('"ayy', Mode.NORMAL)[0] == {
            'type': 'operator', 'op': 'y', 'motion': 'line', 'count': 1, 'register': 'a'}

    def test_register_delete(self):
        a = parse('"add', Mode.NORMAL)[0]
        assert a['op'] == 'd' and a['register'] == 'a'

    def test_register_paste(self):
        assert parse('"ap', Mode.NORMAL)[0] == {
            'type': 'paste', 'before': False, 'count': 1, 'register': 'a'}

    def test_zero_register_paste(self):
        assert parse('"0p', Mode.NORMAL)[0]['register'] == '0'

    def test_blackhole_delete(self):
        assert parse('"_dw', Mode.NORMAL)[0]['register'] == '_'

    def test_incomplete_after_register(self):
        assert parse('"a', Mode.NORMAL)[0] is None     # waiting for the command


# ── Jump list (Ctrl-o / Ctrl-i) ──────────────────────────────────────────────

class TestJumpList:
    def test_ctrl_o_back(self):
        assert parse('\x0f', Mode.NORMAL)[0] == {'type': 'jump', 'dir': 'back', 'count': 1}

    def test_tab_forward(self):
        assert parse('\t', Mode.NORMAL)[0] == {'type': 'jump', 'dir': 'forward', 'count': 1}


# ── Macros (q @ @@) ────────────────────────────────────────────────────────────

class TestMacros:
    def test_q_needs_register(self):
        assert parse('q', Mode.NORMAL)[0] is None

    def test_record(self):
        assert parse('qa', Mode.NORMAL)[0] == {'type': 'macro_record', 'reg': 'a'}

    def test_play(self):
        assert parse('@a', Mode.NORMAL)[0] == {'type': 'macro_play', 'reg': 'a', 'count': 1}

    def test_play_last(self):
        assert parse('@@', Mode.NORMAL)[0] == {'type': 'macro_play', 'reg': '@', 'count': 1}

    def test_count_play(self):
        assert parse('7@a', Mode.NORMAL)[0] == {'type': 'macro_play', 'reg': 'a', 'count': 7}


# ── Search (/ ? n N * #) ──────────────────────────────────────────────────────

class TestSearch:
    def test_slash_enters_search_forward(self):
        assert parse('/', Mode.NORMAL)[0] == {'type': 'enter_mode', 'mode': 'search', 'forward': True}

    def test_question_enters_search_backward(self):
        assert parse('?', Mode.NORMAL)[0] == {'type': 'enter_mode', 'mode': 'search', 'forward': False}

    def test_n_repeat(self):
        assert parse('n', Mode.NORMAL)[0] == {'type': 'search_repeat', 'reverse': False, 'count': 1}

    def test_N_reverse(self):
        assert parse('N', Mode.NORMAL)[0] == {'type': 'search_repeat', 'reverse': True, 'count': 1}

    def test_star_word_forward(self):
        assert parse('*', Mode.NORMAL)[0] == {'type': 'search_word', 'forward': True, 'count': 1}

    def test_hash_word_backward(self):
        assert parse('#', Mode.NORMAL)[0] == {'type': 'search_word', 'forward': False, 'count': 1}


# ── Replace: r{char} and R (REPLACE mode) ────────────────────────────────────

class TestReplace:
    def test_r_needs_char(self):
        assert parse('r', Mode.NORMAL)[0] is None

    def test_r_char(self):
        assert parse('rx', Mode.NORMAL)[0] == {'type': 'replace', 'char': 'x', 'count': 1}

    def test_count_r(self):
        assert parse('3rx', Mode.NORMAL)[0] == {'type': 'replace', 'char': 'x', 'count': 3}

    def test_R_enters_replace_mode(self):
        assert parse('R', Mode.NORMAL)[0] == {'type': 'enter_mode', 'mode': 'replace'}


# ── Case operators (~ and g~/gu/gU) ──────────────────────────────────────────

class TestCaseOperators:
    def test_tilde(self):
        assert parse('~', Mode.NORMAL)[0] == {'type': 'case_char', 'count': 1}

    def test_count_tilde(self):
        assert parse('3~', Mode.NORMAL)[0] == {'type': 'case_char', 'count': 3}

    @pytest.mark.parametrize("keys,op", [('g~w', 'g~'), ('gUw', 'gU'), ('guw', 'gu')])
    def test_case_op_with_motion(self, keys, op):
        action, _ = parse(keys, Mode.NORMAL)
        assert action['op'] == op and action['motion'] == 'w'

    @pytest.mark.parametrize("keys,op", [('gUU', 'gU'), ('guu', 'gu'), ('g~~', 'g~')])
    def test_case_op_line_form(self, keys, op):
        action, _ = parse(keys, Mode.NORMAL)
        assert action == {'type': 'operator', 'op': op, 'motion': 'line', 'count': 1}

    def test_case_op_with_textobj(self):
        action, _ = parse('gUiw', Mode.NORMAL)
        assert action['op'] == 'gU' and action['textobj'] == 'iw'

    def test_case_op_incomplete(self):
        assert parse('gU', Mode.NORMAL)[0] is None    # needs a motion/object


# ── Indent operators (>> << >{m}) ─────────────────────────────────────────────

class TestIndentOperators:
    def test_indent_line(self):
        assert parse('>>', Mode.NORMAL)[0] == {'type': 'operator', 'op': '>', 'motion': 'line', 'count': 1}

    def test_dedent_line(self):
        assert parse('<<', Mode.NORMAL)[0] == {'type': 'operator', 'op': '<', 'motion': 'line', 'count': 1}

    def test_count_indent_line(self):
        assert parse('3>>', Mode.NORMAL)[0]['count'] == 3

    def test_indent_with_motion(self):
        action, _ = parse('>3j', Mode.NORMAL)
        assert action['op'] == '>' and action['motion'] == 'j' and action['motion_count'] == 3

    def test_indent_with_textobj(self):
        action, _ = parse('>ip', Mode.NORMAL)
        assert action['op'] == '>' and action['textobj'] == 'ip'


# ── Mark commands ─────────────────────────────────────────────────────────────

class TestMarkCommands:
    def test_m_mark_set(self):
        action, _ = parse('ma', Mode.NORMAL)
        assert action == {'type': 'mark', 'cmd': 'm', 'reg': 'a'}

    def test_backtick_jump(self):
        action, _ = parse('`a', Mode.NORMAL)
        assert action == {'type': 'mark', 'cmd': '`', 'reg': 'a'}

    def test_single_quote_jump(self):
        action, _ = parse("'a", Mode.NORMAL)
        assert action == {'type': 'mark', 'cmd': "'", 'reg': 'a'}

    def test_mark_incomplete_without_register(self):
        action, _ = parse('m', Mode.NORMAL)
        assert action is None
