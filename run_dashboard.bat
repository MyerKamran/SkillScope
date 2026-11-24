@echo off
title SkillScope Studio Launcher
cd /d "%~dp0"
echo Starting SkillScope Studio on http://127.0.0.1:3000 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_studio.ps1"
pause
