"""Loading database.csv and grouping hats into the sections shown in the tree."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from pathlib import Path

SEPARATOR = ";"
NO_UPDATE = "None"
ALL_CLASSES = "All classes"
MULTI_CLASS = "Multi-class"
PLACEHOLDER_DATE = "2001-01-01"
INTERNAL_HATS = {"defhat"}  # used by nhcustom2 itself; never shown or written

CLASS_ORDER = [
    ALL_CLASSES, MULTI_CLASS,
    "Scout", "Soldier", "Pyro", "Demo", "Heavy", "Engineer", "Medic", "Sniper", "Spy",
]

COMMUNITY_TITLE = "Community cosmetics"


@dataclass(frozen=True)
class Hat:
    id: int  # row number in the database, unique per hat
    name: str
    class_raw: str
    equip: str
    date: str
    update: str
    path: str

    @property
    def class_group(self) -> str:
        if self.class_raw == ALL_CLASSES:
            return ALL_CLASSES
        if "|" in self.class_raw:
            return MULTI_CLASS
        return self.class_raw

    @property
    def is_community(self) -> bool:
        return (self.date == PLACEHOLDER_DATE
                and self.class_raw == ALL_CLASSES
                and self.update == NO_UPDATE)


@dataclass
class ClassGroup:
    label: str
    hats: list[Hat]


@dataclass
class Section:
    kind: str  # "update", "gap" or "community"
    title: str
    date: str  # date shown next to the title; empty for community
    update: str | None  # raw update value for named updates
    groups: list[ClassGroup] = field(default_factory=list)

    @property
    def hats(self) -> list[Hat]:
        return [h for g in self.groups for h in g.hats]


def load_database(path: Path) -> list[Hat]:
    # The database has no quoting, so plain splitting is exact (csv would
    # mangle a stray quote character in a hat name).
    text = path.read_text(encoding="utf-8-sig")
    lines = [line.rstrip("\r") for line in text.split("\n") if line.strip()]
    if not lines:
        raise ValueError(f"{path} is empty")
    header = [h.strip().lower() for h in lines[0].split(SEPARATOR)]
    required = ["hat", "class", "equip", "date", "update", "path"]
    missing = [h for h in required if h not in header]
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    col = {name: header.index(name) for name in required}

    hats = []
    for row_number, line in enumerate(lines[1:], start=1):
        cells = line.split(SEPARATOR)
        if len(cells) < len(header):
            continue
        name = cells[col["hat"]].strip()
        if not name or name in INTERNAL_HATS:
            continue
        hats.append(Hat(
            id=row_number,
            name=name,
            class_raw=cells[col["class"]].strip(),
            equip=cells[col["equip"]].strip(),
            date=cells[col["date"]].strip(),
            update=cells[col["update"]].strip(),
            path=cells[col["path"]].strip(),
        ))
    return hats


def display_update(update: str) -> str:
    """'Scream Fortress VII|Scream Fortress 2015' -> 'Scream Fortress VII / Scream Fortress 2015'."""
    return " / ".join(part.strip() for part in update.split("|"))


def _class_sort_key(label: str):
    if label in CLASS_ORDER:
        return (CLASS_ORDER.index(label), "")
    return (len(CLASS_ORDER), label.casefold())


def _group_by_class(hats: list[Hat]) -> list[ClassGroup]:
    by_class: dict[str, list[Hat]] = {}
    for hat in hats:
        by_class.setdefault(hat.class_group, []).append(hat)
    return [
        ClassGroup(label, sorted(by_class[label], key=lambda h: (h.name.casefold(), h.id)))
        for label in sorted(by_class, key=_class_sort_key)
    ]


def _gap_title(dates: list[str]) -> str:
    first, last = min(dates), max(dates)
    return f"— {first} —" if first == last else f"— {first} – {last} —"


def build_sections(hats: list[Hat]) -> list[Section]:
    """Named updates in release order, with update-less hats in nameless
    sections between them by date, and community cosmetics last."""
    community = [h for h in hats if h.is_community]
    named: dict[str, list[Hat]] = {}
    unnamed: list[Hat] = []
    for hat in hats:
        if hat.is_community:
            continue
        if hat.update == NO_UPDATE:
            unnamed.append(hat)
        else:
            named.setdefault(hat.update, []).append(hat)

    # An update spanning several dates is placed by its earliest one.
    ordered = sorted(named, key=lambda u: (min(h.date for h in named[u]), u.casefold()))
    starts = [min(h.date for h in named[u]) for u in ordered]

    # Gap i holds hats dated on/after update i-1 and before update i, so an
    # update-less hat sharing a date with an update lands right after it.
    gaps: dict[int, list[Hat]] = {}
    for hat in unnamed:
        gaps.setdefault(bisect.bisect_right(starts, hat.date), []).append(hat)

    sections = []
    for i in range(len(ordered) + 1):
        if i > 0:
            update = ordered[i - 1]
            sections.append(Section("update", display_update(update), starts[i - 1],
                                    update, _group_by_class(named[update])))
        if i in gaps:
            dates = [h.date for h in gaps[i]]
            sections.append(Section("gap", _gap_title(dates), min(dates), None,
                                    _group_by_class(gaps[i])))
    if community:
        sections.append(Section("community", COMMUNITY_TITLE, "", None,
                                _group_by_class(community)))
    return sections
