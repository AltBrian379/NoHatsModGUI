"""Main window: mode, search, the hat tree, saving the config and running nhcustom2."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QProcess, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QSplitter, QVBoxLayout, QWidget,
)

from . import APP_NAME
from .config import KEEP, REMOVE, generate, is_generated, parse_generated
from .database import Hat, Section, build_sections, load_database
from .hat_tree import HatTree
from .paths import TOOL_EXE_NAME, TOOL_FOLDER_NAME, ToolPaths, app_dir, find_database, find_tool

SEARCH_DELAY_MS = 150
MAX_TOOL_PATH = 120


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(900, 760)

        self.tool: ToolPaths | None = None
        self.database: Path | None = None
        self.hats: list[Hat] = []
        self.sections: list[Section] = []
        self.process: QProcess | None = None

        self._build_ui()

        # Pick up nhcustom2_windows if it is dropped in while the app is open.
        self._watcher = QFileSystemWatcher([str(app_dir())], self)
        self._watcher.directoryChanged.connect(self._on_app_dir_changed)

        self.reload()

    # ---- layout ---------------------------------------------------------

    def _build_ui(self) -> None:
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setTextInteractionFlags(Qt.TextSelectableByMouse)
        reload_button = QPushButton("Reload")
        reload_button.setToolTip("Look for nhcustom2_windows and the database again")
        reload_button.clicked.connect(self.reload)
        banner_row = QHBoxLayout()
        banner_row.addWidget(self.banner, 1)
        banner_row.addWidget(reload_button)

        self.keep_radio = QRadioButton("Keep selected (remove everything else)")
        self.remove_radio = QRadioButton("Remove selected (keep everything else)")
        self.keep_radio.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.keep_radio)
        self.mode_group.addButton(self.remove_radio)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.keep_radio)
        mode_row.addWidget(self.remove_radio)
        mode_row.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search cosmetics by name…")
        self.search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self, singleShot=True, interval=SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(lambda: self.tree.set_search(self.search.text()))
        self.search.textChanged.connect(self._search_timer.start)
        expand_button = QPushButton("Expand all")
        collapse_button = QPushButton("Collapse all")
        clear_button = QPushButton("Clear selection")
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(expand_button)
        search_row.addWidget(collapse_button)
        search_row.addWidget(clear_button)

        self.tree = HatTree()
        self.tree.selection_changed.connect(self._update_count)
        expand_button.clicked.connect(self.tree.expand_all)
        collapse_button.clicked.connect(self.tree.collapse_all)
        clear_button.clicked.connect(lambda: self.tree.set_selected(set()))

        self.count_label = QLabel()
        self.save_button = QPushButton("Save config")
        self.save_button.clicked.connect(self.save_config)
        save_as_button = QPushButton("Save config as…")
        save_as_button.clicked.connect(self.save_config_as)
        self.clear_output_check = QCheckBox("Clear output folder first")
        self.clear_output_check.setToolTip("nhcustom2 never empties its output folder, so old files pile up between runs")
        self.run_button = QPushButton("Run nhcustom2")
        self.run_button.clicked.connect(self.run_tool)
        self.open_output_button = QPushButton("Open output folder")
        self.open_output_button.clicked.connect(self.open_output)
        action_row = QHBoxLayout()
        action_row.addWidget(self.count_label, 1)
        action_row.addWidget(self.save_button)
        action_row.addWidget(save_as_button)
        action_row.addSpacing(16)
        action_row.addWidget(self.clear_output_check)
        action_row.addWidget(self.run_button)
        action_row.addWidget(self.open_output_button)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas"))
        self.log.setPlaceholderText("nhcustom2 output appears here.")

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addLayout(mode_row)
        top_layout.addLayout(search_row)
        top_layout.addWidget(self.tree, 1)
        top_layout.addLayout(action_row)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(self.log)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(banner_row)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

    # ---- loading --------------------------------------------------------

    def _on_app_dir_changed(self, _path: str) -> None:
        if (find_tool() is None) != (self.tool is None):
            self.reload()

    def reload(self) -> None:
        keep_selection = self.tree.selected_ids() if self.hats else None
        self.tool = find_tool()
        self.database = find_database(self.tool)

        problems = []
        if self.tool is None:
            problems.append(f"Drop the <b>{TOOL_FOLDER_NAME}</b> folder (containing {TOOL_EXE_NAME}) "
                            f"next to this program:<br>{app_dir()}")
        if self.database is None:
            problems.append("No <b>database.csv</b> found. Download the latest one from "
                            "<a href='https://pevhs.ch/tf2/nhcustom2/database.csv'>pevhs.ch/tf2/nhcustom2/</a> "
                            f"and put it in the {TOOL_FOLDER_NAME} folder.")
        else:
            try:
                hats = load_database(self.database)
            except (OSError, ValueError) as error:
                problems.append(f"Could not read {self.database}: {error}")
                hats = []
            if hats != self.hats:
                self.hats = hats
                self.sections = build_sections(hats)
                self.tree.set_sections(self.sections)
                if keep_selection is not None:
                    self.tree.set_selected(keep_selection)
                else:
                    self._load_saved_config()

        self.banner.setOpenExternalLinks(True)
        if problems:
            self.banner.setText("<br>".join(problems))
            self.banner.setStyleSheet("QLabel { color: #b00020; }")
        else:
            self.banner.setText(f"Using {self.tool.exe}<br>Database: {self.database} "
                                f"({len(self.hats)} cosmetics)")
            self.banner.setStyleSheet("")
        self._update_buttons()

    def _load_saved_config(self) -> None:
        """Restore the selection from a config.txt this program wrote earlier."""
        if self.tool is None or not self.tool.config.is_file():
            return
        try:
            text = self.tool.config.read_text(encoding="utf-8-sig")
        except OSError:
            return
        if not is_generated(text):
            return
        saved = parse_generated(text)
        (self.keep_radio if saved.mode == KEEP else self.remove_radio).setChecked(True)
        self.tree.set_selected(saved.resolve(self.hats))

    # ---- state ----------------------------------------------------------

    def mode(self) -> str:
        return KEEP if self.keep_radio.isChecked() else REMOVE

    def _update_count(self) -> None:
        self.count_label.setText(f"{len(self.tree.selected_ids())} of {len(self.hats)} selected")

    def _update_buttons(self) -> None:
        running = self.process is not None
        has_tool = self.tool is not None
        self.save_button.setEnabled(has_tool and bool(self.hats))
        self.run_button.setEnabled(has_tool and bool(self.hats) and not running)
        self.open_output_button.setEnabled(has_tool and self.tool.output.is_dir())

    # ---- saving ---------------------------------------------------------

    def config_text(self) -> str:
        return generate(self.mode(), self.sections, self.tree.selected_ids(), self.hats)

    def save_config(self) -> bool:
        if self.tool is None:
            return self.save_config_as()
        return self._write_config(self.tool.config)

    def save_config_as(self) -> bool:
        start = str(self.tool.config if self.tool else app_dir() / "config.txt")
        name, _ = QFileDialog.getSaveFileName(self, "Save config", start, "Text files (*.txt)")
        return bool(name) and self._write_config(Path(name), confirm=False)

    def _write_config(self, path: Path, confirm: bool = True) -> bool:
        if confirm and path.is_file():
            try:
                existing = path.read_text(encoding="utf-8-sig")
            except OSError:
                existing = ""
            if not is_generated(existing):
                answer = QMessageBox.question(
                    self, "Overwrite config?",
                    f"{path}\nwas not created by {APP_NAME}. Overwrite it?")
                if answer != QMessageBox.Yes:
                    return False
        try:
            # nhcustom2 expects UTF-8 without BOM and LF line endings.
            path.write_text(self.config_text(), encoding="utf-8", newline="\n")
        except OSError as error:
            QMessageBox.critical(self, "Save failed", f"Could not write {path}:\n{error}")
            return False
        self.statusBar().showMessage(f"Saved {path}", 5000)
        return True

    # ---- running nhcustom2 -------------------------------------------

    def run_tool(self) -> None:
        if self.tool is None or self.database is None or self.process is not None:
            return
        tool = self.tool
        if not (tool.input / "models").is_dir():
            QMessageBox.warning(
                self, "No input mod",
                f"Put a decompiled no-hats-bgum mod in\n{tool.input}\n\n"
                "It should contain a \"models\" folder.")
            return
        if not self.save_config():
            return
        if self.clear_output_check.isChecked() and tool.output.is_dir():
            answer = QMessageBox.question(
                self, "Clear output folder?", f"Delete everything inside\n{tool.output}?")
            if answer != QMessageBox.Yes:
                return
            try:
                for child in tool.output.iterdir():
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
            except OSError as error:
                QMessageBox.critical(self, "Could not clear output", str(error))
                return

        # nhcustom2 truncates path arguments longer than ~127 characters, so
        # run it from its own folder and pass paths relative to it.
        args = ["-f", _relative(tool.config, tool.folder), "-d", _relative(self.database, tool.folder),
                "-i", _relative(tool.input, tool.folder), "-o", _relative(tool.output, tool.folder)]
        if any(len(arg) > MAX_TOOL_PATH for arg in args):
            self.log.appendPlainText(f"Warning: a path is longer than {MAX_TOOL_PATH} characters and "
                                     "nhcustom2 may cut it off. Move the database into "
                                     f"{TOOL_FOLDER_NAME} to avoid this.")
        self.log.appendPlainText(f"> {tool.exe.name} {' '.join(args)}")
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(tool.folder))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        self.process.start(str(tool.exe), args)
        self._update_buttons()

    def _on_output(self) -> None:
        data = self.process.readAllStandardOutput().data()
        self.log.appendPlainText(data.decode("utf-8", errors="replace").rstrip("\n"))

    def _on_finished(self, exit_code: int, _status) -> None:
        if exit_code == 0:
            self.log.appendPlainText(f"Done. Output is in {self.tool.output}\n")
        else:
            self.log.appendPlainText(f"nhcustom2 exited with code {exit_code}.\n")
        self.process.deleteLater()
        self.process = None
        self._update_buttons()

    def _on_error(self, error) -> None:
        if error == QProcess.FailedToStart:
            self.log.appendPlainText(f"Could not start {self.tool.exe}\n")
            self.process.deleteLater()
            self.process = None
            self._update_buttons()

    def open_output(self) -> None:
        if self.tool is not None and self.tool.output.is_dir():
            os.startfile(self.tool.output)


def _relative(path: Path, base: Path) -> str:
    try:
        return os.path.relpath(path, base)
    except ValueError:  # different drive
        return str(path)
