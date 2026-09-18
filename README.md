# Studio-II-Homebrew

Studio II-family homebrew games originally by Paul Robson and azya52, with colorization and additional modifications by Alan Steremberg and Elle Ball.

## Build the games

You need:

- [Python 3.9 or newer](https://www.python.org/downloads/)
- A C compiler: GCC or Clang

From the repository root, build every game with:

```shell
python build.py
```

To build just one game, pass its directory name:

```shell
python build.py Pacman
```

The script builds the included ASMX assembler when needed and puts finished files under `build/<game>/`. Normal games produce both a raw `.bin` image and an emulator-ready `.st2` cartridge. Race Colour produces a 4 KiB `.rom` image for Studio III NTSC.

On systems where Python 3 is named `python3`, use `python3 build.py` instead.

## Repository layout

- `Games/` — game source, graphics, metadata, and original per-game build files
- `asmx/` — source for the bundled multi-assembler
- `studio2/` — Studio II emulator source
- `Documents/` — Studio II BIOS and technical source material
- `Arduino/` — Arduino-related Studio II utilities

See [COLOUR.md](COLOUR.md) for the color hardware implementation and [VISICOM.md](VISICOM.md) for Toshiba Visicom COM-100 support.
