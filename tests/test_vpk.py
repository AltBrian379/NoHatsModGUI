import hashlib
import struct
import zlib
from pathlib import Path

import pytest

from nohatsgui.vpk import (
    EMBEDDED, build_custom, decompile, extract, extracted_name, find_input_vpk, has_decompiled, pack, read_entries,
    vpk_parts,
)


def build_vpk(path: Path, files: dict[str, bytes], archive: int = EMBEDDED, version: int = 2) -> None:
    """Write a VPK holding files, embedded or in path's _000 archive."""
    tree = bytearray()
    data = bytearray()
    by_ext: dict[str, dict[str, list[tuple[str, bytes]]]] = {}
    for name, content in files.items():
        folder, _, file_name = name.rpartition("/")
        stem, _, ext = file_name.rpartition(".")
        by_ext.setdefault(ext, {}).setdefault(folder or " ", []).append((stem, content))
    for ext, folders in by_ext.items():
        tree += ext.encode() + b"\0"
        for folder, entries in folders.items():
            tree += folder.encode() + b"\0"
            for stem, content in entries:
                tree += stem.encode() + b"\0"
                tree += struct.pack("<IHHIIH", zlib.crc32(content), 0, archive, len(data), len(content), 0xFFFF)
                data += content
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"
    if version == 1:
        header = struct.pack("<III", 0x55AA1234, 1, len(tree))
    else:
        embedded = len(data) if archive == EMBEDDED else 0
        header = struct.pack("<IIIIIII", 0x55AA1234, 2, len(tree), embedded, 0, 0, 0)
    if archive == EMBEDDED:
        path.write_bytes(header + tree + data)
    else:
        path.write_bytes(header + tree)
        path.with_name(f"{extracted_name(path)}_{archive:03d}.vpk").write_bytes(bytes(data))


FILES = {
    "models/player/items/scout/cap.mdl": b"model data",
    "models/player/items/scout/cap.vvd": b"",
    "models/player/items/spy/hat.dx90.vtx": b"\x00\x01\x02" * 100,
}


@pytest.mark.parametrize("version", [1, 2])
def test_extract_embedded(tmp_path, version):
    vpk = tmp_path / "mod.vpk"
    build_vpk(vpk, FILES, version=version)
    assert extract(vpk, tmp_path / "out") == len(FILES)
    for name, content in FILES.items():
        assert (tmp_path / "out" / name).read_bytes() == content


def test_extract_multi_part(tmp_path):
    vpk = tmp_path / "pak01_dir.vpk"
    build_vpk(vpk, FILES, archive=0)
    assert (tmp_path / "pak01_000.vpk").is_file()
    extract(vpk, tmp_path / "out")
    assert (tmp_path / "out" / "models/player/items/scout/cap.mdl").read_bytes() == b"model data"


def test_extract_reports_progress(tmp_path):
    vpk = tmp_path / "mod.vpk"
    build_vpk(vpk, FILES)
    seen = []
    extract(vpk, tmp_path / "out", lambda done, total: seen.append((done, total)))
    assert seen[-1] == (3, 3)


def test_corrupt_data_is_rejected(tmp_path):
    vpk = tmp_path / "mod.vpk"
    build_vpk(vpk, {"models/a.mdl": b"good"})
    vpk.write_bytes(vpk.read_bytes()[:-4] + b"evil")
    with pytest.raises(ValueError, match="CRC"):
        extract(vpk, tmp_path / "out")


def test_not_a_vpk(tmp_path):
    bad = tmp_path / "bad.vpk"
    bad.write_bytes(b"not a vpk at all")
    with pytest.raises(ValueError, match="not a VPK"):
        read_entries(bad)


