@echo off
chcp 65001 >nul
title Windows Security Policy Unlock Tool (For Experienced Users)
color 0A

:: Check for administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ============================================
    echo   Error: Please run this script as Administrator!
    echo ============================================
    echo.
    echo Right-click this file -^> Run as administrator
    echo.
    pause
    exit /b 1
)

:MENU
cls
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     Windows Security Policy Unlock Tool (For Experienced Users) ║
echo ╠════════════════════════════════════════════════════════════════╣
echo ║  ⚠️  Warning: This script modifies system security settings.   ║
echo ║     Make sure you understand the consequences!               ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo  Please select the open level:
echo.
echo  ─────────────────────────────────────────────────────────────────
echo  [1] Level 1: Conservative Mode (Recommended)
echo      - Turn off PowerShell execution policy restriction
echo      - Turn off SmartScreen filter
echo      - Turn off "File from other computer" warning
echo      - Turn off "Open File - Security Warning" popups
echo      ✅ Very low risk, purely removes "novice protection"
echo.
echo  ─────────────────────────────────────────────────────────────────
echo  [2] Level 2: Advanced Mode
echo      - Includes all content from Level 1
echo      - Lower UAC prompt level
echo      - Turn off Windows Defender real-time protection
echo      - Turn off Defender notifications and sample submission
echo      ⚠️ Moderate risk, third-party antivirus recommended
echo.
echo  ─────────────────────────────────────────────────────────────────
echo  [3] Level 3: Fully Open Mode
echo      - Includes all content from Level 2
echo      - Turn off Windows Firewall
echo      - Turn off Windows Update automatic updates
echo      ❌ Higher risk, only for users who know exactly what they are doing
echo.
echo  ─────────────────────────────────────────────────────────────────
echo  [4] View current system security status
echo  [5] Restore default settings
echo  [0] Exit
echo.
set /p choice=Please enter an option [0-5]: 

if "%choice%"=="1" goto LEVEL1
if "%choice%"=="2" goto LEVEL2
if "%choice%"=="3" goto LEVEL3
if "%choice%"=="4" goto STATUS
if "%choice%"=="5" goto RESTORE
if "%choice%"=="0" exit /b 0
goto MENU

:: ============================================================
:: Level 1: Conservative Mode
:: ============================================================
:LEVEL1
cls
echo ============================================
echo   Level 1: Conservative Mode - Starting configuration...
echo ============================================
echo.

echo [1/4] Setting PowerShell execution policy to Bypass...
powershell -Command "Set-ExecutionPolicy Bypass -Scope LocalMachine -Force" 2>nul
powershell -Command "Set-ExecutionPolicy Bypass -Scope CurrentUser -Force" 2>nul
echo       ✓ Done
echo.

echo [2/4] Turning off SmartScreen filter...
:: Turn off SmartScreen for Explorer
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v SmartScreenEnabled /t REG_SZ /d "Off" /f >nul 2>&1
:: Turn off SmartScreen for Edge/Apps
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableSmartScreen /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\AppHost" /v EnableWebContentEvaluation /t REG_DWORD /d 0 /f >nul 2>&1
echo       ✓ Done
echo.

echo [3/4] Turning off "File from other computer" warning (Zone.Identifier)...
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v SaveZoneInformation /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v SaveZoneInformation /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done
echo.

echo [4/4] Turning off "Open File - Security Warning" popup...
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Associations" /v LowRiskFileTypes /t REG_SZ /d ".exe;.bat;.cmd;.vbs;.js;.ps1;.msi;.reg;" /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Associations" /v LowRiskFileTypes /t REG_SZ /d ".exe;.bat;.cmd;.vbs;.js;.ps1;.msi;.reg;" /f >nul 2>&1
echo       ✓ Done
echo.

echo ============================================
echo   Level 1 configuration complete!
echo   It is recommended to restart the computer to ensure all changes take effect.
echo ============================================
echo.
pause
goto MENU

:: ============================================================
:: Level 2: Advanced Mode
:: ============================================================
:LEVEL2
cls
echo ============================================
echo   Level 2: Advanced Mode - Starting configuration...
echo ============================================
echo.
echo ⚠️  This level will turn off Windows Defender real-time protection
echo    Please ensure you have installed third-party antivirus software!
echo.
set /p confirm=Confirm to continue? (Y/N): 
if /i not "%confirm%"=="Y" goto MENU

echo.
echo [Step 1] Executing all Level 1 configurations first...
call :LEVEL1_SILENT
echo.

echo [Step 2] Lowering UAC prompt level...
:: Set UAC to lowest level (not completely off, keeps background protection)
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v EnableLUA /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done (UAC is still enabled, but no popups)
echo.

echo [Step 3] Turning off Windows Defender real-time protection...
:: Disable Defender via Registry
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableRealtimeMonitoring /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableBehaviorMonitoring /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableOnAccessProtection /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableScanOnRealtimeEnable /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done
echo.

echo [Step 4] Turning off Defender notifications and automatic sample submission...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /v SpynetReporting /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /v SubmitSamplesConsent /t REG_DWORD /d 2 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows Defender Security Center\Notifications" /v DisableNotifications /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done
echo.

echo ============================================
echo   Level 2 configuration complete!
echo   You must restart the computer for it to take full effect!
echo ============================================
echo.
pause
goto MENU

:: ============================================================
:: Level 3: Fully Open Mode
:: ============================================================
:LEVEL3
cls
echo ============================================
echo   Level 3: Fully Open Mode - Starting configuration...
echo ============================================
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║  ❌ Warning: This level turns off the firewall and auto-updates!║
echo ║     This will significantly lower system security!       ║
echo ║     Recommended only for special test environments or   ║
echo ║     if you fully understand the consequences!            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
set /p confirm1=Are you sure you want to continue? Enter YES to confirm: 
if /i not "%confirm1%"=="YES" goto MENU

