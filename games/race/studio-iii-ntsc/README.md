# Race DX — CDP1864 colour

Extended colour build of azya52's beam-raced *Race*
(<https://github.com/azya52/rcastudioii>, write-up at
<https://habr.com/ru/articles/422277/>), running on the Studio III NTSC machine.

## Loading it

Race is assembled as a 4 KB address image covering `$0000-$0FFF`, then packaged
in two forms:

| file | loads as |
| --- | --- |
| `race_colour.st2` | normal cartridge load |
| `race_colour.rom` | firmware (`--bios` / F2 Load Firmware) |

Machine must be **Studio III NTSC**:

```
obj_dir/Vtop --machine studio3ntsc \
  --bios .../build/race/studio-iii-ntsc/race_colour.rom
```

On MiSTer, select Studio III NTSC and load `race_colour.st2` normally. The
original 4 KB firmware-image distribution remains available as
`race_colour.rom` for **F2 Load Firmware**.

On the initial load, press **CLEAR** once before playing. Without that first
reset the title display can occasionally start in a bad raster state. This has
only been observed on the initial load; subsequent starts are stable.

`python build.py race` regenerates both files from `race_colour.asm` and copies
the accompanying `race_colour.txt` release notes.

## Image layout

The assembled program already occupies the correct Studio III address space.
The root build script starts with a 4 KB `$FF`-filled image and places each S-record at its
assembled address, then writes that complete image directly as `race_colour.rom`.

The active code/data is in `$0000-$07FF` and `$0C00-$0FFF`; `$0800-$0BFF`
remains `$FF` in the ROM image. Those bytes do not need to be removed or packed:
the flat file preserves the CPU address layout directly.

Earlier builds split the program into `race_colour_lower.rom` plus
`race_colour_upper.st2`. That was only needed when the upper portion was being
loaded through the cartridge path. The `.st2` file was a sparse container with a
256-byte header and selected 256-byte pages, so the two old files could not be
concatenated byte-for-byte into a valid ROM. A flat 4 KB firmware image removes
that loader workaround entirely.

## How the colour works

Race has no framebuffer — its ISR re-points R0 at ROM data per scanline on exact
cycle counts. The CDP1864 colour index is `{ram_a[7:5], ram_a[2:0]}` of whatever
address the DMA presents, so **a pixel's colour follows the ROM address of the
graphic being displayed, not where it lands on screen.**

This is the opposite of every other colour port here, where the 64 cells act as
fixed screen bands. It is why a plain 8-band table still reads as deliberate: the
perspective road markers gradient red -> magenta -> green -> yellow -> white
toward the viewer for free, because their data sits at ascending ROM addresses.

### Why groups 2, 3 and 4 share a colour

Not a preference — the geometry forces it. Traced with `DMA_TRACE`, the display
rows land in colour groups like this:

| display rows | what | groups |
| --- | --- | --- |
| 0-4 | `SPEED TIME SCORE` header | 3 on row 0, 4 below |
| 8-15 | the digit line | 2 on row 8, 3 below |
| 44-59 | mountains | 4, 5, 6, 7 (4 rows each) |
| 59-66 | the big `AZYA,2020` line | 2, then 3, then 4 |
| 64-127 | road and car | 0-7, 8 rows each |

Every text string on the game straddles a group boundary, so giving 2, 3 and 4
different values bands all three of them. The first version did exactly that,
which is why the score digits had a green top row on a yellow body.

White is the value to unify on because group 4 also draws the mountain tops at
rows 44-47 — the same choice that makes the text legible caps the peaks with
snow. Groups 5-7 keep cyan/red/magenta for the lower slopes and, further down
the screen, for the near road and the car; groups 0 and 1 are the far road alone.

Value 2 is blue, identical to the background, so it is never usable here.

Colouring per graphic rather than per band would need the table indexed by each
element's own ROM address; that has not been done.

`colourInit` sits at `$0400`, which is `$FF` filler in the original image, and
ends with `lbr start`. Reset first forces the CDP1861 display off, then
`colourInit` disables CPU interrupts (`sex r3 / dis / $23`) while loading the
colour table.

`OUT 1` is left alone during colour initialization because it also affects the
display-enable path on this machine. `INP 1` is deferred until RAM and the title
interrupt vector are initialized.

## Changes to azya52's source

`race_multicart.asm` is their original with two fixes. Reset loaded the entry
address with `phi r3` where the comment says `R3.Low = main`; it must be `plo
r3`, or the machine jumps to `$0000` and hangs. The finish-line transition now
loops from the second road back to the first road instead of reading the
graphics table as a nonexistent third road. Score and timer state are retained.
`race_colour.asm` contains the same fixes plus `colourInit` and the band table.

Race DX v1.05 also adds a short periodic low-tone pulse while the car is on the
roadside. The pulse is deliberately brief rather than sustained. The final
countdown beep is six frames longer than the preceding four beeps. Roadside
sound bookkeeping runs only on non-road-draw frames so it does not consume the
raster margin used by the finish-line renderer.

The current timing pass preserves the exact 60-frame subsecond phase across road
transitions. During the paused between-road sequence, the digit line shows the
completed road number, elapsed road time to hundredths (rounded from 1/60-second
frames), and the existing score. The normal race display is restored before the
next road starts.

## Status

The colour build was previously verified in the headless sim using the split
firmware/cartridge loading method — `colour: enabled 1`, with successful captures
through frames 60/200/400/650/880 (title screen, mountains, road markers, speed
164, score 00063).

Both `race_colour.rom` and `race_colour.st2` are reconstructed from the same
assembled address image. The `.st2` stores pages `$00-$07` and `$0C-$0F`; its
payload matches those addresses in the flat ROM and leaves the RAM gap unmapped.
