@echo off
REM =============================================
REM ABAY REPOSITORY DATABASE DEPLOYMENT SCRIPT
REM For Windows
REM =============================================

echo ============================================
echo ABAY REPOSITORY DATABASE DEPLOYMENT
echo ============================================
echo.

REM Configuration
set DB_NAME=abay_repository
set DB_USER=root
set DB_PASSWORD=
set DB_HOST=localhost
set DB_PORT=3306

echo Database: %DB_NAME%
echo User: %DB_USER%
echo Host: %DB_HOST%
echo.

echo Deploying database...
echo.

mysql -u %DB_USER% -p%DB_PASSWORD% -h %DB_HOST% -P %DB_PORT% < deploy_database.sql

if %errorlevel% == 0 (
    echo.
    echo ============================================
    echo ✅ DATABASE DEPLOYMENT COMPLETED SUCCESSFULLY!
    echo ============================================
    echo.
    echo Default Users:
    echo --------------
    echo Admin:   admin     / admin123
    echo Checker: checker   / checker123
    echo Maker:   maker     / maker123
    echo Author:  author    / author123
    echo Client:  client    / client123
    echo.
) else (
    echo.
    echo ============================================
    echo ❌ DATABASE DEPLOYMENT FAILED!
    echo ============================================
    echo Please check your MySQL credentials.
    echo.
)

pause