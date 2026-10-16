# Build the Ultron desktop .exe.
# Run from the project root in an activated venv:
#   .\.venv\Scripts\Activate.ps1
#   .\build_exe.ps1
#
# Output: dist\Ultron\Ultron.exe (plus the supporting folder).

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Installing build deps..." -ForegroundColor Cyan
pip install -q -r requirements-dev.txt

Write-Host "[2/4] Cleaning old build..." -ForegroundColor Cyan
if (Test-Path "build")  { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")   { Remove-Item -Recurse -Force "dist" }

Write-Host "[3/4] Running PyInstaller (this takes 3-8 min)..." -ForegroundColor Cyan
pyinstaller ultron.spec --clean --noconfirm

Write-Host "[4/4] Done." -ForegroundColor Green
Write-Host ""
Write-Host "Built executable: dist\Ultron\Ultron.exe"
Write-Host "Zip up the whole 'dist\Ultron\' folder to distribute."
