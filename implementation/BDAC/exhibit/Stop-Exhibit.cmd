@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop-Exhibit.ps1" %*
if errorlevel 1 pause
