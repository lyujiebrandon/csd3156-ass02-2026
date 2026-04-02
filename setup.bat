@echo off
setlocal EnableDelayedExpansion
title DocuMind - Project Setup

:: ============================================================
::  DocuMind Setup Script
::  CSD3156 Cloud Computing - Group 20
:: ============================================================

set "ROOT=%~dp0"
set "TERRAFORM_DIR=%ROOT%terraform"
set "FRONTEND_DIR=%ROOT%frontend"
set "ENV_FILE=%FRONTEND_DIR%\.env.local"

call :header "DocuMind Project Setup"

:: ============================================================
:: STEP 1 - Check prerequisites
:: ============================================================
call :section "Checking prerequisites..."

call :check_tool terraform  "https://developer.hashicorp.com/terraform/downloads"
if errorlevel 1 goto :missing_prereq

call :check_tool node       "https://nodejs.org"
if errorlevel 1 goto :missing_prereq

call :check_tool npm        "https://nodejs.org"
if errorlevel 1 goto :missing_prereq

call :check_tool aws        "https://aws.amazon.com/cli"
if errorlevel 1 goto :missing_prereq

echo.
echo [OK] All prerequisites found.

:: ============================================================
:: STEP 2 - AWS credentials check
:: ============================================================
call :section "Checking AWS credentials..."

aws sts get-caller-identity >nul 2>&1
if errorlevel 1 (
    echo [WARN] AWS credentials not configured or expired.
    echo.
    echo If you are using AWS Academy Learner Lab:
    echo   1. Open your Learner Lab and click "AWS Details"
    echo   2. Copy the credentials block
    echo   3. Paste them into: %%USERPROFILE%%\.aws\credentials
    echo.
    set /p "CONTINUE=Press ENTER once credentials are configured, or Ctrl+C to abort: "
    aws sts get-caller-identity >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] AWS credentials still invalid. Aborting.
        goto :error
    )
)

for /f "tokens=*" %%i in ('aws sts get-caller-identity --query "Account" --output text 2^>nul') do set "AWS_ACCOUNT=%%i"
for /f "tokens=*" %%i in ('aws configure get region 2^>nul') do set "AWS_REGION=%%i"
if "!AWS_REGION!"=="" set "AWS_REGION=us-east-1"

echo [OK] Authenticated as account !AWS_ACCOUNT! in region !AWS_REGION!

:: ============================================================
:: STEP 3 - Terraform
:: ============================================================
call :section "Deploying infrastructure with Terraform..."

cd /d "%TERRAFORM_DIR%"

echo Initializing Terraform...
terraform init -upgrade
if errorlevel 1 (
    echo [ERROR] terraform init failed.
    goto :error
)

echo.
echo Planning infrastructure changes...
terraform plan -out=tfplan
if errorlevel 1 (
    echo [ERROR] terraform plan failed.
    goto :error
)

echo.
set /p "APPLY=Apply the plan? (yes/no): "
if /i not "!APPLY!"=="yes" (
    echo Skipping apply. You can run 'terraform apply tfplan' manually later.
    goto :skip_apply
)

terraform apply tfplan
if errorlevel 1 (
    echo [ERROR] terraform apply failed.
    goto :error
)

del /f /q tfplan 2>nul

:skip_apply

:: ============================================================
:: STEP 4 - Capture Terraform outputs
:: ============================================================
call :section "Reading Terraform outputs..."

for /f "tokens=*" %%i in ('terraform output -raw ec2_public_ip      2^>nul') do set "TF_EC2_IP=%%i"
for /f "tokens=*" %%i in ('terraform output -raw api_url            2^>nul') do set "TF_API_URL=%%i"
for /f "tokens=*" %%i in ('terraform output -raw websocket_url      2^>nul') do set "TF_WS_URL=%%i"
for /f "tokens=*" %%i in ('terraform output -raw cognito_user_pool_id 2^>nul') do set "TF_POOL_ID=%%i"
for /f "tokens=*" %%i in ('terraform output -raw cognito_client_id  2^>nul') do set "TF_CLIENT_ID=%%i"
for /f "tokens=*" %%i in ('terraform output -raw frontend_url       2^>nul') do set "TF_FRONTEND_URL=%%i"
for /f "tokens=*" %%i in ('terraform output -raw documents_bucket   2^>nul') do set "TF_BUCKET=%%i"

if "!TF_EC2_IP!"=="" (
    echo [WARN] Could not read Terraform outputs - infrastructure may not be deployed yet.
    echo        You will need to update %ENV_FILE% manually.
    goto :frontend_setup
)

echo.
echo   EC2 IP         : !TF_EC2_IP!
echo   API URL        : !TF_API_URL!
echo   WebSocket URL  : !TF_WS_URL!
echo   Cognito Pool   : !TF_POOL_ID!
echo   Cognito Client : !TF_CLIENT_ID!
echo   Frontend URL   : !TF_FRONTEND_URL!
echo   Documents S3   : !TF_BUCKET!

:: ============================================================
:: STEP 5 - Write frontend .env.local
:: ============================================================
call :section "Writing frontend environment file..."

(
    echo REACT_APP_AWS_REGION=!AWS_REGION!
    echo REACT_APP_COGNITO_USER_POOL_ID=!TF_POOL_ID!
    echo REACT_APP_COGNITO_CLIENT_ID=!TF_CLIENT_ID!
    echo REACT_APP_API_URL=!TF_API_URL!
    echo REACT_APP_WEBSOCKET_URL=!TF_WS_URL!
) > "%ENV_FILE%"

echo [OK] Written to %ENV_FILE%

:: ============================================================
:: STEP 6 - Frontend dependencies
:: ============================================================
:frontend_setup
call :section "Installing frontend dependencies..."

cd /d "%FRONTEND_DIR%"

npm install
if errorlevel 1 (
    echo [ERROR] npm install failed.
    goto :error
)

echo [OK] node_modules installed.

:: ============================================================
:: DONE
:: ============================================================
call :section "Setup complete!"

echo.
echo  Next steps:
echo  -----------
if not "!TF_EC2_IP!"=="" (
    echo  1. Wait ~2 minutes for EC2 to finish bootstrapping, then verify:
    echo       curl http://!TF_EC2_IP!/health
    echo.
)
echo  2. Start the React dev server:
echo       cd frontend ^&^& npm start
echo.
if not "!TF_FRONTEND_URL!"=="" (
    echo  3. Or visit the S3-hosted frontend:
    echo       !TF_FRONTEND_URL!
    echo.
)
echo  4. To tear down all infrastructure when done:
echo       cd terraform ^&^& terraform destroy

cd /d "%ROOT%"
echo.
pause
goto :eof

:: ============================================================
:: Helpers
:: ============================================================
:header
echo.
echo ============================================================
echo   %~1
echo ============================================================
echo.
goto :eof

:section
echo.
echo --- %~1
goto :eof

:check_tool
where %~1 >nul 2>&1
if errorlevel 1 (
    echo [MISSING] %~1 is not installed or not on PATH.
    echo           Download from: %~2
    exit /b 1
)
echo [OK] %~1 found.
exit /b 0

:missing_prereq
echo.
echo [ERROR] One or more prerequisites are missing. Install them and re-run this script.
goto :error

:error
cd /d "%ROOT%"
echo.
echo Setup did not complete. Review the errors above.
pause
exit /b 1
