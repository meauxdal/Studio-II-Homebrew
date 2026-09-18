@echo off
python process.py
python binaryconv.py
copy /Y *.h ..\emulator
