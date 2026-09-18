#!/usr/bin/env bash
# Build the colour Race firmware as one flat 4 KiB image for Studio III NTSC.
set -e
cd "$(dirname "$0")"
../../bin/asmx -C 1802 -s9 -l -ew -o race_colour.asm.s9 race_colour.asm
python3 - <<'PY2'
img = bytearray(b'\xFF' * 0x1000)
for line in open('race_colour.asm.s9'):
    line = line.strip()
    if not line.startswith('S1'):
        continue
    n    = int(line[2:4], 16)
    addr = int(line[4:8], 16)
    data = bytes.fromhex(line[8:8 + (n - 3) * 2])
    img[addr:addr + len(data)] = data

open('race_colour.rom', 'wb').write(bytes(img))
print('race_colour.rom: 4096 bytes ($0000-$0FFF)')
PY2
