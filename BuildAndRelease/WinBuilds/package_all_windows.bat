@echo off
REM ============================================================================
REM Package all Windows apps for installer
REM ============================================================================
REM This script collects the built apps into dist_all/bin/ for Inno Setup.
REM
REM Each app is a PyInstaller folder build: dist\<app>\<app>.exe plus its own
REM contents folder (idt-lib, imagedescriber-lib, idtchat-lib). The whole
REM folder is copied, so all three exes and their libraries sit side by side
REM in bin\ without overwriting each other.
REM
REM CI runs this again after signing the exes in each app's dist folder, so
REM the signed copies replace the unsigned ones builditall_wx.bat put here.
REM
REM Prerequisites:
REM   - Run builditall_wx.bat first to build all executables
REM ============================================================================

echo ================================================
echo Packaging Windows Executables
echo ================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Start bin\ empty, so no library from an earlier build is shipped.
if exist "dist_all\bin" rmdir /S /Q "dist_all\bin"
mkdir "dist_all\bin"

if not exist "..\..\idt\dist\idt\idt.exe" goto :missing_idt
if not exist "..\..\idt\dist\idt\idt-lib" goto :missing_idt
echo Copying idt...
xcopy /E /I /Q /Y "..\..\idt\dist\idt" "dist_all\bin"
if errorlevel 1 goto :copy_failed

if not exist "..\..\imagedescriber\dist\ImageDescriber\ImageDescriber.exe" goto :missing_describer
if not exist "..\..\imagedescriber\dist\ImageDescriber\imagedescriber-lib" goto :missing_describer
echo Copying ImageDescriber...
xcopy /E /I /Q /Y "..\..\imagedescriber\dist\ImageDescriber" "dist_all\bin"
if errorlevel 1 goto :copy_failed

REM Required: installer.iss lists it under [Files], so Inno Setup fails the
REM whole installer build if it is absent from dist_all\bin.
if not exist "..\..\chatapp\dist\IDTChat\IDTChat.exe" goto :missing_chat
if not exist "..\..\chatapp\dist\IDTChat\idtchat-lib" goto :missing_chat
echo Copying IDTChat...
xcopy /E /I /Q /Y "..\..\chatapp\dist\IDTChat" "dist_all\bin"
if errorlevel 1 goto :copy_failed

echo.
echo ================================================
echo Packaging complete!
echo ================================================
echo.
echo Files copied to: dist_all\bin\
dir dist_all\bin\
echo.
exit /b 0

:missing_idt
echo ERROR: idt build not found at ..\..\idt\dist\idt\ (idt.exe and idt-lib)
echo Run builditall_wx.bat first
exit /b 1

:missing_describer
echo ERROR: ImageDescriber build not found at ..\..\imagedescriber\dist\ImageDescriber\ (ImageDescriber.exe and imagedescriber-lib)
echo Run builditall_wx.bat first
exit /b 1

:missing_chat
echo ERROR: IDTChat build not found at ..\..\chatapp\dist\IDTChat\ (IDTChat.exe and idtchat-lib)
echo Run builditall_wx.bat first
exit /b 1

:copy_failed
echo ERROR: copying into dist_all\bin failed
exit /b 1
