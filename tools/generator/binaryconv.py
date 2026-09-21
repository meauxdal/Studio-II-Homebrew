#
#	File Conversions
#
from pathlib import Path


def writeFile(code,start,length,target,name):
	code = code[start:start+length]
	out = ",".join(code)
	Path(target).write_text(
		"/* GENERATED */\n\nstatic PROGMEM prog_uchar "
		+ name + "[" + str(len(code)) + "] = {" + out + "};"
	)

bin = Path("studio2.rom").read_bytes()
code = []
for b in bin:
	code.append(str(b))
code[0x3E] = "56"			# Don't wait for B1
		
writeFile(code,0,2048,"studio2.h","_studio2")
writeFile(code,0,1024,"studio2_bios.h","_studio2_bios")
writeFile(code,1024,1024,"studio2_game.h","_studio2_game")