def test_unsafe_paths_are_rejected(tmp_path):
    vpk = tmp_path / "mod.vpk"
    build_vpk(vpk, {"../escape.txt": b"x"})
    with pytest.raises(ValueError, match="unsafe"):
        extract(vpk, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_decompile_replaces_stale_models_and_removes_vpk(tmp_path):
    vpk = tmp_path / "no_hats_bgum.vpk"
    build_vpk(vpk, FILES)
    (tmp_path / "models" / "empty" / "folders").mkdir(parents=True)  # what broken vpk.exe leaves
    assert not has_decompiled(tmp_path)

    assert decompile(vpk) == len(FILES)

    assert has_decompiled(tmp_path)
    assert not (tmp_path / "models" / "empty").exists()
    assert not vpk.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["models"]


def test_failed_decompile_leaves_input_alone(tmp_path):
    vpk = tmp_path / "no_hats_bgum.vpk"
    build_vpk(vpk, {"models/a.mdl": b"good"})
    vpk.write_bytes(vpk.read_bytes()[:-4] + b"evil")
    with pytest.raises(ValueError):
        decompile(vpk)
    assert vpk.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["no_hats_bgum.vpk"]


def test_extracted_name():
    assert extracted_name(Path("no_hats_bgum.vpk")) == "no_hats_bgum"
    assert extracted_name(Path("pak01_dir.vpk")) == "pak01"


def test_vpk_parts_includes_numbered_archives(tmp_path):
    for name in ["pak01_dir.vpk", "pak01_000.vpk", "pak01_001.vpk", "other_000.vpk"]:
        (tmp_path / name).write_bytes(b"")
    parts = [p.name for p in vpk_parts(tmp_path / "pak01_dir.vpk")]
    assert parts == ["pak01_dir.vpk", "pak01_000.vpk", "pak01_001.vpk"]


def test_find_input_vpk_skips_numbered_parts(tmp_path):
    assert find_input_vpk(tmp_path / "missing") is None
    (tmp_path / "pak01_000.vpk").write_bytes(b"")
    assert find_input_vpk(tmp_path) is None
    (tmp_path / "pak01_dir.vpk").write_bytes(b"")
    assert find_input_vpk(tmp_path) == tmp_path / "pak01_dir.vpk"


def test_pack_round_trips(tmp_path):
    root = tmp_path / "output"
    for name, content in FILES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(content)
    (root / "readme.txt").write_bytes(b"not under models, so not packed")
    vpk = root / "custom.vpk"

    assert pack(root, vpk) == len(FILES)

    entries, _ = read_entries(vpk)
    assert sorted(e.path for e in entries) == sorted(FILES)
    extract(vpk, tmp_path / "again")
    for name, content in FILES.items():
        assert (tmp_path / "again" / name).read_bytes() == content
    assert not list(root.glob("*.tmp"))


def test_pack_writes_valve_checksums(tmp_path):
    root = tmp_path / "output"
    (root / "models").mkdir(parents=True)
    (root / "models" / "a.mdl").write_bytes(b"abc")
    (root / "models" / "noext").write_bytes(b"")
    vpk = tmp_path / "custom.vpk"
    pack(root, vpk)

    data = vpk.read_bytes()
    _, version, tree_size, data_size, archive_md5_size, other_md5_size, _ = struct.unpack_from("<7I", data)
    assert (version, data_size, archive_md5_size, other_md5_size) == (2, 3, 0, 48)
    tree = data[28:28 + tree_size]
    other = data[-48:]
    assert other[:16] == hashlib.md5(tree).digest()
    assert other[16:32] == hashlib.md5(b"").digest()
    assert other[32:] == hashlib.md5(data[:-16]).digest()
    assert sorted(e.path for e in read_entries(vpk)[0]) == ["models/a.mdl", "models/noext"]


def test_pack_without_models_fails(tmp_path):
    with pytest.raises(ValueError, match="No files"):
        pack(tmp_path, tmp_path / "custom.vpk")
    assert not (tmp_path / "custom.vpk").exists()


def test_build_custom_moves_output_down_and_packs(tmp_path):
    output = tmp_path / "output"
    for name, content in FILES.items():
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        (output / name).write_bytes(content)
    stale = output / "no-hats-bgum-custom" / "models" / "old.mdl"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"from a previous run")

    vpk, count = build_custom(output, "no-hats-bgum-custom")

    assert vpk == output / "no-hats-bgum-custom.vpk"
    assert count == len(FILES)
    assert not (output / "models").exists()
    assert not stale.exists()
    for name, content in FILES.items():
        assert (output / "no-hats-bgum-custom" / name).read_bytes() == content
    assert sorted(e.path for e in read_entries(vpk)[0]) == sorted(FILES)
