@echo off
cd /d "%~dp0"
py report_generator.py %*
if %ERRORLEVEL% NEQ 0 pause
