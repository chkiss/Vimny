"""Verify that all modules import without error under Python 3.9.

The X | None union syntax for runtime annotations (not inside string
annotations) requires Python 3.10+.  Using `from __future__ import
annotations` defers evaluation so the syntax is safe on 3.9.
"""
import importlib


MODULES = [
    'main',
    'engine.vim_parser',
    'render.title',
    'render.overworld',
    'generation.dungeon_gen',
]


def test_modules_importable():
    for name in MODULES:
        mod = importlib.import_module(name)
        assert mod is not None, f"Failed to import {name}"
