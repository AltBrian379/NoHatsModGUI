"""Decompiling (extracting) and packing Valve VPK files.

TF2's own vpk.exe currently creates the folder tree but writes no files when a
VPK is dragged onto it, so the format is read directly instead. Format:
https://developer.valvesoftware.com/wiki/VPK_(file_format)
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
import shutil
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

SIGNATURE = 0x55AA1234
EMBEDDED = 0x7FFF  # archive index meaning "data follows the tree in this file"
ENTRY_END = 0xFFFF
EXTRACT_FOLDER_NAME = ".decompiling"


@dataclass(frozen=True)
class Entry:
    path: str
    crc: int
    preload: bytes
    archive: int
    offset: int
    length: int


def read_entries(vpk: Path) -> tuple[list[Entry], int]:
    """The VPK's file entries, and where its embedded data section starts."""
    with open(vpk, "rb") as f:
        signature, version, tree_size = struct.unpack("<III", f.read(12))
        if signature != SIGNATURE:
            raise ValueError(f"{vpk.name} is not a VPK file")
        if version == 1:
            header_size = 12
        elif version == 2:
            header_size = 28
        else:
            raise ValueError(f"{vpk.name} uses unsupported VPK version {version}")
        f.seek(header_size)
        tree = f.read(tree_size)
    if len(tree) != tree_size:
        raise ValueError(f"{vpk.name} is truncated")

    pos = 0

    def string() -> str:
        nonlocal pos
        end = tree.index(b"\0", pos)
        value = tree[pos:end].decode("utf-8")
        pos = end + 1
        return value

    entries = []
    try:
        while extension := string():
            while directory := string():
                while name := string():
                    crc, preload_size, archive, offset, length, end = struct.unpack_from("<IHHIIH", tree, pos)
                    if end != ENTRY_END:
                        raise ValueError("bad entry terminator")
                    pos += 18
                    preload = tree[pos:pos + preload_size]
                    pos += preload_size
                    # A single space stands for "none" (root folder, no extension).
                    file_name = name if extension == " " else f"{name}.{extension}"
                    path = file_name if directory == " " else f"{directory}/{file_name}"
                    entries.append(Entry(path, crc, preload, archive, offset, length))
    except (ValueError, struct.error) as error:  # includes UnicodeDecodeError
        raise ValueError(f"{vpk.name} has a corrupt directory tree") from error
    return entries, header_size + tree_size


def archive_path(vpk: Path, index: int) -> Path:
    """The numbered archive of a multi-part VPK: pak01_dir.vpk -> pak01_003.vpk."""
    return vpk.with_name(f"{extracted_name(vpk)}_{index:03d}.vpk")


def _safe_target(destination: Path, path: str) -> Path:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts or any(part in ("", ".", "..") or ":" in part for part in parts) or path.startswith("/"):
        raise ValueError(f"Refusing to extract unsafe path {path!r}")
    return destination.joinpath(*parts)


def extract(vpk: Path, destination: Path, progress: Callable[[int, int], None] | None = None) -> int:
    """Extract every file in the VPK into destination. Returns the number of files."""
    entries, data_start = read_entries(vpk)
    handles = {EMBEDDED: open(vpk, "rb")}
    try:
        for done, entry in enumerate(entries, 1):
            target = _safe_target(destination, entry.path)
            data = b""
            if entry.length:
                if entry.archive not in handles:
                    handles[entry.archive] = open(archive_path(vpk, entry.archive), "rb")
                handle = handles[entry.archive]
                handle.seek(entry.offset + (data_start if entry.archive == EMBEDDED else 0))
                data = handle.read(entry.length)
                if len(data) != entry.length:
                    raise ValueError(f"{vpk.name} is truncated ({entry.path})")
            content = entry.preload + data
            if zlib.crc32(content) != entry.crc:
                raise ValueError(f"{entry.path} in {vpk.name} is corrupt (CRC mismatch)")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if progress is not None:
                progress(done, len(entries))
    finally:
        for handle in handles.values():
            handle.close()
    return len(entries)


def vpk_parts(vpk: Path) -> list[Path]:
    """The VPK, plus the numbered archives of a multi-part *_dir.vpk."""
    if not vpk.stem.lower().endswith("_dir"):
        return [vpk]
    prefix = glob.escape(vpk.stem[:-len("_dir")])
    return [vpk] + sorted(vpk.parent.glob(f"{prefix}_[0-9][0-9][0-9].vpk"))


def extracted_name(vpk: Path) -> str:
    """The VPK's name without .vpk (or _dir.vpk)."""
    stem = vpk.stem
    return stem[:-len("_dir")] if stem.lower().endswith("_dir") else stem


