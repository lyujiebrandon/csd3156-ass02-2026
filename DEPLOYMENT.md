# DocuMind Deployment Guide

## Prerequisites

Install the following tools before you begin. All must be accessible from the command line.

| Tool | Download |
|------|----------|
| Terraform | https://developer.hashicorp.com/terraform/downloads |
| Node.js + npm | https://nodejs.org |
| AWS CLI | https://aws.amazon.com/cli |

Verify they are installed by opening a terminal and running:
```
terraform -v
node -v
aws --version
```

---

## Step 1 — Configure AWS Credentials

1. Open your **AWS Academy Learner Lab** and start the lab session
2. Click **AWS Details** → **Show** next to "AWS CLI"
3. Copy the entire credentials block (it looks like this):
   ```
   [default]
   aws_access_key_id=ASIA...
   aws_secret_access_key=...
   aws_session_token=...
   ```
4. Open the file `C:\Users\<YourName>\.aws\credentials` in Notepad and paste the block in, replacing any existing content
5. Save the file

> **Note:** Learner Lab credentials expire when your session ends. You must repeat this step every time you start a new lab session.

---

## Step 2 — Run setup.bat

1. Double-click **`setup.bat`** in the project root folder
2. The script will:
   - Check all prerequisites are installed
   - Verify your AWS credentials
   - Run `terraform init` and `terraform plan`
   - Ask you to confirm: **type `yes` and press Enter** to deploy
   - Write the frontend `.env.local` configuration file
   - Install frontend npm packages

3. At the end of the script you will see your deployment URLs:

   ```
   EC2 IP         : x.x.x.x
   API URL        : http://x.x.x.x
   Frontend URL   : http://documind-group20-frontend-<account>.s3-website-us-east-1.amazonaws.com
   ```

> The window stays open after completion. Copy the Frontend URL before closing it.

---

## Step 3 — Deploy the Frontend to S3

After `setup.bat` finishes, run **`refresh-env.bat`** to build the React app and deploy it to S3:

1. Double-click **`refresh-env.bat`**
2. It will:
   - Read the latest URLs from Terraform
   - Check the EC2 backend is reachable (wait if it says "not responding yet" — the EC2 needs ~2 minutes to finish booting)
   - Build the React app
   - Upload the build to the S3 frontend bucket

3. At the end you will see:
   ```
   Done! App is live at:
   http://documind-group20-frontend-<account>.s3-website-us-east-1.amazonaws.com
   ```

> If the EC2 is not yet responding, wait 2 minutes and run `refresh-env.bat` again.

---

## Step 4 — Open the App

Open the **Frontend URL** from Step 3 in your browser:

```
http://documind-group20-frontend-<account>.s3-website-us-east-1.amazonaws.com
```

1. Click **Sign Up** and register with your email
2. Verify your email using the code sent to your inbox
3. Log in
4. Go to **Upload** and upload a PDF or image to test

---

## Starting a New Lab Session

AWS Learner Lab credentials and EC2 instances reset when a session ends. At the start of every new session:

1. **Update credentials** — paste new credentials into `%USERPROFILE%\.aws\credentials` (repeat Step 1)
2. **Run `refresh-env.bat`** — this updates the config and redeploys the frontend with the current EC2 IP

You do **not** need to run `setup.bat` again unless you have destroyed the infrastructure.

---

## Tearing Down Infrastructure

When you are done with the project, destroy all AWS resources to avoid charges:

```
cd terraform
terraform destroy
```

Type `yes` when prompted. This removes all EC2 instances, S3 buckets, Lambda functions, and other resources created by Terraform.

---

## Troubleshooting

### "Failed to load documents" or "Network Error" in the app

The EC2 backend is unreachable or the frontend has a stale API URL.

**Fix:** Run `refresh-env.bat` and wait for it to complete.

### EC2 not responding in refresh-env.bat

The EC2 is still booting after a session restart (takes 1–2 minutes).

**Fix:** Wait 2 minutes and run `refresh-env.bat` again.

### AWS credentials error

Your Learner Lab session has expired or credentials were not saved correctly.

**Fix:** Start a new lab session, copy the new credentials, and update `%USERPROFILE%\.aws\credentials`.

### Terminal window closes immediately

Run the `.bat` file by double-clicking it. The window is designed to stay open until you close it manually.

### Backend code was changed

If you modify any files in `backend/ec2_app/`, run **`deploy-ec2.bat`** to push the changes to the running EC2 instance, then run `refresh-env.bat` to redeploy the frontend.

---

## Special Cases

### Pre-existing EC2 with outdated backend code

**When this happens:**
The EC2 instance was created at an earlier point in time with an older version of the backend code. Because EC2 only pulls code from S3 on first boot, any code changes made after the instance was created are not automatically applied. Symptoms include persistent "Network Error" or "Failed to load documents" errors even after `refresh-env.bat` runs successfully and the EC2 health check passes.

**How to confirm:**
Run this in PowerShell to test the CORS preflight response:
```powershell
Invoke-WebRequest -Uri "http://<EC2_IP>/documents" -Method OPTIONS `
  -Headers @{"Origin"="http://your-frontend-url.com"; "Access-Control-Request-Method"="GET"; "Access-Control-Request-Headers"="authorization"} `
  -UseBasicParsing | Select-Object -ExpandProperty Headers
```
If `access-control-allow-origin` is **missing** from the response, the EC2 is running old code.

**Fix — run `deploy-ec2.bat`:**

1. Double-click **`deploy-ec2.bat`**
2. It will:
   - Force-upload the latest backend code zip to S3
   - Find the running EC2 instance automatically
   - Send an update command to EC2 via AWS SSM to pull the new code and restart the service
3. Wait ~30 seconds, then verify:
   ```
   curl http://<EC2_IP>/health
   ```
4. Run **`refresh-env.bat`** afterward to rebuild and redeploy the frontend

> `deploy-ec2.bat` uses AWS Systems Manager (SSM) to run commands on EC2 remotely — no SSH key required. This works because EC2 instances in the Learner Lab use the `LabInstanceProfile` IAM role which includes SSM permissions.

**When you will need this:**
- You pulled new code changes from git onto an already-running EC2
- A teammate pushed backend changes while your EC2 was running
- You manually edited files in `backend/ec2_app/` after the initial deployment

**When you will NOT need this:**
- Running `setup.bat` for the first time on a clean environment — the EC2 always boots with the latest code
- After running `terraform destroy` and re-deploying — the new EC2 pulls fresh code on first boot
