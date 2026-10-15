from nohatsgui.config import (
    KEEP, REMOVE, escape_regex, exact, generate, is_generated, parse_generated,
)
from nohatsgui.database import Hat, build_sections


def hat(id, name, update="U", path=None, cls="Scout", date="2010-01-01"):
    return Hat(id, name, cls, "Hat", date, update, path or f"models/{id}.*")


def test_escape_regex():
    assert escape_regex("The Voodoo Juju (Slight Return)") == r"The Voodoo Juju \(Slight Return\)"
    assert escape_regex("a.b*c+d?e|f^g$h[i]j{k}l\\m") == r"a\.b\*c\+d\?e\|f\^g\$h\[i\]j\{k\}l\\m"
    assert escape_regex("MONOCULUS!") == "MONOCULUS!"


def test_exact_quotes_and_doubles_quotes():
    # Matches the documented form: hat:"The Voodoo Juju \(Slight Return\)"
    assert exact("The Voodoo Juju (Slight Return)") == r'"^The Voodoo Juju \(Slight Return\)$"'
    assert exact('Say "hi"') == '"^Say ""hi""$"'


def test_full_update_collapses_to_one_line():
    hats = [hat(1, "A", "SF VII|SF 2015"), hat(2, "B", "SF VII|SF 2015"), hat(3, "C", "Other")]
    text = generate(KEEP, build_sections(hats), {1, 2}, hats)
    assert r'update:"^SF VII\|SF 2015$"' in text
    assert "hat:" not in text


def test_partial_update_lists_hats():
    hats = [hat(1, "A"), hat(2, "B")]
    text = generate(REMOVE, build_sections(hats), {2}, hats)
    lines = text.splitlines()
    assert lines[1] == "remove"
    assert 'hat:"^B$"' in lines
    assert "update:" not in text


def test_nameless_section_never_uses_update_line():
    hats = [hat(1, "A", "None"), hat(2, "B", "None")]
    text = generate(KEEP, build_sections(hats), {1, 2}, hats)
    assert "update:" not in text
    assert 'hat:"^A$"' in text and 'hat:"^B$"' in text


def test_duplicate_names_narrowed_by_path():
    hats = [hat(1, "Medal", "None", "models/x/a.*", "All classes", "2001-01-01"),
            hat(2, "Medal", "None", "models/x/b.*", "All classes", "2001-01-01")]
    one = generate(KEEP, build_sections(hats), {1}, hats)
    assert r'hat:"^Medal$"}path:"^models/x/a\.\*$"' in one
    both = generate(KEEP, build_sections(hats), {1, 2}, hats)
    assert "path:" not in both


def test_round_trip():
    hats = [hat(1, 'The "Quoted" (Hat)!', "U1"), hat(2, "Other", "U1"),
            hat(3, "Full A", "U2"), hat(4, "Full B", "U2"),
            hat(5, "Dup", "None", "models/p/1.*"), hat(6, "Dup", "None", "models/p/2.*")]
    selected = {1, 3, 4, 6}
    text = generate(REMOVE, build_sections(hats), selected, hats)
    assert is_generated(text)
    saved = parse_generated(text)
    assert saved.mode == REMOVE
    assert saved.updates == {"U2"}
    assert saved.resolve(hats) == selected


def test_hand_written_config_not_generated():
    assert not is_generated("keep\nhat:foppish physician\n")
