param(
    [string]$Python = "python",
    [string]$Name = "OrderEntryBot"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt pyinstaller

Write-Host "Building executable..."
& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --name $Name `
  --windowed `
  --add-data "docs;docs" `
  run_app.py

Write-Host "Build complete: dist/$Name"
