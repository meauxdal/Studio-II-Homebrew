@echo off
cd ..\generator
call build.bat
cd ..\emulator
mingw32-make
if not exist ..\..\build\tools mkdir ..\..\build\tools
copy /Y studio2.exe ..\..\build\tools
