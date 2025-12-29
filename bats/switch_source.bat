@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ==============================================================================
:: Python Package Source Switcher (Windows Version)
:: Supports: pip, conda
:: Mirrors: Tsinghua, USTC, Tencent, Aliyun, Douban
:: ==============================================================================

title Python Package Source Switcher

:: Config Files
set "CONDARC=%USERPROFILE%\.condarc"
set "PIP_CONF=%APPDATA%\pip\pip.ini"

:: ------------------------------------------------------------------------------
:: Main Menu
:: ------------------------------------------------------------------------------
:main_menu
cls
echo.
echo ========================================
echo    Windows Python Source Switcher Tool
echo ========================================
echo.
echo  1) Configure pip
echo  2) Configure conda
echo  3) View current configuration
echo  0) Exit
echo.
set /p "choice=Enter choice [0-3]: "

if "%choice%"=="1" goto menu_pip
if "%choice%"=="2" goto menu_conda
if "%choice%"=="3" goto view_config
if "%choice%"=="0" goto exit_script
echo [ERR] Invalid choice
timeout /t 2 >nul
goto main_menu

:: ------------------------------------------------------------------------------
:: PIP Menu
:: ------------------------------------------------------------------------------
:menu_pip
cls
echo.
echo === Configure pip Source ===
echo.
echo  1) Tsinghua (China) [Recommended]
echo  2) USTC (China)
echo  3) Aliyun (China)
echo  4) Tencent (China)
echo  5) Douban (China)
echo  6) Restore Default (Official PyPI)
echo  0) Return to Main Menu
echo.
set /p "pip_choice=Enter choice [0-6]: "

if "%pip_choice%"=="1" (
    set "pip_url=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
    set "pip_name=Tsinghua"
    goto set_pip
)
if "%pip_choice%"=="2" (
    set "pip_url=https://mirrors.ustc.edu.cn/pypi/simple"
    set "pip_name=USTC"
    goto set_pip
)
if "%pip_choice%"=="3" (
    set "pip_url=https://mirrors.aliyun.com/pypi/simple/"
    set "pip_name=Aliyun"
    goto set_pip
)
if "%pip_choice%"=="4" (
    set "pip_url=https://mirrors.cloud.tencent.com/pypi/simple"
    set "pip_name=Tencent"
    goto set_pip
)
if "%pip_choice%"=="5" (
    set "pip_url=https://pypi.douban.com/simple"
    set "pip_name=Douban"
    goto set_pip
)
if "%pip_choice%"=="6" goto restore_pip
if "%pip_choice%"=="0" goto main_menu

echo [ERR] Invalid choice
timeout /t 2 >nul
goto menu_pip

:set_pip
:: Check if pip exists
where pip >nul 2>&1
if errorlevel 1 (
    echo [ERR] pip not found. Please install Python first.
    pause
    goto menu_pip
)

echo.
echo [INFO] Setting pip source to: %pip_name%

:: Backup existing config
if exist "%PIP_CONF%" (
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set "datestamp=%%c%%a%%b"
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "timestamp=%%a%%b"
    copy "%PIP_CONF%" "%PIP_CONF%.bak_!datestamp!_!timestamp!" >nul 2>&1
    echo [INFO] Backed up existing pip.ini
)

:: Create pip config directory if not exists
if not exist "%APPDATA%\pip" mkdir "%APPDATA%\pip"

:: Write new config
(
    echo [global]
    echo index-url = %pip_url%
    echo trusted-host = %pip_url:~8%
) > "%PIP_CONF%"

:: Also set via pip config command for reliability
pip config set global.index-url "%pip_url%" >nul 2>&1

echo [INFO] pip source updated successfully!
echo.
echo Current pip config:
pip config list
echo.
pause
goto menu_pip

:restore_pip
where pip >nul 2>&1
if errorlevel 1 (
    echo [ERR] pip not found.
    pause
    goto menu_pip
)

echo.
echo [INFO] Restoring pip to default source...
pip config unset global.index-url >nul 2>&1
pip config unset global.trusted-host >nul 2>&1

if exist "%PIP_CONF%" del "%PIP_CONF%" >nul 2>&1

echo [INFO] pip restored to official PyPI source.
echo.
pause
goto menu_pip

:: ------------------------------------------------------------------------------
:: Conda Menu
:: ------------------------------------------------------------------------------
:menu_conda
cls
:: Check if conda exists
where conda >nul 2>&1
if errorlevel 1 (
    echo [ERR] Conda is not installed or not in PATH.
    echo Please install Anaconda/Miniconda first.
    pause
    goto main_menu
)

