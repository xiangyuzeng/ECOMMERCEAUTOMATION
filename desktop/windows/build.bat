@echo off
REM Build Windows launcher .exe
REM Requires Node.js installed on build machine

echo Building EcommerceAutomation.exe...
npx pkg launcher.js --targets node18-win-x64 --output EcommerceAutomation.exe
echo.
echo Done! EcommerceAutomation.exe has been created.
echo Move it to the project root to use.
pause
