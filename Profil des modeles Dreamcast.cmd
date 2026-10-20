@echo off
cd /d "%~dp0"
title FV2 - Profil des modeles Dreamcast
echo.
echo Profil des 16 premieres entrees de MDL_DAT.AFS, puis un nuage de points
echo par entree dans nuages\. Demande le lanceur "Ouvrir le disque Dreamcast".
echo.
py -3 afs.py profil dreamcast\MDL_DAT.AFS 16
if errorlevel 1 goto fin
echo.
py -3 nuage.py dreamcast\MDL_DAT.AFS 0 15
:fin
echo.
pause
