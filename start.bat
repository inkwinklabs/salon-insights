@echo off
REM ---------------------------------------------------------------
REM  Double-click this file to start Salon Customer Insights.
REM  It runs start.py, which sets things up on the first run.
REM ---------------------------------------------------------------

REM Work from the folder this file is in, wherever it was opened from.
cd /d "%~dp0"

REM "py" is the Python launcher that python.org installs on Windows. Try it first.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 start.py %*
    goto done
)

REM Otherwise try plain "python".
where python >nul 2>nul
if %errorlevel%==0 (
    python start.py %*
    goto done
)

echo.
echo  Python was not found on this computer.
echo  1. Install Python 3.11 or newer from https://www.python.org/downloads/
echo  2. During installation, tick "Add Python to PATH".
echo  3. Double-click start.bat again.

:done
echo.
REM Keep the window open so any message can be read before it closes.
pause
