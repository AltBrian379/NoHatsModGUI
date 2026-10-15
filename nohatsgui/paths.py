"""Locating the nhcustom2 tool folder next to this program."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

TOOL_FOLDER_NAME = "nhcustom2_windows"
TOOL_EXE_NAME = "nhcustom2.exe"
DATABASE_NAME = "database.csv"
CONFIG_NAME = "config.txt"


def app_dir() -> Path:
    """Folder containing this program's exe (or the project root when run from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ToolPaths:
    folder: Path

    @property
    def exe(self) -> Path:
        return self.folder / TOOL_EXE_NAME

    @property
    def config(self) -> Path:
        return self.folder / CONFIG_NAME

    @property
    def input(self) -> Path:
        return self.folder / "input"

    @property
    def output(self) -> Path:
        return self.folder / "output"


def find_tool(base: Path | None = None) -> ToolPaths | None:
    """Find the nhcustom2_windows folder dropped next to this program.

    Also accepts the folder one level deeper, which is what extracting a zip
    into a same-named folder produces (nhcustom2_windows/nhcustom2_windows/).
    """
    base = base or app_dir()
    folder = base / TOOL_FOLDER_NAME
    if not folder.is_dir():
        return None
    if (folder / TOOL_EXE_NAME).is_file():
        return ToolPaths(folder)
    for child in sorted(folder.iterdir()):
        if child.is_dir() and (child / TOOL_EXE_NAME).is_file():
            return ToolPaths(child)
    return None


def find_database(tool: ToolPaths | None, base: Path | None = None) -> Path | None:
    """The database next to nhcustom2.exe, falling back to one next to this program."""
    base = base or app_dir()
    candidates = []
    if tool is not None:
        candidates.append(tool.folder / DATABASE_NAME)
    candidates.append(base / DATABASE_NAME)
    for path in candidates:
        if path.is_file():
            return path
    return None
