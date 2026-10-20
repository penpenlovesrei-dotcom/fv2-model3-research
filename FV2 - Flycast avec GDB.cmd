@echo off
cd /d "%~dp0"
title FV2 - Flycast avec serveur GDB
echo.
echo Lance Fighting Vipers 2 dans Flycast, serveur GDB sur le port 3263.
echo Le dynarec est desactive : le jeu sera lent, c'est normal et necessaire
echo pour que les points d'arret materiels soient honores.
echo.
echo Une fois le jeu lance, dans une autre fenetre :
echo    py -3 gdb_flycast.py etat
echo    py -3 gdb_flycast.py guette 0x8C113314 4
echo.
start "" "C:\Users\frede\Documents\Dreamcast\flycast.exe" "C:\Users\frede\Documents\Dreamcast\Games\Fighting Vipers 2.cdi"
