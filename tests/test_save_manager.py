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

"""Tests for vimny/save/save_manager.py — slug, round-trip I/O, progress helpers."""
from vimny.save.save_manager import (
    _slug, save_for, load_for, list_saves, save_progress, load_progress,
    load_player_name, save_layout, list_layouts, delete_layout, rename_layout,
    touch_loaded,
)


# ── _slug ─────────────────────────────────────────────────────────────────────

class TestSlug:
    def test_simple_name(self):
        assert _slug('Alice') == 'alice'

    def test_spaces_become_underscores(self):
        assert _slug('John Doe') == 'john_doe'

    def test_multiple_spaces_collapsed(self):
        assert _slug('  Bob   Smith  ') == 'bob_smith'

    def test_special_chars_stripped(self):
        assert _slug('O\'Brien!') == 'obrien'

    def test_slashes_stripped(self):
        assert _slug('path/to/file') == 'pathtofile'

    def test_unicode_stripped(self):
        assert _slug('Ångström') == 'ngstrm'

    def test_empty_string_returns_unnamed(self):
        assert _slug('') == 'unnamed'

    def test_only_special_chars_returns_unnamed(self):
        assert _slug('!!!') == 'unnamed'

    def test_digits_preserved(self):
        assert _slug('Player1') == 'player1'


# ── save_for / load_for round-trip ────────────────────────────────────────────

class TestSaveLoadRoundTrip:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'score': 99})
        result = load_for('Alice')
        assert result == {'score': 99}

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        assert load_for('Nobody') is None

    def test_overwrite_keeps_latest(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'v': 1})
        save_for('Alice', {'v': 2})
        assert load_for('Alice') == {'v': 2}

    def test_different_players_isolated(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'x': 1})
        save_for('Bob',   {'x': 2})
        assert load_for('Alice')['x'] == 1
        assert load_for('Bob')['x']   == 2


# ── list_saves ────────────────────────────────────────────────────────────────

class TestListSaves:
    def test_empty_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        assert list_saves() == []

    def test_nonexistent_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path / 'nosuchdir')
        assert list_saves() == []

    def test_returns_all_saves(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'player_name': 'Alice'})
        save_for('Bob',   {'player_name': 'Bob'})
        names = {s['player_name'] for s in list_saves()}
        assert names == {'Alice', 'Bob'}

    def test_skips_invalid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        (tmp_path / 'broken.json').write_text('not json')
        save_for('Alice', {'player_name': 'Alice'})
        results = list_saves()
        assert len(results) == 1
        assert results[0]['player_name'] == 'Alice'

    def test_orders_by_last_loaded_newest_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'player_name': 'Alice', 'last_loaded': 100.0})
        save_for('Bob',   {'player_name': 'Bob',   'last_loaded': 300.0})
        save_for('Carol', {'player_name': 'Carol', 'last_loaded': 200.0})
        order = [s['player_name'] for s in list_saves()]
        assert order == ['Bob', 'Carol', 'Alice']

    def test_touch_loaded_moves_save_to_front(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'player_name': 'Alice', 'last_loaded': 100.0})
        save_for('Bob',   {'player_name': 'Bob',   'last_loaded': 300.0})
        touch_loaded('Alice')
        assert list_saves()[0]['player_name'] == 'Alice'


# ── load_progress ─────────────────────────────────────────────────────────────

class TestLoadProgress:
    def test_none_input_returns_empty_dict(self):
        assert load_progress(None) == {}

    def test_missing_progress_key_returns_empty(self):
        assert load_progress({'player_name': 'Alice'}) == {}

    def test_slug_keys_loaded_as_is(self):
        data = {'progress': {'first_cave': {'complete': True},
                             'counting_crypts': {'complete': False}}}
        result = load_progress(data)
        assert result['first_cave'] == {'complete': True}
        assert result['counting_crypts'] == {'complete': False}

    def test_values_preserved(self):
        data = {'progress': {'line_halls': {'complete': True, 'stars': 3}}}
        result = load_progress(data)
        assert result['line_halls'] == {'complete': True, 'stars': 3}

    def test_round_trip_via_save_progress(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        original = {'first_cave': {'complete': True, 'stars': 2},
                    'line_halls': {'complete': False}}
        save_progress(original, 'Alice')
        raw = load_for('Alice')
        restored = load_progress(raw)
        assert restored == original
        assert all(isinstance(k, str) for k in restored)


# ── load_player_name ──────────────────────────────────────────────────────────

class TestLoadPlayerName:
    def test_none_returns_default(self):
        assert load_player_name(None) == 'Normand'

    def test_missing_key_returns_default(self):
        assert load_player_name({'progress': {}}) == 'Normand'

    def test_returns_stored_name(self):
        assert load_player_name({'player_name': 'Alice'}) == 'Alice'


# ── save_progress ─────────────────────────────────────────────────────────────

class TestSaveProgress:
    def test_writes_progress_keyed_by_slug(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_progress({'first_cave': {'complete': True}}, 'Alice')
        raw = load_for('Alice')
        assert 'first_cave' in raw['progress']

    def test_merges_with_existing_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'extra_field': 'preserved'})
        save_progress({'first_cave': {'complete': True}}, 'Alice')
        raw = load_for('Alice')
        assert raw.get('extra_field') == 'preserved'
        assert 'first_cave' in raw['progress']

    def test_player_name_stored(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_progress({}, 'Alice')
        raw = load_for('Alice')
        assert raw['player_name'] == 'Alice'

    def test_heart_container_max_hp_persists(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        progress = {'max_hp': 8, 'collected_hearts': [[51, 2, 41]]}
        save_progress(progress, 'Alice')
        restored = load_progress(load_for('Alice'))
        assert restored['max_hp'] == 8
        assert restored['collected_hearts'] == [[51, 2, 41]]

    def test_heart_container_round_trip_default_hp(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        save_progress({}, 'Alice')
        restored = load_progress(load_for('Alice'))
        # Default max_hp of 6 is not stored in progress dict (omitted when unchanged)
        assert restored.get('max_hp', 6) == 6

    def test_multiple_hearts_all_collected_positions_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.SAVES_DIR', tmp_path)
        hearts = [[51, 2, 41], [3, 4, 10]]
        progress = {'max_hp': 10, 'collected_hearts': hearts}
        save_progress(progress, 'Alice')
        restored = load_progress(load_for('Alice'))
        assert restored['max_hp'] == 10
        assert restored['collected_hearts'] == hearts


# ── Layouts (netrw custom/) ────────────────────────────────────────────────────

class TestLayouts:
    _LAYOUT = {'rows': 1, 'cols': 1, 'cells': [['F']]}

    def test_save_list_rename_delete(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.LAYOUTS_DIR', tmp_path)
        save_layout('My Map', self._LAYOUT)
        assert [l['layout_name'] for l in list_layouts()] == ['My Map']
        assert rename_layout('My Map', 'Renamed') is True
        assert [l['layout_name'] for l in list_layouts()] == ['Renamed']
        assert not (tmp_path / 'my_map.json').exists()      # old slug removed
        assert (tmp_path / 'renamed.json').exists()
        assert delete_layout('Renamed') is True
        assert list_layouts() == []

    def test_rename_rejects_missing_source_or_empty_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr('vimny.save.save_manager.LAYOUTS_DIR', tmp_path)
        assert rename_layout('nope', 'x') is False          # source doesn't exist
        save_layout('Map', self._LAYOUT)
        assert rename_layout('Map', '   ') is False         # empty new name
        assert [l['layout_name'] for l in list_layouts()] == ['Map']
