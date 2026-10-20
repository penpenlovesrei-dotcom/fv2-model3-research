@echo off
cd /d "%~dp0"
title FV2 - Ouvrir le disque Dreamcast
echo.
echo Liste le .cdi puis en sort 1ST_READ.BIN et les archives AFS dans dreamcast\
echo (le bourrage de selfboot de 300 Mo est saute).
echo.
py -3 cdi.py lister
if errorlevel 1 goto fin
echo.
py -3 cdi.py sortir dreamcast
:fin
echo.
pause
