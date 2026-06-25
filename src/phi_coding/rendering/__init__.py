"""Event renderers for Phi coding frontends and print modes."""

from phi_coding.rendering.base import EventRenderer, PrintOutputMode
from phi_coding.rendering.json import JsonEventRenderer
from phi_coding.rendering.plain import FinalTextRenderer
from phi_coding.rendering.transcript import TranscriptRenderer


def create_event_renderer(mode: PrintOutputMode) -> EventRenderer:
    """Create a renderer for a print output mode."""
    if mode is PrintOutputMode.text:
        return FinalTextRenderer()
    if mode is PrintOutputMode.json:
        return JsonEventRenderer()
    return TranscriptRenderer()


__all__ = [
    "EventRenderer",
    "FinalTextRenderer",
    "JsonEventRenderer",
    "PrintOutputMode",
    "TranscriptRenderer",
    "create_event_renderer",
]
