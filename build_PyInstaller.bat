@echo off
setlocal EnableDelayedExpansion
set "DIR=%~dp0"
title Switex -- Build

if "%~1"=="__child__" goto :main_start
cmd /k "%~f0" __child__
exit /b

:main_start
echo.
echo =========================================
echo   Switex -- Build Switex.exe
echo =========================================

echo [CHECK] Looking for Python 3.7+...
set "PYTHON="
for %%C in (python python3 py) do (
    if not defined PYTHON (
        %%C --version >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=2" %%V in ('%%C --version 2^>^&1') do (
                for /f "tokens=1,2 delims=." %%A in ("%%V") do (
                    if %%A GEQ 3 if %%B GEQ 7 set "PYTHON=%%C"
                )
            )
        )
    )
)
if not defined PYTHON (
    echo [ERROR] Python 3.7+ not found.
    pause & exit /b 1
)
echo [OK] Python found (%PYTHON%)

echo [INSTALL] Installing packages...
%PYTHON% -m pip install --upgrade pip >nul
%PYTHON% -m pip install pynput pyperclip pystray Pillow pyinstaller windows-toasts
if errorlevel 1 ( echo [ERROR] Install failed. & pause & exit /b 1 )

:: ── Download UPX ──────────────────────────────────────────────────────────────
echo.
echo [UPX] Checking for UPX...
set "UPX_DIR=%DIR%upx"
set "UPX_OPT="

if exist "%UPX_DIR%\upx.exe" (
    echo [OK] UPX already present.
    set "UPX_OPT=--upx-dir=%UPX_DIR%"
    goto :upx_done
)

echo [UPX] Downloading UPX...
set "UPX_ZIP=%TEMP%\upx.zip"
set "UPX_URL=https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip"

powershell -NoProfile -Command "Invoke-WebRequest -Uri '%UPX_URL%' -OutFile '%UPX_ZIP%' -UseBasicParsing" >nul 2>&1
if errorlevel 1 (
    echo [WARN] UPX download failed. Building without compression.
    goto :upx_done
)

mkdir "%UPX_DIR%" >nul 2>&1
powershell -NoProfile -Command "Expand-Archive -Path '%UPX_ZIP%' -DestinationPath '%TEMP%\upx_extracted' -Force" >nul 2>&1
for /r "%TEMP%\upx_extracted" %%F in (upx.exe) do copy /Y "%%F" "%UPX_DIR%\upx.exe" >nul
del "%UPX_ZIP%" >nul 2>&1

if exist "%UPX_DIR%\upx.exe" (
    echo [OK] UPX downloaded successfully.
    set "UPX_OPT=--upx-dir=%UPX_DIR%"
) else (
    echo [WARN] UPX extraction failed. Building without compression.
)

:upx_done

:: ── Icon ──────────────────────────────────────────────────────────────────────
set "ICON_OPT="
set "ICON_DATA_OPT="
if exist "%DIR%switex.ico" (
    set "ICON_OPT=--icon=%DIR%switex.ico"
    set "ICON_DATA_OPT=--add-data "%DIR%switex.ico;.""
)

:: ── Build ─────────────────────────────────────────────────────────────────────
echo.
echo [BUILD] Compiling...

%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name Switex ^
    --add-data "%DIR%switex.py;." ^
    %ICON_DATA_OPT% ^
    %ICON_OPT% ^
    %UPX_OPT% ^
    --upx-exclude=vcruntime140.dll ^
    --upx-exclude=python3*.dll ^
    --exclude-module tkinter ^
    --exclude-module email ^
    --exclude-module html ^
    --exclude-module http ^
    --exclude-module urllib ^
    --exclude-module xml ^
    --exclude-module xmlrpc ^
    --exclude-module ftplib ^
    --exclude-module imaplib ^
    --exclude-module smtplib ^
    --exclude-module turtle ^
    --exclude-module unittest ^
    --exclude-module doctest ^
    --exclude-module pydoc ^
    --exclude-module difflib ^
    --exclude-module PIL.ImageTk ^
    --exclude-module PIL.ImageQt ^
    --hidden-import pynput.keyboard ^
    --hidden-import pynput.mouse ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._imaging ^
    --hidden-import pyperclip ^
    --hidden-import windows_toasts ^
    --hidden-import winrt.windows.ui.notifications ^
    --hidden-import winrt.windows.data.xml.dom ^
    --clean ^
    --noconfirm ^
    "%DIR%switex_tray.py"

if errorlevel 1 ( echo [ERROR] Build failed. & pause & exit /b 1 )

if exist "%DIR%dist\Switex.exe" (
    copy /Y "%DIR%dist\Switex.exe" "%DIR%Switex.exe" >nul
    echo.
    echo =========================================
    echo   BUILD SUCCESSFUL
    echo   %DIR%Switex.exe
    echo =========================================
) else (
    echo [ERROR] Output not found.
)

pause