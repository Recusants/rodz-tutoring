# Rodz Tutoring - Django Learning Platform & Content Engine

A production-ready Django web application for **Rodz Tutoring** supporting Grades 7–12 across **CAPS**, **IEB**, and **Cambridge** curricula. Featuring multi-role email authentication, non-downloadable content protection (canvas PDF viewer & video streaming), an interactive quiz engine, a student coin wallet economy with WhatsApp order integration, 1-click dev/push scripts, and Docker Hub CI/CD.

---

## 🚀 1-Click Quickstart (Local Development)

### Windows (1-Click Batch):
Double-click or run:
```cmd
run_dev.bat
```
*(PowerShell alternative: `.\run_dev.ps1`)*

**What this automatically does:**
1. Checks for and creates Python `.venv` if not found.
2. Activates the virtual environment.
3. Installs dependencies from `requirements.txt`.
4. Copies `.env.example` to `.env` if missing.
5. Runs database migrations (`python manage.py migrate`).
6. Seeds initial demo subjects, users, protected PDFs, videos, and quizzes (`python manage.py seed_rodz`).
7. Opens your default web browser to `http://127.0.0.1:8089/`.
8. Starts the Django development server.

---

## 📦 Demo Accounts (Pre-Seeded)

| Role | Email | Password | Access / Notes |
| :--- | :--- | :--- | :--- |
| **Admin + Tutor + Student** | `admin@rodztutoring.co.za` | `RodzAdmin2026!` | Full admin access, manual coin crediting, tutor access, 500 coins |
| **Senior Tutor** | `tutor@rodztutoring.co.za` | `RodzTutor2026!` | Tutor access, views all teaching materials without coin deduction |
| **Student** | `student@rodztutoring.co.za` | `RodzStudent2026!` | Enrolled Grade 12 CAPS student, pre-credited with **150 coins** |

---

## ⚡ 1-Click Push to GitHub

Double-click or run:
```cmd
push_to_github.bat
```
*(PowerShell alternative: `.\push_to_github.ps1`)*

**What this does:**
1. Verifies git initialization and sets branch to `main`.
2. Prompts for remote repository URL if not yet configured.
3. Prompts for commit message (defaults to auto-timestamped message if left blank).
4. Stages all changes (`git add -A`), commits, and pushes to `origin main`.
5. Triggers the automated GitHub Actions Docker Hub workflow!

---

## 🐳 Docker Hub CI/CD Workflow

The repository includes [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml).

### Setting up Docker Hub Automated Push:
1. In your GitHub repository, navigate to **Settings > Secrets and variables > Actions**.
2. Add the following repository secrets:
   - `DOCKERHUB_USERNAME`: Your Docker Hub account username.
   - `DOCKERHUB_TOKEN`: Your Docker Hub Personal Access Token (PAT).
3. Whenever you run `push_to_github.bat`, GitHub Actions will build the production image and push it to:
   `yourdockerhubusername/rodz-tutoring:latest` and `yourdockerhubusername/rodz-tutoring:<sha>`

---

## 🚢 Production Docker Deployment

To test or deploy using Docker locally or on a production VPS:

```bash
# 1. Build and launch with docker-compose
docker-compose up --build -d

# 2. Check container status
docker-compose ps
```

---

## 🔒 Non-Downloadable Content Protection Architecture

1. **Protected PDF Canvas Viewer**:
   - PDFs are stored in `media/protected_pdfs/` away from public direct access.
   - Streamed via a secure Django endpoint (`/content/stream/<slug>/`) only after session and coin unlock verification.
   - Rendered strictly via **Mozilla PDF.js** onto HTML5 `<canvas>` elements.
   - No browser PDF download or print buttons are provided.
   - Dynamic translucent watermarks (`CONFIDENTIAL • LICENSED TO: student@email.com • RODZ TUTORING`) rendered over every canvas page.
   - Client-side keyboard shortcuts (`Ctrl+S`, `Ctrl+P`, `Ctrl+U`, `F12`) and right-click context menu are suppressed.
2. **In-App Video Streaming**:
   - Embedded responsive YouTube player (`modestbranding=1`, `rel=0`).
   - Right-click protected to prevent direct media link scraping.
3. **Interactive Quizzes**:
   - Timed multiple-choice quizzes with automatic scoring, pass/fail grading, and step-by-step mathematical explanations.

---

## 🪙 Student Coin Economy & WhatsApp Workflow

1. Students browse the Resource Hub. Free items are instantly accessible.
2. Premium items require a one-time coin spend (e.g. 50 coins) for permanent library access.
3. If a student needs coins, they visit **Buy Coins** (`/wallet/buy-coins/`) and choose a package.
4. Clicking "Order via WhatsApp" launches WhatsApp with a pre-filled order message containing their registered email and selected bundle.
5. The Admin verifies the proof of payment and credits the student's wallet via the **Admin Coin Credit Panel** (`/wallet/admin-credits/`).
