# Quick activation script for the trading-bot virtual environment
# Usage: . .\activate_venv.ps1

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
. .\venvs\w_venv\bin\Activate.ps1

Write-Host "Virtual environment activated! You can now run your Python scripts." -ForegroundColor Green

