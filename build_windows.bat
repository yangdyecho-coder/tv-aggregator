@echo off
chcp 65001 > nul
title 美剧信息聚合器 — 构建 Windows 安装包

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   美剧信息聚合器 — Windows 安装包构建    ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── 1. 检查 Python ────────────────────────────────────────────────────────
echo [步骤 1/5] 检查 Python 环境...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [错误] 未检测到 Python！
    echo  请先从以下地址下载并安装 Python 3.11+（勾选 Add to PATH）:
    echo  https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  已检测到 Python %PY_VER%

:: ── 2. 安装依赖 ───────────────────────────────────────────────────────────
echo.
echo [步骤 2/5] 安装 Python 依赖...
pip install pyinstaller requests Pillow --quiet --upgrade
if %errorlevel% neq 0 (
    echo  [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)
echo  依赖安装完成。

:: ── 3. 生成图标 ───────────────────────────────────────────────────────────
echo.
echo [步骤 3/5] 生成应用图标...
python create_icon.py
if not exist icon.ico (
    echo  [警告] icon.ico 未生成，将使用 PyInstaller 默认图标。
)

:: ── 4. PyInstaller 打包 ───────────────────────────────────────────────────
echo.
echo [步骤 4/5] PyInstaller 打包为单文件 exe（首次较慢，请耐心等待）...
pyinstaller build.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo  [错误] PyInstaller 打包失败，请查看上方错误信息。
    pause
    exit /b 1
)
if not exist "dist\TVAggregator.exe" (
    echo  [错误] dist\TVAggregator.exe 未生成。
    pause
    exit /b 1
)
echo  exe 打包成功 → dist\TVAggregator.exe

:: ── 5. Inno Setup 制作安装包 ──────────────────────────────────────────────
echo.
echo [步骤 5/5] 制作 Windows 安装包（Inno Setup）...

set "ISCC_PATH="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_PATH (
    echo.
    echo  [提示] 未找到 Inno Setup 6，跳过安装包制作。
    echo  ─────────────────────────────────────────────
    echo  可直接使用 exe：dist\TVAggregator.exe
    echo  如需制作安装程序，请安装 Inno Setup 6 后重新运行：
    echo  https://jrsoftware.org/isdl.php
    echo  ─────────────────────────────────────────────
    goto :done
)

if not exist Output mkdir Output
"%ISCC_PATH%" installer.iss
if %errorlevel% neq 0 (
    echo  [错误] Inno Setup 打包失败，请查看上方错误信息。
    echo  exe 仍可在 dist\TVAggregator.exe 使用。
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  构建成功！                                              ║
echo  ║  安装包位于: Output\TVAggregator_Setup_v1.0.0.exe        ║
echo  ╚══════════════════════════════════════════════════════════╝

:done
echo.
pause
