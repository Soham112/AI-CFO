# Daily DICFO run for Windows. Schedule it with Task Scheduler (see docs/INSTALL.md).
param([string]$Profile = "dad")
Set-Location (Join-Path $PSScriptRoot "..")
& .\.venv\Scripts\python.exe -m dicfo daily --profile $Profile --notify "email,whatsapp"
