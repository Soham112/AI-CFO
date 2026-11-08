# Windows: Task Scheduler -> Create Task -> Trigger "At log on" -> Action: powershell.exe
#   -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\<you>\Documents\AI-CFO\scripts\autostart\telegram-listener.ps1"
Set-Location (Join-Path $PSScriptRoot "..\..")
& .\.venv\Scripts\python.exe -m dicfo telegram-listen --profile dad
