@echo off
REM This batch file runs the translate_excel.py script.

REM --- Configuration ---
REM Set the directory where your Python script (translate_excel.py) is located.
REM Make sure this path is correct.
SET SCRIPT_DIR=C:\GitHub\Gakumas-Commu-AutoTL
REM Set the name of your Python script.
SET SCRIPT_NAME=translate_excel.py

REM --- Execution ---

REM Change to the script directory.
cd "%SCRIPT_DIR%"

REM Check if the change directory was successful.
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Could not change to directory "%SCRIPT_DIR%".
    echo Please check if the SCRIPT_DIR path is correct.
    goto :end
)

REM Run the Python script.
REM Make sure 'python' command is in your system's PATH.
REM If not, replace 'python' with the full path to your python executable,
REM e.g., "C:\Python39\python.exe"
echo Running %SCRIPT_NAME%...
python "%SCRIPT_NAME%"

REM Check if the Python script executed successfully.
IF %ERRORLEVEL% NEQ 0 (
    echo Error: The Python script encountered an error.
    echo Please check the script output above for details.
) else (
    echo Script finished successfully.
)

:end
REM Pause the script so you can see the output before the window closes.
pause
