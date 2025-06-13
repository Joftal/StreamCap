@echo off
chcp 65001 >nul
color 0A

echo =====================================
echo    StreamCap Build Tool
echo =====================================
echo.
echo Select build mode:
echo 1: GUI mode (no console window)
echo 2: Console mode (with console window)
echo.
set /p mode="Enter option (1/2): "

if "%mode%"=="1" (
    set "spec_file=main_gui.spec"
    set "mode_name=GUI mode"
) else if "%mode%"=="2" (
    set "spec_file=main_console.spec"
    set "mode_name=Console mode"
) else (
    echo Invalid option, using Console mode
    set "spec_file=main_console.spec"
    set "mode_name=Console mode"
    timeout /t 3 >nul
)

echo.
echo =====================================
echo    Version Update
echo =====================================
echo Current version in config\version.json:

REM 显示当前目录和文件信息
echo Current directory: %CD%
echo Checking version.json...
if exist config\version.json (
    echo File exists
    type config\version.json
) else (
    echo File not found
)

REM 尝试读取版本号
echo.
echo Attempting to read version...
python -c "import json, os; print('Python working directory:', os.getcwd()); print('Looking for file:', os.path.abspath('config/version.json')); f=open('config/version.json', 'r', encoding='utf-8'); data=json.load(f); print('Version:', data['version_updates'][0]['version']); f.close()" 2>nul
if errorlevel 1 (
    echo Failed to read version.json
    echo Please check if the file exists and is valid
    pause
    exit /b 1
)
echo.
echo Do you want to update the version?
echo 1: Yes, update version
echo 2: No, keep current version
echo.

:version_choice
set /p update_version="Enter option (1/2): "
if "%update_version%"=="1" goto update_version
if "%update_version%"=="2" goto continue_build
echo Invalid option, please try again
goto version_choice

:update_version
echo.
echo Enter new version (e.g., 1.0.2):
set /p new_version="Version: "

echo [Step 0] Updating version...
python -c "import json, os; print('Python working directory:', os.getcwd()); print('Looking for file:', os.path.abspath('config/version.json')); f=open('config/version.json', 'r', encoding='utf-8'); data=json.load(f); data['version']='%new_version%'; data['version_updates'][0]['version']='%new_version%'; f=open('config/version.json', 'w', encoding='utf-8'); json.dump(data, f, indent=2, ensure_ascii=False); f.close()" 2>nul
if errorlevel 1 (
    echo Failed to update version.json
    echo Please check if the file exists and is valid
    pause
    exit /b 1
)
echo Version updated to: %new_version%
echo.

:continue_build
echo =====================================
echo    Building StreamCap...
echo    Mode: %mode_name%
echo =====================================

REM Check icon file
if not exist assets\icon.ico (
    echo [Warning] Icon file not found: assets\icon.ico
    echo Using default icon
    timeout /t 3 >nul
)

REM Install dependencies
echo [Step 1] Installing dependencies...
pip install -r requirements-win.txt
if errorlevel 1 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

REM Clean previous build
echo [Step 2] Cleaning build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build with selected spec
echo [Step 3] Building...
echo - Using %mode_name%
echo - Using custom icon
pyinstaller "%spec_file%"
if errorlevel 1 (
    echo Failed to build application
    pause
    exit /b 1
)

REM Copy required folders
echo [Step 4] Copying folders...
xcopy /E /I /Y assets dist\StreamCap\assets
xcopy /E /I /Y config dist\StreamCap\config
xcopy /E /I /Y downloads dist\StreamCap\downloads
xcopy /E /I /Y locales dist\StreamCap\locales
xcopy /E /I /Y logs dist\StreamCap\logs

echo =====================================
echo    Build complete! 
echo    Program is in dist/StreamCap directory
echo    Mode: %mode_name%
if "%mode%"=="1" echo    Memory cleanup logs: logs/memory_clean.log
echo =====================================
pause 