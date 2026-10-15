from pathlib import Path

import pytest

from nohatsgui.database import (
    ALL_CLASSES, COMMUNITY_TITLE, MULTI_CLASS, build_sections, load_database,
)

HEADER = "hat;class;equip;date;update;path\n"


def write_db(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "database.csv"
    path.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return path


@pytest.fixture
def sample(tmp_path):
    return load_database(write_db(tmp_path, [
        "defhat;Scout|Soldier;Hat;2001-01-01;None;models/nope",
        "Mining Light;Engineer;None;2009-05-21;Sniper vs. Spy Update;models/a",
        "Demoman's Fro;Demo;Hat;2010-09-29;Sniper vs. Spy Update;models/b",
        "Batter's Helmet;Scout;Hat;2009-08-13;Classless Update;models/c",
        "Gentle Manne's Service Medal;All classes;Medal;2009-08-13;Classless Update;models/d",
        "Ghastly Gibus;Scout|Medic;Hat;2009-08-13;Classless Update;models/e",
        "Archimedes;Medic;Hat;2009-08-13;Classless Update;models/f",
        "Cheater's Lament;All classes;None;2009-09-02;None;models/g",
        "Same Day Hat;Pyro;Hat;2009-08-13;None;models/h",
        "Haunted Thing;Spy;Hat;2009-10-29;Haunted Hallowe'en Special;models/i",
        "UGC Participant;All classes;Medal;2001-01-01;None;models/j",
        "Early Hat;Soldier;Hat;2008-01-01;None;models/k",
        "SF Hat;Sniper;Hat;2015-10-28;Scream Fortress VII|Scream Fortress 2015;models/l",
    ]))


def titles(sections):
    return [s.title for s in sections]


def test_internal_hat_hidden(sample):
    assert "defhat" not in {h.name for h in sample}


def test_section_order(sample):
    assert titles(build_sections(sample)) == [
        "— 2008-01-01 —",
        "Sniper vs. Spy Update",  # placed by its earliest date
        "Classless Update",
        "— 2009-08-13 – 2009-09-02 —",  # same-date tie goes after the named update
        "Haunted Hallowe'en Special",
        "Scream Fortress VII / Scream Fortress 2015",
        COMMUNITY_TITLE,
    ]


def test_class_group_order(sample):
    classless = build_sections(sample)[2]
    assert [g.label for g in classless.groups] == [ALL_CLASSES, MULTI_CLASS, "Scout", "Medic"]


def test_community_requires_all_three_fields(sample):
    community = build_sections(sample)[-1]
    assert [h.name for h in community.hats] == ["UGC Participant"]


def test_alphabetical_within_group(tmp_path):
    hats = load_database(write_db(tmp_path, [
        "zebra;Scout;Hat;2010-01-01;U;p1",
        "Apple;Scout;Hat;2010-01-01;U;p2",
        "banana;Scout;Hat;2010-01-01;U;p3",
    ]))
    assert [h.name for h in build_sections(hats)[0].hats] == ["Apple", "banana", "zebra"]


def test_missing_column(tmp_path):
    path = tmp_path / "database.csv"
    path.write_text("hat;class\nx;Scout\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_database(path)


def test_real_database_loads():
    path = Path(__file__).resolve().parent.parent / "database.csv"
    if not path.exists():
        pytest.skip("no database.csv in project root")
    hats = load_database(path)
    sections = build_sections(hats)
    assert sum(len(s.hats) for s in sections) == len(hats)
    assert sections[-1].title == COMMUNITY_TITLE
    dates = [s.date for s in sections[:-1]]
    assert dates == sorted(dates)
