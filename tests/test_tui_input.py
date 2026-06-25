"""Tests for the Phase 2 TUI input layer (slash autocomplete + fallback).

These cover the module-level completion logic, which works with or without
prompt_toolkit installed, so the suite stays green in minimal environments.
"""

from harness.tui import slash_completions, SLASH_COMMANDS, APP_NAME


def _names(text):
    return [cmd for cmd, _ in slash_completions(text)]


def test_app_is_named_menace():
    assert APP_NAME == "menace"


def test_empty_input_offers_all_commands():
    names = _names("")
    assert set(names) == set(SLASH_COMMANDS)
    # every suggestion carries a help string
    assert all(help_ for _, help_ in slash_completions(""))


def test_slash_prefix_filters_commands():
    assert _names("/re") == ["/remember", "/recall"]
    assert _names("/me") == ["/memory"]


def test_full_command_still_matches_itself():
    assert _names("/help") == ["/help"]


def test_no_completion_after_a_space():
    # once arguments begin, the command token is settled
    assert slash_completions("/recall something") == []
    assert slash_completions("/remember ") == []


def test_non_slash_text_is_not_completed():
    assert slash_completions("hello world") == []
    assert slash_completions("search the web") == []


def test_unknown_slash_prefix_yields_nothing():
    assert slash_completions("/zzz") == []
