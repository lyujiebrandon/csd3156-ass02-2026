@echo off
if not defined DEPLOYING (
    set DEPLOYING=1
    cmd /k "%~f0"
    exit /b
)
setlocal EnableDelayedExpansion
title DocuMind - Deploy Backend to EC2

set "ROOT=%~dp0"
set "TERRAFORM_DIR=%ROOT%terraform"

echo.
echo ============================================================
echo   DocuMind - Push Backend Code to EC2
echo   Run this whenever you change backend/ec2_app/
echo ============================================================
echo.

cd /d "%TERRAFORM_DIR%"

echo Checking AWS credentials...
aws sts get-caller-identity >nul 2>&1
if errorlevel 1 (
    echo [ERROR] AWS credentials not configured or expired.
    goto :end
)

echo Reading Terraform outputs...
for /f "tokens=*" %%i in ('terraform output -raw ec2_public_ip    2^>nul') do set "EC2_IP=%%i"
for /f "tokens=*" %%i in ('terraform output -raw documents_bucket 2^>nul') do set "BUCKET=%%i"

if "!EC2_IP!"=="" (
    echo [ERROR] Could not read Terraform outputs.
    goto :end
)

echo   EC2 IP : !EC2_IP!
echo   Bucket : !BUCKET!

:: ── Step 1: Force-replace S3 object so EC2 always gets fresh code ─────────────
echo.
echo Uploading backend code to S3 (force replace)...
terraform apply -auto-approve -replace=module.ec2.aws_s3_object.ec2_app
if errorlevel 1 (
    echo [ERROR] terraform apply failed.
    goto :end
)
echo [OK] Code uploaded to s3://!BUCKET!/app/ec2_app.zip

:: ── Step 2: Get instance ID via Name tag (avoids special chars in query) ───────
echo.
echo Finding EC2 instance...
aws ec2 describe-instances ^
  --filters "Name=tag:Name,Values=documind-group20-backend" "Name=instance-state-name,Values=running" ^
  --query "Reservations[*].Instances[*].InstanceId" ^
  --output text > "%TEMP%\ec2_id.txt" 2>nul
set /p INSTANCE_ID=<"%TEMP%\ec2_id.txt"
del "%TEMP%\ec2_id.txt" >nul 2>&1

if "!INSTANCE_ID!"=="" (
    echo [ERROR] Could not find running EC2 instance. Check the AWS Console.
    goto :end
)
if "!INSTANCE_ID!"=="None" (
    echo [ERROR] No running EC2 instance found with tag Name=documind-group20-backend.
    goto :end
)
echo [OK] Found instance: !INSTANCE_ID!

:: ── Step 3: Write SSM parameters to a temp JSON file (avoids quoting issues) ──
echo.
echo Sending update commands to EC2 via SSM...
set "SSM_JSON=%TEMP%\ssm_params.json"
(
    echo {
    echo   "commands": [
    echo     "aws s3 cp s3://!BUCKET!/app/ec2_app.zip /opt/ec2_app.zip",
    echo     "unzip -o /opt/ec2_app.zip -d /opt/ec2_app",
    echo     "python3.11 -m pip install -r /opt/ec2_app/requirements.txt -q",
    echo     "systemctl restart documind",
    echo     "echo UPDATE COMPLETE"
    echo   ]
    echo }
) > "!SSM_JSON!"

aws ssm send-command ^
  --instance-ids "!INSTANCE_ID!" ^
  --document-name "AWS-RunShellScript" ^
  --parameters "file://!SSM_JSON!" ^
  --comment "DocuMind backend update" ^
  --output text >nul 2>&1

if errorlevel 1 (
    echo [WARN] SSM send-command failed - LabRole may not have SSM permissions.
    echo.
    echo Run these commands manually via EC2 Instance Connect in the AWS Console:
    echo   aws s3 cp s3://!BUCKET!/app/ec2_app.zip /opt/ec2_app.zip
    echo   unzip -o /opt/ec2_app.zip -d /opt/ec2_app
    echo   python3.11 -m pip install -r /opt/ec2_app/requirements.txt -q
    echo   systemctl restart documind
    goto :end
)

echo [OK] SSM command sent. Waiting 25 seconds for service restart...
timeout /t 25 /nobreak >nul

echo Verifying EC2 is responding...
curl -s --max-time 5 http://!EC2_IP!/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] EC2 not responding yet. Wait 30 more seconds then check again.
) else (
    echo [OK] EC2 backend is up with the new code.
)

echo.
echo ============================================================
echo   Done! Backend updated at http://!EC2_IP!
echo   Now run refresh-env.bat to rebuild and redeploy the frontend.
echo ============================================================

:end
del "%TEMP%\ssm_params.json" >nul 2>&1
cd /d "%ROOT%"
echo.
pause
cmd /k
