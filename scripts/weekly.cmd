@echo off
rem Runs the weekly loop. Schedule with Windows Task Scheduler (see docs/SCHEDULING.md).
cd /d "%~dp0.."
claude -p "Use the content-agent subagent to run the weekly loop" >> scripts\weekly.log 2>&1
