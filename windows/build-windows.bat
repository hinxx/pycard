@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Create it first with: py -3.11 -m venv .venv
    exit /b 1
)

if /I "%1"=="clean" (
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
)

.\.venv\Scripts\python.exe -m PyInstaller --clean pycard.spec
if errorlevel 1 exit /b %errorlevel%

echo.
echo Build complete:
echo   dist\pycard\pycard.exe
