# 🚀 Rodz Tutoring — AWS Deployment & CI/CD Pipeline Guide

Continuous Deployment pipeline connecting local development to AWS EC2 via **GitHub Actions** and **Docker Hub** with **1-click automatic updates**, semantic versioning, and rollback support (matching the architecture of `clarity-retail-lan`).

---

## 🏗️ 1-Click Architecture

```mermaid
flowchart TD
    subgraph DevWorkstation["💻 Developer PC"]
        Code["Code Changes / Fixes"] --> PushBat["push.bat (1-Click Push)"]
        PushBat --> VersionMgr["Auto-increments version.txt (e.g. v1.0.1)"]
        VersionMgr --> RunTests["Runs Django Automated Tests"]
        RunTests --> GitPush["Pushes branch 'main' + release tag 'v1.0.1'"]
    end

    subgraph GitHubActions["🐙 GitHub Actions (.github/workflows/build-and-push.yml)"]
        GitPush --> TestJob["1. Run Automated Test Suite"]
        TestJob --> BuildJob["2. Build Production Docker Image (Buildx Cache)"]
        BuildJob --> DockerHubPush["Pushes to Docker Hub:
        • :latest (Active production)
        • :v1.0.1 (Immutable rollback tag)"]
        DockerHubPush --> DeployJob["3. Deploy to AWS via SSH (appleboy/ssh-action)"]
    end

    subgraph AWSEC2["☁️ AWS EC2 Production Server"]
        DeployJob --> SCP["Transfers docker-compose.prod.yml"]
        SCP --> SSH["SSH Command Execution"]
        SSH --> Pull["docker compose pull web"]
        Pull --> Restart["docker compose up -d web"]
        Restart --> Entrypoint["entrypoint.sh auto-runs:
        • python manage.py migrate
        • python manage.py collectstatic"]
        Restart --> Prune["docker image prune -f"]
        Entrypoint --> LiveApp["Rodz Tutoring Live on Port 80 / Domain!"]
    end
```

---

## 🔑 GitHub Repository Secrets Configuration

In your GitHub repository, navigate to **Settings > Secrets and variables > Actions** and click **New repository secret**:

| Secret Name | Value / Description | Example |
| :--- | :--- | :--- |
| `DOCKERHUB_USERNAME` | Your Docker Hub account username. | `tinashemp` |
| `DOCKERHUB_TOKEN` | Docker Hub Personal Access Token (PAT with Read & Write access). | `dckr_pat_...` |
| `AWS_HOST` | Public IPv4 Address or Elastic IP of your AWS EC2 instance. | `13.244.120.45` |
| `AWS_USER` | SSH Username on the AWS instance (default for Ubuntu is `ubuntu`). | `ubuntu` |
| `AWS_SSH_PRIVATE_KEY` | Entire content of your AWS `.pem` private key file (including `-----BEGIN RSA PRIVATE KEY-----`). | `-----BEGIN RSA...` |

*(Optional)*: If your SSH port is not 22, add `AWS_PORT`.

---

## ☁️ 1-Command AWS Server Setup

### Step 1: Launch an AWS EC2 Instance
1. Go to AWS Management Console $\rightarrow$ **EC2** $\rightarrow$ **Launch Instance**.
2. **Name**: `rodz-tutoring-production`
3. **OS**: **Ubuntu Server 22.04 LTS** or **24.04 LTS** (64-bit x86).
4. **Instance Type**: `t3.small` (recommended for Gunicorn + Python) or `t3.micro` (free tier).
5. **Key Pair**: Select or create an `.pem` key pair (download and keep it safe).
6. **Network & Security Groups**: Allow:
   - ☑ **SSH (Port 22)** — Anywhere or your IP
   - ☑ **HTTP (Port 80)** — Anywhere (0.0.0.0/0)
   - ☑ **HTTPS (Port 443)** — Anywhere (0.0.0.0/0)
7. Click **Launch Instance**.

### Step 2: Initialize Server (Run Once)
Connect to your new EC2 instance via SSH:
```bash
ssh -i /path/to/your-key.pem ubuntu@YOUR_AWS_PUBLIC_IP
```

Download and run the setup script:
```bash
# Clone or transfer the rodz-tutoring repo, or run setup_ec2.sh directly:
curl -fsSL https://raw.githubusercontent.com/Avail-Technologies-Pvt-Ltd/rodz-tutoring/main/aws/setup_ec2.sh -o setup_ec2.sh
sudo bash setup_ec2.sh
```

This will automatically:
- Install Docker & Docker Compose
- Configure UFW firewall (Ports 22, 80, 443)
- Create `/home/ubuntu/rodz-tutoring`
- Generate `/home/ubuntu/rodz-tutoring/.env.prod`
- Set up `update.sh` and `rollback.sh`

### Step 3: Configure `.env.prod` on AWS
Edit `/home/ubuntu/rodz-tutoring/.env.prod`:
```bash
nano /home/ubuntu/rodz-tutoring/.env.prod
```
Ensure:
- `DOCKER_REGISTRY=yourdockerhubusername` (matches your Docker Hub account)
- `ALLOWED_HOSTS=*` (or your domain e.g. `rodztutoring.co.za,YOUR_AWS_IP`)
- `SECRET_KEY=your-secure-production-secret-key`

---

## ⚡ How to Trigger the 1-Click Update (From Your PC)

Whenever you have finished code changes or content updates:

1. Double-click **`push.bat`** (or `push_to_github.bat`).
2. The script will:
   - Read current version from `version.txt` (e.g. `1.0.0`) and propose `1.0.1`.
   - Prompt for an optional custom commit message.
   - Automatically run all 87+ automated tests (`python manage.py test`).
   - If tests pass, commit and create a Git release tag (`v1.0.1`).
   - Push branch and tag to GitHub origin `main`.
3. **GitHub Actions takes over completely**:
   - Compiles and publishes `:latest` and `:v1.0.1` to Docker Hub.
   - Connects to your AWS EC2 instance via SSH.
   - Pulls the new Docker image and restarts the container.
   - Runs database migrations automatically via `entrypoint.sh`.
   - Cleans up old Docker images.
   - **Your AWS website is updated!**

---

## 🔄 Useful AWS Server Commands

Connect to your AWS instance anytime:
```bash
# View live container logs
docker logs -f rodz_production_app

# Manual 1-click update on server
./rodz-tutoring/update.sh

# 1-second Instant Rollback to an older version (e.g. v1.0.0)
./rodz-tutoring/rollback.sh v1.0.0

# Create Django Superuser inside the production container
docker compose -f /home/ubuntu/rodz-tutoring/docker-compose.yml exec web python manage.py createsuperuser
```
