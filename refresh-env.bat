@echo off
if not defined REFRESHING (
    set REFRESHING=1
    cmd /k "%~f0"
    exit /b
)
setlocal EnableDelayedExpansion
title DocuMind - Refresh Environment

set "ROOT=%~dp0"
set "TERRAFORM_DIR=%ROOT%terraform"
set "FRONTEND_DIR=%ROOT%frontend"
set "ENV_FILE=%FRONTEND_DIR%\.env.local"

echo.
echo ============================================================
echo   DocuMind - Refresh Environment URLs
echo   Run this at the start of each Learner Lab session
echo ============================================================
echo.

cd /d "%TERRAFORM_DIR%"

echo Checking AWS credentials...
aws sts get-caller-identity >nul 2>&1
if errorlevel 1 (
    echo [ERROR] AWS credentials not configured or expired.
    echo Update %%USERPROFILE%%\.aws\credentials then re-run this script.
    goto :end
)

echo Reading Terraform outputs...
for /f "tokens=*" %%i in ('terraform output -raw ec2_public_ip        2^>nul') do set "TF_EC2_IP=%%i"
for /f "tokens=*" %%i in ('terraform output -raw api_url              2^>nul') do set "TF_API_URL=%%i"
for /f "tokens=*" %%i in ('terraform output -raw websocket_url        2^>nul') do set "TF_WS_URL=%%i"
for /f "tokens=*" %%i in ('terraform output -raw cognito_user_pool_id 2^>nul') do set "TF_POOL_ID=%%i"
for /f "tokens=*" %%i in ('terraform output -raw cognito_client_id    2^>nul') do set "TF_CLIENT_ID=%%i"
for /f "tokens=*" %%i in ('terraform output -raw frontend_url         2^>nul') do set "TF_FRONTEND_URL=%%i"
for /f "tokens=*" %%i in ('terraform output -raw frontend_bucket      2^>nul') do set "TF_FRONTEND_BUCKET=%%i"
for /f "tokens=*" %%i in ('aws configure get region                   2^>nul') do set "AWS_REGION=%%i"
if "!AWS_REGION!"=="" set "AWS_REGION=us-east-1"

if "!TF_EC2_IP!"=="" (
    echo [ERROR] Could not read Terraform outputs. Is the infrastructure deployed?
    goto :end
)

echo.
echo   EC2 IP          : !TF_EC2_IP!
echo   API URL         : !TF_API_URL!
echo   Frontend Bucket : !TF_FRONTEND_BUCKET!
echo   Frontend URL    : !TF_FRONTEND_URL!
echo.

echo Checking EC2 backend is reachable...
curl -s --max-time 5 http://!TF_EC2_IP!/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] EC2 not responding yet. It may still be starting up.
    echo        Wait 1-2 minutes then re-run this script.
    goto :end
)
echo [OK] EC2 backend is up.

:: ── Write .env.local ────────────────────────────────────────────────────────
echo.
echo Writing .env.local...
(
    echo REACT_APP_AWS_REGION=!AWS_REGION!
    echo REACT_APP_COGNITO_USER_POOL_ID=!TF_POOL_ID!
    echo REACT_APP_COGNITO_CLIENT_ID=!TF_CLIENT_ID!
    echo REACT_APP_API_URL=!TF_API_URL!
    echo REACT_APP_WEBSOCKET_URL=!TF_WS_URL!
) > "%ENV_FILE%"
echo [OK] Written to %ENV_FILE%

:: ── Build React app ─────────────────────────────────────────────────────────
echo.
echo Building React app (this takes ~1 minute)...
cd /d "%FRONTEND_DIR%"
call npm run build --no-audit
if errorlevel 1 (
    echo [ERROR] npm run build failed.
    goto :end
)
echo [OK] Build complete.

:: ── Deploy to S3 ────────────────────────────────────────────────────────────
echo.
echo Deploying to S3 bucket: !TF_FRONTEND_BUCKET!
aws s3 sync "%FRONTEND_DIR%\build" "s3://!TF_FRONTEND_BUCKET!" --delete
if errorlevel 1 (
    echo [ERROR] S3 sync failed.
    goto :end
)
echo [OK] Frontend deployed.

echo.
echo ============================================================
echo   Done! App is live at:
echo   !TF_FRONTEND_URL!
echo.
echo   Or for local dev: cd frontend ^&^& npm start
echo ============================================================

:end
cd /d "%ROOT%"
echo.
pause
cmd /k
