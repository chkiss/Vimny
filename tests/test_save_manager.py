"""Tests for save/save_manager.py — slug, round-trip I/O, progress helpers."""
import json
import pytest
from pathlib import Path
from save.save_manager import (
    _slug, save_for, load_for, list_saves, save_progress, load_progress,
    load_player_name,
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
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'score': 99})
        result = load_for('Alice')
        assert result == {'score': 99}

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        assert load_for('Nobody') is None

    def test_overwrite_keeps_latest(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'v': 1})
        save_for('Alice', {'v': 2})
        assert load_for('Alice') == {'v': 2}

    def test_different_players_isolated(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'x': 1})
        save_for('Bob',   {'x': 2})
        assert load_for('Alice')['x'] == 1
        assert load_for('Bob')['x']   == 2


# ── list_saves ────────────────────────────────────────────────────────────────

class TestListSaves:
    def test_empty_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        assert list_saves() == []

    def test_nonexistent_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path / 'nosuchdir')
        assert list_saves() == []

    def test_returns_all_saves(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'player_name': 'Alice'})
        save_for('Bob',   {'player_name': 'Bob'})
        names = {s['player_name'] for s in list_saves()}
        assert names == {'Alice', 'Bob'}

    def test_skips_invalid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        (tmp_path / 'broken.json').write_text('not json')
        save_for('Alice', {'player_name': 'Alice'})
        results = list_saves()
        assert len(results) == 1
        assert results[0]['player_name'] == 'Alice'


# ── load_progress ─────────────────────────────────────────────────────────────

class TestLoadProgress:
    def test_none_input_returns_empty_dict(self):
        assert load_progress(None) == {}

    def test_missing_progress_key_returns_empty(self):
        assert load_progress({'player_name': 'Alice'}) == {}

    def test_string_keys_converted_to_int(self):
        data = {'progress': {'0': {'complete': True}, '2': {'complete': False}}}
        result = load_progress(data)
        assert 0 in result
        assert 2 in result
        assert isinstance(list(result.keys())[0], int)

    def test_values_preserved(self):
        data = {'progress': {'1': {'complete': True, 'stars': 3}}}
        result = load_progress(data)
        assert result[1] == {'complete': True, 'stars': 3}

    def test_round_trip_via_save_progress(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        original = {0: {'complete': True, 'stars': 2}, 1: {'complete': False}}
        save_progress(original, 'Alice')
        raw = load_for('Alice')
        restored = load_progress(raw)
        assert restored == original
        assert all(isinstance(k, int) for k in restored)


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
    def test_writes_progress_with_string_keys(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_progress({0: {'complete': True}}, 'Alice')
        raw = load_for('Alice')
        assert '0' in raw['progress']

    def test_merges_with_existing_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_for('Alice', {'extra_field': 'preserved'})
        save_progress({0: {'complete': True}}, 'Alice')
        raw = load_for('Alice')
        assert raw.get('extra_field') == 'preserved'
        assert '0' in raw['progress']

    def test_player_name_stored(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_progress({}, 'Alice')
        raw = load_for('Alice')
        assert raw['player_name'] == 'Alice'

    def test_heart_container_max_hp_persists(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        progress = {'max_hp': 8, 'collected_hearts': [[51, 2, 41]]}
        save_progress(progress, 'Alice')
        restored = load_progress(load_for('Alice'))
        assert restored['max_hp'] == 8
        assert restored['collected_hearts'] == [[51, 2, 41]]

    def test_heart_container_round_trip_default_hp(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        save_progress({}, 'Alice')
        restored = load_progress(load_for('Alice'))
        # Default max_hp of 6 is not stored in progress dict (omitted when unchanged)
        assert restored.get('max_hp', 6) == 6

    def test_multiple_hearts_all_collected_positions_saved(self, tmp_path, monkeypatch):
        monkeypatch.setattr('save.save_manager.SAVES_DIR', tmp_path)
        hearts = [[51, 2, 41], [3, 4, 10]]
        progress = {'max_hp': 10, 'collected_hearts': hearts}
        save_progress(progress, 'Alice')
        restored = load_progress(load_for('Alice'))
        assert restored['max_hp'] == 10
        assert restored['collected_hearts'] == hearts
