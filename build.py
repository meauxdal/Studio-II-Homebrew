#!/usr/bin/env python3
"""Build the Studio II homebrew games with the bundled ASMX source."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
GAMES = ROOT / "games"
OUTPUT = ROOT / "build"
ASMX_SOURCE = ROOT / "tools" / "asmx" / "src"


def find_compiler() -> str:
    candidates = ([os.environ["CC"]] if os.environ.get("CC") else []) + [
        "cc",
        "gcc",
        "clang",
    ]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    raise SystemExit(
        "No C compiler found. Install GCC or Clang, then run this command again."
    )


def build_assembler() -> Path:
    platform_tag = f"{platform.system().lower()}-{platform.machine().lower()}"
    tool_dir = OUTPUT / "tools" / platform_tag
    tool_dir.mkdir(parents=True, exist_ok=True)
    executable = tool_dir / ("asmx.exe" if os.name == "nt" else "asmx")
    sources = sorted(ASMX_SOURCE.glob("*.c"))
    headers = sorted(ASMX_SOURCE.glob("*.h"))

    newest_source = max(path.stat().st_mtime for path in sources + headers)
    if executable.exists() and executable.stat().st_mtime >= newest_source:
        return executable

    compiler = find_compiler()
    print(f"Building assembler with {compiler}...")
    command = [
        compiler,
        "-O2",
        "-std=gnu89",
        "-Wno-implicit-int",
        "-Wno-implicit-function-declaration",
        "-Wno-return-type",
        '-DVERSION="2.0b5"',
        f"-I{ASMX_SOURCE}",
        "-o",
        str(executable),
        *(str(path) for path in sources),
    ]
    subprocess.run(command, check=True)
    return executable


def read_srecords(path: Path, include_checksums: bool = False) -> bytearray:
    image = bytearray(b"\xff" * 0x10000)
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("S1"):
            continue
        try:
            count = int(line[2:4], 16)
            address = int(line[4:8], 16)
            data_length = count - 3
            end = 8 + data_length * 2 + (2 if include_checksums else 0)
            data = bytes.fromhex(line[8:end])
        except ValueError as error:
            raise SystemExit(f"Invalid S-record in {path}, line {line_number}") from error
        expected_length = data_length + (1 if include_checksums else 0)
        if len(data) != expected_length:
            raise SystemExit(f"Truncated S-record in {path}, line {line_number}")
        image[address : address + len(data)] = data
    return image


def read_descriptor(path: Path) -> tuple[dict[str, str], list[tuple[int, int]]]:
    fields: dict[str, str] = {}
    pages: list[tuple[int, int]] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        command, value = (part.strip() for part in line.split(":", 1))
        command = command.upper()
        if command == "CODE":
            address, count = value.split(",", 1)
            pages.append((int(address, 16), int(count, 16)))
        else:
            fields[command] = value
    return fields, pages


def put_ascii(buffer: bytearray, offset: int, text: str) -> None:
    encoded = text.encode("ascii")
    buffer[offset : offset + len(encoded)] = encoded


def create_st2(descriptor: Path, image: bytearray, destination: Path) -> None:
    fields, page_groups = read_descriptor(descriptor)
    output = bytearray(8192)
    output[0:4] = b"RCA2"
    output[4] = 1
    output[5] = 1
    put_ascii(output, 8, fields.get("AUTHOR", "??")[:2])
    put_ascii(output, 10, fields.get("DUMPER", "??")[:2])
    put_ascii(output, 16, fields.get("CAT", "") + "\0")
    put_ascii(output, 32, fields.get("TITLE", "") + "\0")

    for address, count in page_groups:
        for page_address in range(address, address + count * 0x100, 0x100):
            output[4] += 1
            page_number = output[4]
            output[64 + page_number - 2] = page_address // 0x100
            target = (page_number - 2) * 0x100 + 0x100
            output[target : target + 0x100] = image[page_address : page_address + 0x100]

    destination.write_bytes(output[: output[4] * 0x100])


def assemble(
    asmx: Path, game_dir: Path, source_name: str, include_checksums: bool = False
) -> bytearray:
    game_output = OUTPUT / game_dir.relative_to(GAMES)
    game_output.mkdir(parents=True, exist_ok=True)
    srecord = game_output / f"{Path(source_name).stem}.s9"
    listing = game_output / f"{Path(source_name).stem}.lst"
    subprocess.run(
        [
            str(asmx),
            "-C",
            "1802",
            "-s9",
            "-l",
            str(listing),
            "-ew",
            "-o",
            str(srecord),
            source_name,
        ],
        cwd=game_dir,
        check=True,
    )
    return read_srecords(srecord, include_checksums)


def build_game(asmx: Path, game_dir: Path) -> list[Path]:
    game_output = OUTPUT / game_dir.relative_to(GAMES)
    descriptor = game_dir / "st2file"
    fields, _ = read_descriptor(descriptor)
    source_field = Path(fields["SOURCE"]).name
    source_name = source_field.removesuffix(".bin")
    # Preserve the original s9tobinary.py behavior for byte-identical builds.
    image = assemble(
        asmx, game_dir, source_name, include_checksums=source_field.endswith(".bin")
    )
    stem = Path(source_name).stem
    cartridge = game_output / Path(fields["BINARY"]).name
    create_st2(descriptor, image, cartridge)
    built = [cartridge]

    if source_field.endswith(".bin"):
        binary = game_output / f"{stem}.bin"
        binary.write_bytes(image[0x400:0x1000])
        built.insert(0, binary)

    if "ROM" in fields:
        rom = game_output / Path(fields["ROM"]).name
        rom.write_bytes(image[:0x1000])
        built.append(rom)

    return built


def game_directories(selection: str) -> list[Path]:
    targets = sorted(
        (
            path
            for path in GAMES.glob("*/*")
            if path.is_dir() and (path / "st2file").exists()
        ),
        key=lambda path: path.as_posix(),
    )
    normalized = selection.replace("\\", "/").strip("/").lower()
    if normalized == "all":
        return targets

    exact = {
        path.relative_to(GAMES).as_posix().lower(): path
        for path in targets
    }
    if normalized in exact:
        return [exact[normalized]]

    by_title = [path for path in targets if path.parent.name.lower() == normalized]
    if by_title:
        return by_title

    choices = ", ".join(path.relative_to(GAMES).as_posix() for path in targets)
    raise SystemExit(
        f"Unknown game or target '{selection}'. Choose a title, all, or one of: {choices}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "game",
        nargs="?",
        default="all",
        help="title or title/target (default: all)",
    )
    args = parser.parse_args()

    asmx = build_assembler()
    built: list[Path] = []
    for game_dir in game_directories(args.game):
        print(f"Building {game_dir.relative_to(GAMES).as_posix()}...")
        built.extend(build_game(asmx, game_dir))

    print("\nBuilt:")
    for path in built:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Build failed with exit code {error.returncode}.") from error
