# Studio-II-Homebrew

Homebrew games for the RCA Studio II family, originally written by Paul Robson and azya52, with colour editions and additional modifications by Alan Steremberg and Elle Ball.

## Games

| Game | RCA Studio II | Toshiba Visicom | Studio III NTSC |
| --- | :---: | :---: | :---: |
| Asteroids | ✓ | ✓ | — |
| Berzerk | ✓ | ✓ | — |
| Combat | ✓ | ✓ | — |
| Hockey | ✓ | ✓ | — |
| Invaders | ✓ | — | — |
| Kaboom | ✓ | — | — |
| Pacman | ✓ | ✓ | — |
| Race | — | — | ✓ |
| Scramble | ✓ | — | — |

Some Studio II cartridges include optional CDP1864 colour data while retaining Studio II compatibility. See [Colour hardware](docs/colour-hardware.md) for details.

## Build

Install [Python 3.9 or newer](https://www.python.org/downloads/) and either GCC or Clang. Then, from the repository root, run:

```shell
python build.py
```

That builds every supported target. A title builds all of its editions:

```shell
python build.py pacman
```

You can also select one target explicitly:

```shell
python build.py pacman/visicom
```

On systems where Python 3 is named `python3`, use `python3 build.py` instead. The script compiles the included ASMX assembler when necessary and writes finished cartridges under `build/<game>/<target>/`.

Studio II and Visicom targets produce a raw `.bin` image and an emulator-ready
`.st2` cartridge. Race produces an emulator-ready `.st2`, its original flat
4 KiB `.rom` firmware image, and release notes.

## Repository layout

- `games/` — maintained game sources, grouped by title and hardware target
- `docs/` — colour, Visicom, and historical hardware documentation
- `tools/asmx/` — the included multi-assembler source
- `tools/emulator/` — Paul Robson's Studio II emulator source
- `tools/generator/` — code-generation utilities used by the emulator projects
- `extras/arduino/` — the historical Arduino port and TV output support

## Upstream compatibility

The `upstream-compatible` branch retains Paul Robson's original repository layout. Game fixes should be made there first when they may be useful upstream, then merged into `main`. This branch contains the reorganized, end-user-facing edition of the project.

See [Visicom support](docs/visicom.md) for technical details of the Toshiba Visicom COM-100 ports.
