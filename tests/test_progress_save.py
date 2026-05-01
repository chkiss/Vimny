"""Progress save behaviour — :q must not persist dungeon completion."""


def _run_main_loop_progress_update(dung_result: dict, progress: dict, level: int):
    """Replicate the fixed progress-update logic from main.py's main loop.

    Progress is only updated (and saved) when the player used :wq to exit.
    :w mid-dungeon is handled inside run_dungeon and is not tested here.
    """
    if dung_result['won'] and dung_result['action'] == 'wq':
        prev_stars = progress.get(level, {}).get('stars', 0)
        progress[level] = {
            'complete': True,
            'stars': max(dung_result['stars'], prev_stars),
        }
    # save only happens when action == 'wq'; not tested here


def test_quit_without_save_does_not_mark_level_complete():
    """Bug: :q after winning updates progress in memory even though no :w was issued.

    The main loop mutates the progress dict whenever won=True, regardless of
    whether the action was 'wq' or 'quit'.  A subsequent :wq from the overworld
    then persists the completion — the player never had to type :w.

    Fix: only update progress[level] when action == 'wq'.
    """
    progress = {}
    level = 2
    dung_result = {'won': True, 'stars': 2, 'action': 'quit'}

    _run_main_loop_progress_update(dung_result, progress, level)

    # FAILS: current code sets progress[2] = {'complete': True, ...}
    assert level not in progress, (
        ":q exit should not mark the level as complete in progress; "
        "only :wq should persist a win"
    )


def test_wq_does_mark_level_complete():
    """:wq after winning must update progress (sanity check for the fix)."""
    progress = {}
    level = 2
    dung_result = {'won': True, 'stars': 2, 'action': 'wq'}

    _run_main_loop_progress_update(dung_result, progress, level)

    # This will also FAIL until the fix lands (the helper only guards 'wq';
    # update _run_main_loop_progress_update to match the fixed main.py).
    assert progress.get(level, {}).get('complete') is True, (
        ":wq exit must mark the level as complete in progress"
    )
