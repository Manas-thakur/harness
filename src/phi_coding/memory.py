"""Persistent long-term memory for the agent.

A small markdown-backed store that survives across sessions. It holds an
always-loaded **profile** (who the user is, what they're working on, lasting
preferences) plus on-demand **facts**. The model writes to it through the
``update_profile`` / ``remember`` tools and reads it back via the always-injected
profile block and the ``recall`` tool — phi's clean, model-driven realization of
menace's long-term memory.

Storage is one markdown file per project (alongside that project's sessions).
Every mutation snapshots the previous file first, so memory is always
recoverable.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from phi_coding.paths import PhiPaths

PROFILE_SECTIONS: tuple[str, ...] = ("About", "Current Work", "User Preferences")
FACTS_SECTION = "Facts"
_ALL_SECTIONS: tuple[str, ...] = (*PROFILE_SECTIONS, FACTS_SECTION)
_MAX_SNAPSHOTS = 10


def default_memory_path(cwd: Path, paths: PhiPaths | None = None) -> Path:
    """Return the per-project memory file path (beside that project's sessions)."""
    resolved = (paths or PhiPaths()).project_session_dir(Path(cwd))
    return resolved / "memory.md"


class MemoryStore:
    """Markdown-backed profile + facts store for one project."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # -- reading ---------------------------------------------------------

    def _sections(self) -> dict[str, list[str]]:
        """Parse the file into an ordered ``section -> bullet lines`` mapping."""
        sections: dict[str, list[str]] = {name: [] for name in _ALL_SECTIONS}
        if not self.path.exists():
            return sections
        current: str | None = None
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            if line.startswith("## "):
                current = line[3:].strip()
                sections.setdefault(current, [])
            elif line.startswith("- ") and current is not None:
                sections[current].append(line[2:].strip())
        return sections

    def read_core(self) -> str:
        """Return the always-loaded profile block, or ``""`` if empty."""
        sections = self._sections()
        blocks: list[str] = []
        for name in PROFILE_SECTIONS:
            entries = sections.get(name) or []
            if entries:
                blocks.append(f"## {name}\n" + "\n".join(f"- {e}" for e in entries))
        if not blocks:
            return ""
        return "# What you remember about the user\n\n" + "\n\n".join(blocks)

    def read_all(self) -> str:
        """Return the full memory document (or a friendly empty message)."""
        if not self.path.exists():
            return "_Memory is empty._"
        return self.path.read_text(encoding="utf-8")

    def search(self, query: str) -> list[str]:
        """Return memory bullet lines matching ``query`` (case-insensitive)."""
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[str] = []
        for name, entries in self._sections().items():
            for entry in entries:
                if needle in entry.lower():
                    matches.append(f"[{name}] {entry}")
        return matches

    # -- writing ---------------------------------------------------------

    def append_to_section(self, section: str, content: str) -> str:
        """Append a bullet under ``section`` (creating it if needed)."""
        content = content.strip()
        if not content:
            return "Nothing to store (empty content)."
        match = next((s for s in PROFILE_SECTIONS if s.lower() == section.lower()), section)
        sections = self._sections()
        sections.setdefault(match, [])
        if content not in sections[match]:
            sections[match].append(content)
        self._write(sections)
        return f"Recorded under {match}."

    def save_fact(self, fact: str, key: str | None = None) -> str:
        """Append a fact (optionally key-tagged) to the Facts section."""
        fact = fact.strip()
        if not fact:
            return "Nothing to remember (empty fact)."
        entry = f"[{key}] {fact}" if key else fact
        sections = self._sections()
        if entry not in sections[FACTS_SECTION]:
            sections[FACTS_SECTION].append(entry)
        self._write(sections)
        return "Remembered."

    def _write(self, sections: dict[str, list[str]]) -> None:
        self._snapshot()
        ordered = list(_ALL_SECTIONS) + [s for s in sections if s not in _ALL_SECTIONS]
        lines = ["# Memory", ""]
        for name in ordered:
            entries = sections.get(name) or []
            lines.append(f"## {name}")
            lines.extend(f"- {entry}" for entry in entries)
            lines.append("")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _snapshot(self) -> None:
        """Copy the current file into a versions dir before overwriting it."""
        if not self.path.exists():
            return
        versions = self.path.parent / "memory.versions"
        versions.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(self.path, versions / f"memory_{stamp}.md")
        snapshots = sorted(versions.glob("memory_*.md"))
        for old in snapshots[:-_MAX_SNAPSHOTS]:
            old.unlink(missing_ok=True)
