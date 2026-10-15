"""The checkable, searchable tree of hats: update sections > class groups > hats."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QBrush, QFont, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeView, QVBoxLayout, QWidget

from .database import Hat, Section

ROLE_KIND = Qt.UserRole + 1  # "section", "group" or "hat"
ROLE_SECTION = Qt.UserRole + 2  # section index
ROLE_HAT_ID = Qt.UserRole + 3
ROLE_SEARCH = Qt.UserRole + 4  # casefolded hat name; empty for headers

COLUMNS = ["Cosmetic", "Released"]


def matches(search_text: str, needle: str) -> bool:
    return not needle or (bool(search_text) and needle in search_text)


class HatFilterProxy(QSortFilterProxyModel):
    """Filters on hat names only; headers stay visible while they have matching hats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.needle = ""
        self.setRecursiveFilteringEnabled(True)
        self.setDynamicSortFilter(False)

    def set_needle(self, needle: str) -> None:
        self.beginFilterChange()
        self.needle = needle
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        index = self.sourceModel().index(source_row, 0, source_parent)
        return matches(index.data(ROLE_SEARCH) or "", self.needle)


class HatTree(QWidget):
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(COLUMNS)
        self._proxy = HatFilterProxy(self)
        self._proxy.setSourceModel(self._model)

        self._view = QTreeView(self)
        self._view.setModel(self._proxy)
        self._view.setUniformRowHeights(True)
        self._view.setSelectionMode(QAbstractItemView.NoSelection)
        self._view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self._view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._sections: list[Section] = []
        self._section_items: list[QStandardItem] = []
        self._section_hat_items: list[list[QStandardItem]] = []
        self._hat_items: dict[int, QStandardItem] = {}
        self._updating = False
        self._saved_expanded: set[int] = set()
        self._model.itemChanged.connect(self._on_item_changed)

    # ---- building -------------------------------------------------------

    def set_sections(self, sections: list[Section]) -> None:
        self._updating = True
        self._model.removeRows(0, self._model.rowCount())
        self._sections = sections
        self._section_items, self._section_hat_items, self._hat_items = [], [], {}

        dim = QBrush(self.palette().color(QPalette.Disabled, QPalette.Text))
        bold = QFont()
        bold.setBold(True)
        italic = QFont()
        italic.setItalic(True)

        for si, section in enumerate(sections):
            sec_item = _item(section.title, ROLE_KIND, "section", ROLE_SECTION, si)
            sec_item.setCheckable(True)
            sec_item.setFont(bold)
            date_item = _item(section.date)
            if section.kind == "gap":
                sec_item.setFont(italic)
                sec_item.setForeground(dim)
                date_item.setForeground(dim)

            hat_items = []
            for group in section.groups:
                group_item = _item(group.label, ROLE_KIND, "group", ROLE_SECTION, si)
                group_item.setForeground(dim)
                for hat in group.hats:
                    hat_item = _item(hat.name, ROLE_KIND, "hat", ROLE_SECTION, si,
                                     ROLE_HAT_ID, hat.id, ROLE_SEARCH, hat.name.casefold())
                    hat_item.setCheckable(True)
                    hat_item.setToolTip(_tooltip(hat))
                    released = "" if section.kind == "community" else hat.date
                    group_item.appendRow([hat_item, _item(released)])
                    hat_items.append(hat_item)
                    self._hat_items[hat.id] = hat_item
                sec_item.appendRow([group_item, _item("")])
            self._model.appendRow([sec_item, date_item])
            self._section_items.append(sec_item)
            self._section_hat_items.append(hat_items)
            self._refresh_section(si)

        self._updating = False
        self._saved_expanded = set()
        self._apply_expansion(set())
        self.selection_changed.emit()

    # ---- selection ------------------------------------------------------

    def selected_ids(self) -> set[int]:
        return {hid for hid, item in self._hat_items.items()
                if item.checkState() == Qt.Checked}

    def set_selected(self, ids: set[int]) -> None:
        self._updating = True
        for hid, item in self._hat_items.items():
            item.setCheckState(Qt.Checked if hid in ids else Qt.Unchecked)
        for si in range(len(self._sections)):
            self._refresh_section(si)
        self._updating = False
        self.selection_changed.emit()

    def _on_item_changed(self, item: QStandardItem) -> None:
        if self._updating or item.column() != 0:
            return
        si = item.data(ROLE_SECTION)
        kind = item.data(ROLE_KIND)
        if kind == "hat":
            self._updating = True
            self._refresh_section(si)
            self._updating = False
        elif kind == "section":
            self._toggle_section(si)
        else:
            return
        self.selection_changed.emit()

    def _toggle_section(self, si: int) -> None:
        """Check every shown hat in the section, or uncheck them if all are checked."""
        shown = [it for it in self._section_hat_items[si]
                 if matches(it.data(ROLE_SEARCH), self._proxy.needle)]
        target = Qt.Unchecked if all(it.checkState() == Qt.Checked for it in shown) else Qt.Checked
        self._updating = True
        for it in shown:
            if it.checkState() != target:
                it.setCheckState(target)
        self._refresh_section(si)
        self._updating = False

    def _refresh_section(self, si: int) -> None:
        items = self._section_hat_items[si]
        checked = sum(1 for it in items if it.checkState() == Qt.Checked)
        if checked == 0:
            state = Qt.Unchecked
        elif checked == len(items):
            state = Qt.Checked
        else:
            state = Qt.PartiallyChecked
        sec_item = self._section_items[si]
        sec_item.setCheckState(state)
        sec_item.setText(f"{self._sections[si].title}   ({checked}/{len(items)})")

    # ---- search and expansion ----------------------------------------

    def set_search(self, text: str) -> None:
        needle = text.strip().casefold()
        if needle == self._proxy.needle:
            return
        if needle and not self._proxy.needle:
            self._saved_expanded = self._expanded_sections()
        self._proxy.set_needle(needle)
        if needle:
            self._view.expandAll()
        else:
            self._apply_expansion(self._saved_expanded)

    def expand_all(self) -> None:
        self._apply_expansion(set(range(len(self._sections))))

    def collapse_all(self) -> None:
        self._apply_expansion(set())

    def _expanded_sections(self) -> set[int]:
        result = set()
        for row in range(self._proxy.rowCount()):
            index = self._proxy.index(row, 0)
            if self._view.isExpanded(index):
                result.add(index.data(ROLE_SECTION))
        return result

    def _apply_expansion(self, expanded: set[int]) -> None:
        """Expand the given sections; class groups are always left expanded."""
        for row in range(self._proxy.rowCount()):
            index = self._proxy.index(row, 0)
            for child in range(self._proxy.rowCount(index)):
                self._view.setExpanded(self._proxy.index(child, 0, index), True)
            self._view.setExpanded(index, index.data(ROLE_SECTION) in expanded)


def _item(text: str, *roles) -> QStandardItem:
    item = QStandardItem(text)
    item.setEditable(False)
    for role, value in zip(roles[::2], roles[1::2]):
        item.setData(value, role)
    return item


def _tooltip(hat: Hat) -> str:
    return "\n".join([
        hat.name,
        f"Class: {hat.class_raw.replace('|', ', ')}",
        f"Equip: {hat.equip}",
        f"Path: {hat.path}",
    ])
