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
    @pytest.mark.parametrize("key", list('hjklwbe0^${}G'))
    def test_single_motion(self, key):
        action, remaining = parse(key, Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': key, 'count': 1}
        assert remaining == ''

    def test_count_motion(self):
        action, _ = parse('5j', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'j', 'count': 5}

    def test_multi_digit_count(self):
        action, _ = parse('12h', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'h', 'count': 12}

    def test_trailing_zero_in_count(self):
        action, _ = parse('30l', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': 'l', 'count': 30}

    def test_zero_alone_is_motion(self):
        action, _ = parse('0', Mode.NORMAL)
        assert action == {'type': 'motion', 'motion': '0', 'count': 1}


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
