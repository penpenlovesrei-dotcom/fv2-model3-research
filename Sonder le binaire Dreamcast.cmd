@echo off
cd /d "%~dp0"
title FV2 - Sonder le binaire Dreamcast
echo.
echo Sonde dreamcast\1ST_READ.BIN par balayage d'octets, sans Ghidra.
echo Demande le binaire (lanceur "Ouvrir le disque Dreamcast").
echo.
echo --- le repartiteur de ressources, 0x8C047C9E ---
py -3 desas_sh4.py 0x8C047C9E 30
echo.
echo --- la branche du genre 0xF0, la musique ---
py -3 desas_sh4.py 0x8C047E54 10
echo.
echo --- l'enregistrement des cinq partitions ADXF, 0x8C028988 ---
py -3 desas_sh4.py 0x8C028988 24
echo.
echo --- qui charge la table des archives et l'enumeration des musiques ---
py -3 tables_sh4.py charge 0x8C0CD278 0x8C0CD28C 0x8C112420
echo.
echo --- les tables de saut calculees du binaire entier ---
py -3 tables_sh4.py braf
echo.
pause
