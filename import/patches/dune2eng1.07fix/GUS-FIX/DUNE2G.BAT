@echo off
if not "%ultrasnd%"=="" %ultradir%\ultramid -f -q
if not "%ultrasnd%"=="" %ultradir%\ultramid -16 -m115 -q
if errorlevel 1 goto done
dune2.exe
echo.
if not "%ultrasnd%"=="" %ultradir%\ultramid -f -q
:done
