@echo off
title Rodz Tutoring - One-Click Automated Test Runner

echo ========================================================
echo   RODZ TUTORING - 1-CLICK TEST SUITE RUNNER
echo ========================================================
echo.

REM 1. Virtual Environment Activation
if not exist "%~dp0.venv\Scripts\activate.bat" goto use_system_python

echo [1/3] Activating project virtual environment: .venv
call "%~dp0.venv\Scripts\activate.bat"
goto check_args

:use_system_python
echo [1/3] Using system Python environment

:check_args
echo.
if "%~1"=="" goto run_all_apps

echo [2/3] Target apps specified: %*
echo.
echo [3/3] Executing targeted test suite...
echo.
python "%~dp0manage.py" test %* --verbosity=1
goto evaluate_result

:run_all_apps
echo [2/3] Preparing test run for ALL apps: accounts, content_hub, wallet, quizzes
echo.
echo [3/3] Executing comprehensive test suite...
echo.
python "%~dp0manage.py" test accounts content_hub wallet quizzes --verbosity=1

:evaluate_result
set TEST_EXIT_CODE=%ERRORLEVEL%

echo.
echo ========================================================
if %TEST_EXIT_CODE% EQU 0 (
    echo   [SUCCESS] ALL TESTS PASSED SUCCESSFULLY!
    echo   Accounts, Content Hub, Wallet, and Quizzes are verified.
) else (
    echo   [FAILED] TEST SUITE FAILED WITH EXIT CODE: %TEST_EXIT_CODE%
    echo   Please inspect the test failure traceback above.
)
echo ========================================================
echo.

REM Keep command prompt window open so user can review results on double-click
pause
exit /b %TEST_EXIT_CODE%
