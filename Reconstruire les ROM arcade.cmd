@echo off
cd /d "%~dp0"
title FV2 - Reconstruire les ROM arcade
echo.
echo Reconstruit fv2_crom_swap16.bin (8 Mo) et fv2_vrom.bin (64 Mo) depuis le
echo zip MAME, puis en sort le programme decompresse (foo.bin).
echo.
py -3 build_crom.py tout
if errorlevel 1 goto fin
echo.
py -3 gzip_crom.py extraire
:fin
echo.
pause
