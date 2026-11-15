# Start Slipday on Windows.  Usage: .\run.ps1 [-Port 8000]
# MALLOC_ARENA_MAX is a glibc (Linux) setting and does nothing on Windows; it is set here only so that
# every start command in the repository carries it.
param([int]$Port = 8000)
$env:MALLOC_ARENA_MAX = "2"
$py = if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") { "$PSScriptRoot\.venv\Scripts\python.exe" } else { "python" }
& $py -m uvicorn slipday.api:app --host 127.0.0.1 --port $Port
