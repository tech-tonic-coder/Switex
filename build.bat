@echo off
setlocal EnableDelayedExpansion
set "DIR=%~dp0"
title Switex — Build

echo.
echo =========================================
echo   Switex — Build Switex.exe
echo =========================================
echo.
echo This will compile Switex into a single Switex.exe
echo that includes Python and all dependencies.
echo The final file will be in:  %DIR%dist\Switex.exe
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
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
    echo         Install from https://www.python.org/downloads/
    pause & exit /b 1
)
echo [OK] Python found  (%PYTHON%)

:: ── Install / upgrade required packages ──────────────────────────────────────
echo.
echo [INSTALL] Installing required packages...
%PYTHON% -m pip install --upgrade pip >nul
%PYTHON% -m pip install pynput pyperclip pystray Pillow pyinstaller

if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    echo         Try running this script as Administrator.
    pause & exit /b 1
)
echo [OK] All packages installed.

:: ── Generate a simple icon file ───────────────────────────────────────────────
echo.
echo [BUILD] Generating icon...
%PYTHON% -c "
from PIL import Image, ImageDraw, ImageFont
import os

size = 256
img  = Image.new('RGBA', (size, size), (0,0,0,0))
draw = ImageDraw.Draw(img)

# Green circle background
draw.ellipse([4, 4, size-4, size-4], fill=(34, 160, 54, 255))

# White 'S' letter
try:
    font = ImageFont.truetype('arialbd.ttf', 160)
except:
    try:
        font = ImageFont.truetype('arial.ttf', 160)
    except:
        font = ImageFont.load_default()

text = 'S'
bbox = draw.textbbox((0,0), text, font=font)
tw = bbox[2]-bbox[0]
th = bbox[3]-bbox[1]
draw.text(((size-tw)/2 - bbox[0], (size-th)/2 - bbox[1]),
          text, font=font, fill=(255,255,255,255))

# Save as ICO with multiple sizes
icon_path = os.path.join(r'%DIR%', 'switex_icon.ico')
img_16  = img.resize((16,16),   Image.LANCZOS)
img_32  = img.resize((32,32),   Image.LANCZOS)
img_48  = img.resize((48,48),   Image.LANCZOS)
img_64  = img.resize((64,64),   Image.LANCZOS)
img_128 = img.resize((128,128), Image.LANCZOS)
img_256 = img.resize((256,256), Image.LANCZOS)
img_256.save(icon_path, format='ICO',
             sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(f'Icon saved to: {icon_path}')
"

if errorlevel 1 (
    echo [WARN] Icon generation failed. Building without custom icon.
    set "ICON_OPT="
) else (
    set "ICON_OPT=--icon=%DIR%switex_icon.ico"
    echo [OK] Icon generated.
)

:: ── Run PyInstaller ───────────────────────────────────────────────────────────
echo.
echo [BUILD] Compiling Switex.exe with PyInstaller...
echo         This may take a minute...
echo.

%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name Switex ^
    --add-data "%DIR%switex.py;." ^
    %ICON_OPT% ^
    --hidden-import pynput.keyboard ^
    --hidden-import pynput.mouse ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._imaging ^
    --hidden-import pyperclip ^
    --clean ^
    --noconfirm ^
    "%DIR%switex_tray.py"

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed.
    echo         Check the output above for details.
    pause & exit /b 1
)

:: ── Copy output ───────────────────────────────────────────────────────────────
echo.
if exist "%DIR%dist\Switex.exe" (
    copy /Y "%DIR%dist\Switex.exe" "%DIR%Switex.exe" >nul
    echo =========================================
    echo   BUILD SUCCESSFUL!
    echo.
    echo   Switex.exe is ready:
    echo   %DIR%Switex.exe
    echo.
    echo   Double-click Switex.exe to launch.
    echo   It will appear in your system tray.
    echo.
    echo   Right-click the tray icon for:
    echo     Start / Stop / Restart / Status
    echo     Open Log / Exit
    echo =========================================
) else (
    echo [ERROR] Switex.exe not found in dist\ folder.
    echo         Build may have failed silently.
)

echo.
pause
