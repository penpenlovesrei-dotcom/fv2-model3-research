@echo off
cd /d "%~dp0"
title FV2 - Table des decors
echo.
echo Compare la table de decors des deux versions. Demande foo.bin (lanceur
echo "Reconstruire les ROM arcade") et dreamcast\1ST_READ.BIN (lanceur
echo "Ouvrir le disque Dreamcast").
echo.
py -3 decors.py comparer
echo.
echo --- detail cote arcade ---
py -3 decors.py arcade
echo.
pause