def has_decompiled(input_folder: Path) -> bool:
    """True if input/models holds files (not just the empty folders a broken vpk.exe leaves)."""
    models = input_folder / "models"
    return models.is_dir() and any(path.is_file() for path in models.rglob("*"))


def find_input_vpk(input_folder: Path) -> Path | None:
    """A VPK placed in nhcustom2's input folder, skipping the numbered parts of a multi-part VPK."""
    if not input_folder.is_dir():
        return None
    vpks = sorted(path for path in input_folder.glob("*.vpk")
                  if path.is_file() and not re.search(r"_\d{3}$", path.stem))
    return vpks[0] if vpks else None


def decompile(vpk: Path, progress: Callable[[int, int], None] | None = None) -> int:
    """Extract the VPK into its own folder, then delete the VPK files. Returns the number of files.

    Extracts into a temporary folder first so a failure leaves the input folder untouched.
    """
    folder = vpk.parent
    work = folder / EXTRACT_FOLDER_NAME
    if work.exists():
        shutil.rmtree(work)
    try:
        count = extract(vpk, work, progress)
        for child in list(work.iterdir()):
            destination = folder / child.name
            if destination.is_dir():
                shutil.rmtree(destination)
            elif destination.exists():
                destination.unlink()
            child.rename(destination)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for part in vpk_parts(vpk):
        part.unlink()
    return count


def pack(root: Path, vpk: Path, folders: tuple[str, ...] = ("models",),
         progress: Callable[[int, int], None] | None = None) -> int:
    """Pack root's files under the given top-level folders into a single-file VPK v2,
    laid out like vpk.exe's output. Paths inside the VPK are relative to root
    (e.g. models/...). Returns the number of files.
    """
    # Tree order: extension, then folder, then name.
    entries = []
    for folder in folders:
        # os.walk lists files without a stat call each, which matters for ~27k files.
        for current, _, file_names in os.walk(root / folder):
            directory = Path(current).relative_to(root).as_posix()
            for file_name in file_names:
                stem, dot, extension = file_name.rpartition(".")
                if not dot:
                    stem, extension = file_name, " "
                entries.append((extension, directory, stem, os.path.join(current, file_name)))
    if not entries:
        raise ValueError(f"No files to pack in {root}")
    entries.sort()

    temporary = vpk.with_name(vpk.name + ".tmp")
    data_file = vpk.with_name(vpk.name + ".data.tmp")
    try:
        # The tree holds each file's CRC and size and comes before the data,
        # so read each file once into a side file, then assemble.
        tree = bytearray()
        offset = 0
        previous_extension = previous_directory = None
        with open(data_file, "wb") as data:
            for done, (extension, directory, stem, path) in enumerate(entries, 1):
                if extension != previous_extension:
                    if previous_extension is not None:
                        tree += b"\0\0"  # end of folder, end of extension
                    tree += extension.encode("utf-8") + b"\0"
                    previous_extension, previous_directory = extension, None
                if directory != previous_directory:
                    if previous_directory is not None:
                        tree += b"\0"
                    tree += directory.encode("utf-8") + b"\0"
                    previous_directory = directory
                with open(path, "rb") as source:
                    content = source.read()
                data.write(content)
                tree += stem.encode("utf-8") + b"\0"
                tree += struct.pack("<IHHIIH", zlib.crc32(content), 0, EMBEDDED, offset, len(content), ENTRY_END)
                offset += len(content)
                if progress is not None:
                    progress(done, len(entries))
        tree += b"\0\0\0"  # end of last folder, last extension, and the tree

        whole = hashlib.md5()
        with open(temporary, "wb") as out, open(data_file, "rb") as data:
            def write(chunk: bytes) -> None:
                out.write(chunk)
                whole.update(chunk)

            write(struct.pack("<7I", SIGNATURE, 2, len(tree), offset, 0, 48, 0))
            write(bytes(tree))
            while chunk := data.read(1 << 20):
                write(chunk)
            write(hashlib.md5(bytes(tree)).digest())
            write(hashlib.md5(b"").digest())  # no archive MD5 section in a single-file VPK
            out.write(whole.digest())
        temporary.replace(vpk)
    finally:
        temporary.unlink(missing_ok=True)
        data_file.unlink(missing_ok=True)
    return len(entries)


def build_custom(output: Path, name: str, progress: Callable[[int, int], None] | None = None) -> tuple[Path, int]:
    """Move nhcustom2's output/models down into output/<name>/models, then pack that folder
    into output/<name>.vpk (paths inside start at models/, as TF2 expects).
    Returns the VPK and the number of files.
    """
    folder = output / name
    models = output / "models"
    if models.is_dir():
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        models.rename(folder / "models")
    vpk = output / f"{name}.vpk"
    return vpk, pack(folder, vpk, progress=progress)
