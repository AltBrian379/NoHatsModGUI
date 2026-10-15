# Builds dist\NoHatsModGUI.exe. Drop the nhcustom2_windows folder next to it to use it.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python -m pip install -q -r requirements.txt
.\.venv\Scripts\python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed `
    --name NoHatsModGUI `
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf `
    main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Built dist\NoHatsModGUI.exe"