echo.
echo [Step 1] Executing all Level 1 and Level 2 configurations first...
call :LEVEL1_SILENT
call :LEVEL2_SILENT
echo.

echo [Step 2] Turning off Windows Firewall...
netsh advfirewall set allprofiles state off >nul 2>&1
echo       ✓ Done (Firewall for all profiles is off)
echo.

echo [Step 3] Turning off Windows Update automatic updates...
:: Stop update services
net stop wuauserv >nul 2>&1
net stop UsoSvc >nul 2>&1
:: Disable update services
sc config wuauserv start= disabled >nul 2>&1
sc config UsoSvc start= disabled >nul 2>&1
:: Disable automatic updates via Registry
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v AUOptions /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done (Windows Update service is disabled)
echo.

echo ============================================
echo   Level 3 configuration complete!
echo   ⚠️  The system is now in a fully open state!
echo   You must restart the computer for it to take full effect!
echo ============================================
echo.
pause
goto MENU

:: ============================================================
:: View Current Status
:: ============================================================
:STATUS
cls
echo ============================================
echo   Current System Security Status
echo ============================================
echo.

echo [PowerShell Execution Policy]
powershell -Command "Get-ExecutionPolicy -List" 2>nul
echo.

echo [SmartScreen Status]
for /f "tokens=3" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v SmartScreenEnabled 2^>nul ^| find "SmartScreenEnabled"') do (
    echo   SmartScreen: %%a
)
echo.

echo [UAC Status]
for /f "tokens=3" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v EnableLUA 2^>nul ^| find "EnableLUA"') do (
    if "%%a"=="0x1" (echo   UAC: Enabled) else (echo   UAC: Disabled)
)
echo.

echo [Windows Defender Status]
powershell -Command "Get-MpComputerStatus | Select-Object -Property AntivirusEnabled,RealTimeProtectionEnabled" 2>nul
echo.

echo [Windows Firewall Status]
netsh advfirewall show allprofiles state 2>nul
echo.

echo [Windows Update Service Status]
sc query wuauserv | find "STATE" 2>nul
echo.

pause
goto MENU

:: ============================================================
:: Restore Default Settings
:: ============================================================
:RESTORE
cls
echo ============================================
echo   Restore Default Security Settings
echo ============================================
echo.
echo This will restore the following settings to Windows defaults:
echo   - PowerShell Execution Policy
echo   - SmartScreen
echo   - UAC
echo   - Windows Defender
echo   - Windows Firewall
echo   - Windows Update
echo.
set /p confirm=Confirm restore? (Y/N): 
if /i not "%confirm%"=="Y" goto MENU

echo.
echo [1/6] Restoring PowerShell execution policy...
powershell -Command "Set-ExecutionPolicy Restricted -Scope LocalMachine -Force" 2>nul
powershell -Command "Set-ExecutionPolicy Restricted -Scope CurrentUser -Force" 2>nul
echo       ✓ Done
echo.

echo [2/6] Restoring SmartScreen...
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableSmartScreen /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v SmartScreenEnabled /t REG_SZ /d "Warn" /f >nul 2>&1
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\AppHost" /v EnableWebContentEvaluation /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done
echo.

echo [3/6] Restoring UAC...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 5 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v PromptOnSecureDesktop /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v EnableLUA /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Done
echo.

echo [4/6] Restoring Windows Defender...
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender" /v DisableAntiSpyware /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /f >nul 2>&1
echo       ✓ Done
echo.

echo [5/6] Restoring Windows Firewall...
netsh advfirewall set allprofiles state on >nul 2>&1
echo       ✓ Done
echo.

echo [6/6] Restoring Windows Update...
sc config wuauserv start= demand >nul 2>&1
sc config UsoSvc start= demand >nul 2>&1
net start wuauserv >nul 2>&1
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v AUOptions /f >nul 2>&1
echo       ✓ Done
echo.

echo ============================================
echo   Restored to Windows default security settings!
echo   It is recommended to restart the computer to ensure all changes take effect.
echo ============================================
echo.
pause
goto MENU

:: ============================================================
:: Silent execution of Level 1 (Called by Level 2/3)
:: ============================================================
:LEVEL1_SILENT
powershell -Command "Set-ExecutionPolicy Bypass -Scope LocalMachine -Force" 2>nul
powershell -Command "Set-ExecutionPolicy Bypass -Scope CurrentUser -Force" 2>nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v SmartScreenEnabled /t REG_SZ /d "Off" /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableSmartScreen /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\AppHost" /v EnableWebContentEvaluation /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v SaveZoneInformation /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v SaveZoneInformation /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Associations" /v LowRiskFileTypes /t REG_SZ /d ".exe;.bat;.cmd;.vbs;.js;.ps1;.msi;.reg;" /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Associations" /v LowRiskFileTypes /t REG_SZ /d ".exe;.bat;.cmd;.vbs;.js;.ps1;.msi;.reg;" /f >nul 2>&1
echo       ✓ Level 1 configuration complete
goto :eof

:: ============================================================
:: Silent execution of Level 2 (Called by Level 3)
:: ============================================================
:LEVEL2_SILENT
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender" /v DisableAntiSpyware /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableRealtimeMonitoring /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableBehaviorMonitoring /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableOnAccessProtection /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection" /v DisableScanOnRealtimeEnable /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /v SpynetReporting /t REG_DWORD /d 0 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender\Spynet" /v SubmitSamplesConsent /t REG_DWORD /d 2 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows Defender Security Center\Notifications" /v DisableNotifications /t REG_DWORD /d 1 /f >nul 2>&1
echo       ✓ Level 2 configuration complete
goto :eof