echo.
echo === Configure Conda Source ===
echo.
echo  1) Tsinghua (China) [Includes pytorch/conda-forge]
echo  2) USTC (China) [Includes bioconda/conda-forge]
echo  3) Restore Default (Official)
echo  0) Return to Main Menu
echo.
set /p "conda_choice=Enter choice [0-3]: "

if "%conda_choice%"=="1" goto conda_tsinghua
if "%conda_choice%"=="2" goto conda_ustc
if "%conda_choice%"=="3" goto conda_default
if "%conda_choice%"=="0" goto main_menu

echo [ERR] Invalid choice
timeout /t 2 >nul
goto menu_conda

:conda_tsinghua
echo.
echo [INFO] Setting Conda source to Tsinghua...

:: Backup existing config
call :backup_condarc

:: Write Tsinghua config
(
    echo channels:
    echo   - defaults
    echo show_channel_urls: true
    echo default_channels:
    echo   - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
    echo   - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
    echo   - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
    echo custom_channels:
    echo   conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
    echo   msys2: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
    echo   bioconda: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
    echo   menpo: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
    echo   pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
    echo   pytorch-lts: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
    echo   simpleitk: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
) > "%CONDARC%"

echo [INFO] Tsinghua mirror configured successfully!
call :show_conda_config
goto menu_conda

:conda_ustc
echo.
echo [INFO] Setting Conda source to USTC...

:: Backup existing config
call :backup_condarc

:: Write USTC config
(
    echo channels:
    echo   - defaults
    echo show_channel_urls: true
    echo default_channels:
    echo   - https://mirrors.ustc.edu.cn/anaconda/pkgs/main
    echo   - https://mirrors.ustc.edu.cn/anaconda/pkgs/r
    echo custom_channels:
    echo   conda-forge: https://mirrors.ustc.edu.cn/anaconda/cloud
    echo   bioconda: https://mirrors.ustc.edu.cn/anaconda/cloud
    echo   msys2: https://mirrors.ustc.edu.cn/anaconda/cloud
    echo   pytorch: https://mirrors.ustc.edu.cn/anaconda/cloud
) > "%CONDARC%"

echo [INFO] USTC mirror configured successfully!
call :show_conda_config
goto menu_conda

:conda_default
echo.
echo [INFO] Restoring Conda to default source...

:: Backup existing config
call :backup_condarc

:: Remove custom configs
conda config --remove-key channels >nul 2>&1
conda config --remove-key default_channels >nul 2>&1
conda config --remove-key custom_channels >nul 2>&1

if exist "%CONDARC%" del "%CONDARC%" >nul 2>&1

echo [INFO] Conda restored to official defaults.
echo.
pause
goto menu_conda

:backup_condarc
if exist "%CONDARC%" (
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set "datestamp=%%c%%a%%b"
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "timestamp=%%a%%b"
    copy "%CONDARC%" "%CONDARC%.bak_!datestamp!_!timestamp!" >nul 2>&1
    echo [INFO] Backed up existing .condarc
)
goto :eof

:show_conda_config
echo.
echo Current Conda config:
echo ----------------------------------------
if exist "%CONDARC%" (
    type "%CONDARC%"
) else (
    echo [No .condarc file found]
)
echo ----------------------------------------
echo.
echo Note: Run 'conda clean -i' if you encounter errors after switching.
echo.
pause
goto :eof

:: ------------------------------------------------------------------------------
:: View Current Config
:: ------------------------------------------------------------------------------
:view_config
cls
echo.
echo === Current Configuration ===
echo.

echo --- pip Configuration ---
where pip >nul 2>&1
if errorlevel 1 (
    echo pip is not installed.
) else (
    pip config list 2>nul
    if errorlevel 1 echo [Using default PyPI source]
)

echo.
echo --- Conda Configuration ---
where conda >nul 2>&1
if errorlevel 1 (
    echo Conda is not installed.
) else (
    if exist "%CONDARC%" (
        type "%CONDARC%"
    ) else (
        echo [Using default Conda channels]
    )
)

echo.
echo --- Config File Locations ---
echo pip.ini:  %PIP_CONF%
echo .condarc: %CONDARC%
echo.
pause
goto main_menu

:: ------------------------------------------------------------------------------
:: Exit
:: ------------------------------------------------------------------------------
:exit_script
echo.
echo [INFO] Exiting...
timeout /t 1 >nul
exit /b 0

