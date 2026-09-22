# Backend API — Local Development Guide

This folder contains the **FastAPI backend** for the production e-commerce platform.

The backend is the single API source used by both:

- **Customer Frontend**
- **CMS / Admin**

The recommended local development flow is:

```text
PostgreSQL
   ↓
FastAPI Backend
   ├── Customer Frontend
   └── CMS
```

---

## 1. Requirements

Install the following before starting the backend:

- Python 3.11+ recommended
- PostgreSQL 14+ recommended
- Git (optional)
- A terminal / command prompt

Check Python:

### Windows

```powershell
python --version
```

If `python` is not available:

```powershell
py --version
```

### macOS

```bash
python3 --version
```

Check PostgreSQL:

```bash
psql --version
```

---

# 2. Windows Setup

Open **PowerShell** or **Command Prompt** and go to the backend folder.

```powershell
cd path\to\backend
```

Example:

```powershell
cd E:\e\backend
```

## Create virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

After activation, your terminal should show:

```text
(.venv)
```

## Install dependencies

If the project contains `requirements.txt`:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the project uses `pyproject.toml` instead, install the project according to that file's package configuration.

---

# 3. macOS Setup

Open Terminal and go to the backend folder:

```bash
cd /path/to/backend
```

Example:

```bash
cd ~/Projects/backend
```

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

# 4. PostgreSQL Database

Create a PostgreSQL database for local development.

Example:

```sql
CREATE DATABASE ecommerce_db;
```

Create a dedicated local database user if required:

```sql
CREATE USER ecommerce_user WITH PASSWORD 'change_this_password';
```

Grant access:

```sql
GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_user;
```

> Use your own local PostgreSQL username/password. Do not commit real production credentials to Git.

---

# 5. Environment Variables

Create the backend environment file expected by the project.

Typical local configuration:

```env
DATABASE_URL=postgresql+asyncpg://ecommerce_user:change_this_password@localhost:5432/ecommerce_db

SECRET_KEY=change-this-local-secret
ALGORITHM=HS256

CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

If the project already contains an `.env.example`, copy it first and then update the values.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS:

```bash
cp .env.example .env
```

**Do not commit `.env` to Git.**

---

# 6. Run Database Migrations

This project uses **Alembic** for database migrations.

With the virtual environment activated:

```bash
python -m alembic upgrade head
```

If the project specifically provides an Alembic command through its environment, this is also possible:

```bash
alembic upgrade head
```

Using:

```bash
python -m alembic upgrade head
```

is recommended because it makes sure Alembic runs from the active Python environment.

---

# 7. Start the FastAPI Backend

The normal development command is:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

If `uvicorn` is not found:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
``` used
uvicorn app.main:app --reload
```
The backend will be available at:

```text
http://127.0.0.1:8000
```

FastAPI Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

---

# 8. Windows Quick Start

After PostgreSQL is running:

```powershell
cd E:\e\backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m alembic upgrade head

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

# 9. macOS Quick Start

```bash
cd /path/to/backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m alembic upgrade head

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

# 10. Verify the Backend

Open:

```text
http://127.0.0.1:8000/docs
```

You should see the FastAPI Swagger UI.

You can also test the API from a terminal:

```bash
curl http://127.0.0.1:8000/
```

If the project exposes a health endpoint, test it with:

```bash
curl http://127.0.0.1:8000/health
```

The exact health endpoint should be confirmed from the current API routes if it differs.

---

# 11. CMS Dummy Admin Account

For **local development only**, use the following dummy CMS administrator credentials if the database has been seeded with the development admin account:

```text
Admin User ID: admin
Admin Password: Admin@12345
```

### Important

These credentials are **dummy development credentials**.

Before deploying to production:

1. Log in to the CMS.
2. Change the password immediately.
3. Prefer changing the admin username/email as well.
4. Use a strong unique password.
5. Never commit the production password to Git.
6. Never place production credentials inside frontend JavaScript.
7. Store production secrets in the deployment platform's secret/environment-variable manager.

If your current database does not contain this dummy account, create the admin through the project's supported admin/user seed or administration flow rather than adding credentials directly to frontend code.

---

# 12. Frontend + CMS Connection

The backend should be running before starting the Frontend or CMS.

Local backend:

```text
http://127.0.0.1:8000
```

The Frontend and CMS should point their API base URL to the backend.

Typical local environment value:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not hard-code production URLs into application source code.

For production, configure the deployed API URL through environment variables.

Example:

```env
VITE_API_BASE_URL=https://api.example.com
```

---

# 13. Production Deployment Checklist

Before production deployment:

- [ ] PostgreSQL production database created
- [ ] Alembic migrations applied
- [ ] Production `DATABASE_URL` configured
- [ ] Strong production `SECRET_KEY` configured
- [ ] Production CORS origins configured
- [ ] Dummy admin password changed
- [ ] Debug/reload mode disabled
- [ ] HTTPS enabled
- [ ] Production API URL configured in Frontend
- [ ] Production API URL configured in CMS
- [ ] `.env` excluded from Git
- [ ] No hard-coded passwords or API keys
- [ ] Database backups configured
- [ ] Logging/monitoring configured
- [ ] API health check verified

For production, run without development reload:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

A reverse proxy such as Nginx or a managed cloud load balancer can then expose the API over HTTPS.

---

# 14. Recommended Project Structure

The backend should remain independent from the Frontend and CMS:

```text
backend/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── core/
│   └── main.py
├── alembic/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

The Frontend and CMS communicate with this backend through HTTP APIs. They should not directly access PostgreSQL.

---

## Important Security Rule

The **Frontend and CMS must never connect directly to PostgreSQL**.

Correct:

```text
Frontend → FastAPI → PostgreSQL
CMS      → FastAPI → PostgreSQL
```

Incorrect:

```text
Frontend → PostgreSQL
CMS      → PostgreSQL
```
```
admin user id and pass

Email:    admin@myshop.com
Password: Admin@2026Secure
Name:     Store Administrator

Keeping FastAPI as the single API/data-access layer keeps authentication, authorization, validation, business rules, inventory, orders, CMS changes, and database operations centralized.
#   E - B a c k e n d 
 
 