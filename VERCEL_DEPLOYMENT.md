# FastAPI Backend — Vercel Deployment

## 1. Push to GitHub

From this folder:

```bash
git init
git add .
git commit -m "Prepare FastAPI backend for Vercel"
git branch -M main
git remote add origin https://github.com/<YOUR-USER>/<YOUR-REPO>.git
git push -u origin main
```

Do **not** commit `.env`, `.venv`, local database files, or uploaded media.

## 2. Vercel

Import the GitHub repository into Vercel.

If the GitHub repository contains this backend as its repository root, leave **Root Directory** as `./`.

If the backend is inside a larger monorepo, set Root Directory to the backend folder.

The repository already contains:
- `api/index.py`
- `vercel.json`
- `.vercelignore`

## 3. Required Environment Variables

Add these in Vercel → Project → Settings → Environment Variables:

```text
DATABASE_URL=<production PostgreSQL connection string>
SECRET_KEY=<long-random-production-secret>
BACKEND_CORS_ORIGINS=["https://YOUR-FRONTEND-DOMAIN"]
PROJECT_NAME=Production E-Commerce Platform API
API_V1_STR=/api/v1
```

Add the variables to the **Production** environment (and Preview if required).

## 4. URLs after deployment

```text
https://YOUR-DOMAIN.vercel.app/health
https://YOUR-DOMAIN.vercel.app/api/v1/health
https://YOUR-DOMAIN.vercel.app/api/v1/docs
```

## Important: uploaded product images

Vercel serverless functions do not provide persistent local storage. This deployment uses `/tmp/uploads` on Vercel so image-upload requests do not fail because of a read-only filesystem, but those files are ephemeral.

For permanent product images, use object storage such as S3/R2/Cloudinary and store the public URL in PostgreSQL. The existing API structure can be extended for that without removing the current product-image functionality.
