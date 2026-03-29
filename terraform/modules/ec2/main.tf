# ── Latest Amazon Linux 2023 AMI ──────────────────────────────────────────────
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── Security Group ─────────────────────────────────────────────────────────────
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "DocuMind EC2 backend security group"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP (Nginx)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "FastAPI (direct debug)"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-ec2-sg"
    Environment = var.environment
  }
}

# ── Upload app code to S3 so EC2 can pull it on startup ───────────────────────
data "archive_file" "ec2_app" {
  type        = "zip"
  source_dir  = "${path.root}/../backend/ec2_app"
  output_path = "${path.module}/ec2_app.zip"
}

resource "aws_s3_object" "ec2_app" {
  bucket = var.documents_bucket
  key    = "app/ec2_app.zip"
  source = data.archive_file.ec2_app.output_path
  etag   = data.archive_file.ec2_app.output_md5
}

# ── IAM Instance Profile (use Academy's existing LabInstanceProfile) ───────────
data "aws_iam_instance_profile" "lab" {
  name = "LabInstanceProfile"
}

# ── EC2 Instance ───────────────────────────────────────────────────────────────
resource "aws_instance" "backend" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  key_name                    = var.key_name
  iam_instance_profile        = data.aws_iam_instance_profile.lab.name
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.ec2.id]

  user_data = <<-EOF
    #!/bin/bash
    set -e
    exec > /var/log/user-data.log 2>&1

    echo "=== Installing system packages ==="
    dnf update -y
    dnf install -y python3.11 python3.11-pip nginx unzip

    echo "=== Downloading app from S3 ==="
    aws s3 cp s3://${var.documents_bucket}/app/ec2_app.zip /opt/ec2_app.zip
    unzip -o /opt/ec2_app.zip -d /opt/ec2_app

    echo "=== Installing Python dependencies ==="
    python3.11 -m pip install -r /opt/ec2_app/requirements.txt

    echo "=== Creating systemd service ==="
    cat > /etc/systemd/system/documind.service << 'SERVICE'
    [Unit]
    Description=DocuMind FastAPI Backend
    After=network.target

    [Service]
    Type=simple
    User=ec2-user
    WorkingDirectory=/opt/ec2_app
    Environment=DOCUMENTS_BUCKET=${var.documents_bucket}
    Environment=DOCUMENTS_TABLE=${var.documents_table}
    Environment=JOBS_TABLE=${var.jobs_table}
    Environment=CONNECTIONS_TABLE=${var.connections_table}
    Environment=OCR_QUEUE_URL=${var.ocr_queue_url}
    Environment=AI_QUEUE_URL=${var.ai_queue_url}
    Environment=AWS_REGION=${var.aws_region}
    Environment=COGNITO_USER_POOL_ID=${var.cognito_user_pool_id}
    Environment=COGNITO_CLIENT_ID=${var.cognito_client_id}
    ExecStart=/usr/local/bin/uvicorn main:app --host 127.0.0.1 --port 8000
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    SERVICE

    echo "=== Configuring Nginx reverse proxy ==="
    cat > /etc/nginx/conf.d/documind.conf << 'NGINX'
    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass         http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_read_timeout 120s;
        }
    }
    NGINX

    # Remove default nginx config to avoid port conflict
    rm -f /etc/nginx/conf.d/default.conf

    echo "=== Starting services ==="
    systemctl daemon-reload
    systemctl enable documind
    systemctl start documind
    systemctl enable nginx
    systemctl start nginx

    echo "=== EC2 setup complete ==="
  EOF

  depends_on = [aws_s3_object.ec2_app]

  tags = {
    Name        = "${var.project_name}-backend"
    Environment = var.environment
  }
}
