# Script to fix Python setup on Windows
# This script helps you set up Python properly and recreate the virtual environment

Write-Host "=== Python Setup Fix for Windows ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "Checking for Python installation..." -ForegroundColor Yellow
$pythonPaths = @(
    "C:\Python*\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
    "$env:ProgramFiles\Python*\python.exe",
    "$env:ProgramFiles(x86)\Python*\python.exe"
)

$foundPython = $null
foreach ($path in $pythonPaths) {
    $matches = Get-ChildItem -Path $path -ErrorAction SilentlyContinue
    if ($matches) {
        $foundPython = $matches[0].FullName
        break
    }
}

if ($foundPython) {
    Write-Host "Found Python at: $foundPython" -ForegroundColor Green
    $pythonVersion = & $foundPython --version 2>&1
    Write-Host "Version: $pythonVersion" -ForegroundColor Green
    Write-Host ""
    Write-Host "Python is installed! Now let's recreate the virtual environment..." -ForegroundColor Green
    Write-Host ""
    
    # Remove old venv
    if (Test-Path "venvs\w_venv") {
        Write-Host "Removing old macOS virtual environment..." -ForegroundColor Yellow
        Remove-Item -Path "venvs\w_venv" -Recurse -Force
    }
    
    # Create new venv
    Write-Host "Creating new Windows virtual environment..." -ForegroundColor Yellow
    & $foundPython -m venv venvs\w_venv
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Virtual environment created successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "To activate it, run:" -ForegroundColor Cyan
        Write-Host "  . .\w_venv.ps1" -ForegroundColor White
        Write-Host ""
        Write-Host "Or manually:" -ForegroundColor Cyan
        Write-Host "  . .\venvs\w_venv\bin\Activate.ps1" -ForegroundColor White
        Write-Host ""
        Write-Host "Then install dependencies:" -ForegroundColor Cyan
        Write-Host "  pip install -r requirements.txt" -ForegroundColor White
    } else {
        Write-Host "Failed to create virtual environment. Please check Python installation." -ForegroundColor Red
    }
} else {
    Write-Host "Python is not installed or not found in standard locations." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python for Windows:" -ForegroundColor Yellow
    Write-Host "1. Download Python from: https://www.python.org/downloads/" -ForegroundColor Cyan
    Write-Host "2. During installation, check 'Add Python to PATH'" -ForegroundColor Cyan
    Write-Host "3. After installation, restart PowerShell and run this script again" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or use winget to install:" -ForegroundColor Yellow
    Write-Host "  winget install Python.Python.3.13" -ForegroundColor Cyan
}

