"""Textual TUI frontend for Phi coding sessions."""

from phi_coding.tui.adapter import TuiEventAdapter
from phi_coding.tui.app import PhiTuiApp, run_tui_app
from phi_coding.tui.autocomplete import CompletionOption
from phi_coding.tui.config import (
    BUILTIN_TUI_THEME_NAMES,
    HIGH_CONTRAST_THEME,
    PHI_DARK_THEME,
    PHI_LIGHT_THEME,
    TuiConfigError,
    TuiKeybindings,
    TuiRoleStyle,
    TuiSettings,
    TuiTheme,
    TuiThemeName,
    get_tui_theme,
    load_tui_settings,
    save_tui_settings,
    tui_settings_path,
)
from phi_coding.tui.state import ChatItem, TuiState
from phi_coding.tui.widgets import (
    CompactSessionInfo,
    SessionSidebar,
    StreamingTranscriptMessageWidget,
    TranscriptMessageWidget,
    TranscriptView,
    render_chat_item,
    render_compact_session_info,
    render_session_sidebar,
    transcript_item_selection_text,
)

__all__ = [
    "BUILTIN_TUI_THEME_NAMES",
    "ChatItem",
    "CompletionOption",
    "CompactSessionInfo",
    "PhiTuiApp",
    "SessionSidebar",
    "PHI_DARK_THEME",
    "PHI_LIGHT_THEME",
    "StreamingTranscriptMessageWidget",
    "TranscriptMessageWidget",
    "TranscriptView",
    "TuiEventAdapter",
    "TuiConfigError",
    "HIGH_CONTRAST_THEME",
    "TuiKeybindings",
    "TuiRoleStyle",
    "TuiSettings",
    "TuiTheme",
    "TuiThemeName",
    "TuiState",
    "get_tui_theme",
    "load_tui_settings",
    "render_chat_item",
    "render_compact_session_info",
    "render_session_sidebar",
    "run_tui_app",
    "save_tui_settings",
    "transcript_item_selection_text",
    "tui_settings_path",
]
