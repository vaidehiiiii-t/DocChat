# DocChat Production Deployment Guide

This guide describes how to deploy, configure, secure, and operate DocChat in a production environment.

---

## 1. System Requirements

- **Operating System:** Linux (Ubuntu 22.04 LTS / Debian 12 recommended) or Windows Server
- **Python:** 3.11+ (managed via `uv` or virtualenv)
- **Node.js / Package Manager:** Bun 1.1+ or Node 18+ / npm
- **Database:** TiDB Serverless (Cloud MySQL 8.0 compatible) or self-hosted MySQL 8.0+ with `utf8mb4`
- **Reverse Proxy:** Nginx or Caddy with SSE streaming support (`proxy_buffering off`)

---

## 2. Environment Variables Checklist

Ensure the following variables are set in production (e.g. via systemd environment, AWS Parameter Store, or Docker secrets):

| Variable | Requirement | Description | Example / Recommended |
|---|---|---|---|
| `FLASK_ENV` | **Required** | Environment profile | `production` |
| `SECRET_KEY` | **Required** | High-entropy secret for Flask session cookies | Minimum 32 random chars: `openssl rand -hex 32` |
| `JWT_SECRET_KEY` | **Required** | High-entropy secret for signing JWT tokens | Minimum 32 random chars: `openssl rand -hex 32` |
| `JWT_ACCESS_MINUTES` | Optional | JWT access token lifetime | `60` (or `120`) |
| `DATABASE_URL` | **Required** | MySQL / TiDB connection string | `mysql+pymysql://<user>:<password>@<host>:4000/docchat?ssl_verify_cert=true` |
| `UPLOAD_DIR` | Optional | Absolute or persistent path for raw uploaded documents | `/var/lib/docchat/uploads` |
| `CHROMA_DIR` | Optional | Path for local Chroma vector database | `/var/lib/docchat/chroma` |
| `MAX_UPLOAD_MB` | Optional | Max allowed upload size per file | `20` |
| `ALLOWED_EXTENSIONS` | Optional | Permitted file extensions | `pdf,txt,md` |
| `EMBEDDING_MODEL` | Optional | Sentence Transformer model | `sentence-transformers/all-MiniLM-L6-v2` |
| `TOP_K` | Optional | Number of retrieved chunks | `5` |
| `MAX_DISTANCE` | Optional | Cosine distance cutoff threshold | `0.55` |
| `OPENROUTER_API_KEY` | **Required** | OpenRouter API Key for LLM inference | `sk-or-v1-...` |
| `LLM_MODEL` | Optional | Primary model ID | `google/gemma-4-31b-it:free` |
| `LLM_FALLBACK_MODELS` | Optional | Fallback model IDs if primary fails | `nvidia/nemotron-3-super:free` |
| `ALLOW_PAID_MODELS` | Optional | Safety switch against accidental spend | `false` |
| `FRONTEND_ORIGIN` | **Required** | Allowed origin for CORS | `https://docchat.yourdomain.com` |

---

## 3. Database Migration & Initialization

1. Connect to MySQL / TiDB and ensure the target database exists with `utf8mb4`:
   ```sql
   CREATE DATABASE IF NOT EXISTS docchat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Apply database migrations:
   ```bash
   cd backend
   uv run flask db upgrade
   ```

---

## 4. Backend Service (Gunicorn)

In production, run the Flask backend using **Gunicorn** with a multi-worker setup:

```bash
cd backend
uv run gunicorn \
  --workers 2 \
  --bind 127.0.0.1:5000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
```

### Systemd Service Unit (`/etc/systemd/system/docchat-backend.service`)
```ini
[Unit]
Description=DocChat RAG Backend Application
After=network.target

[Service]
User=docchat
Group=docchat
WorkingDirectory=/opt/docchat/backend
EnvironmentFile=/opt/docchat/backend/.env
ExecStart=/home/docchat/.cargo/bin/uv run gunicorn --workers 2 --bind 127.0.0.1:5000 --timeout 120 wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 5. Frontend Build & Static Serving

Build the optimized production assets using `bun`:

```bash
cd frontend
bun install --frozen-lockfile
bun run build
```
This generates static assets in `frontend/dist/`.

---

## 6. Nginx Reverse Proxy Configuration

Nginx handles HTTPS termination, serves static frontend assets, and proxies API calls to Gunicorn.
Crucially, **buffering must be disabled for Server-Sent Events (SSE)** so tokens stream without lag.

```nginx
server {
    listen 80;
    server_name docchat.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name docchat.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/docchat.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/docchat.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Frontend Single Page App
    root /opt/docchat/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API Endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 25M;
    }

    # SSE Streaming endpoint: Disable proxy buffering
    location ~ ^/api/chat/sessions/[0-9]+/messages/stream$ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        chunked_transfer_encoding off;
    }
}
```

---

## 7. Backup, Disaster Recovery & Vector Rebuilding

DocChat uses MySQL / TiDB as the **canonical source of truth** for all documents, chunk texts, user metadata, and chat history.

### Database Backup
```bash
# Automated daily TiDB / MySQL dump
mysqldump -h gateway01.ap-northeast-1.prod.aws.tidbcloud.com \
  -P 4000 \
  -u "<username>" \
  -p"<password>" \
  --ssl-mode=VERIFY_IDENTITY \
  --single-transaction \
  --routines \
  --triggers \
  docchat > /backups/docchat_$(date +%F).sql
```

### Vector Store Recovery
If the local Chroma storage (`storage/chroma`) is ever lost, corrupted, or deleted, you can fully rebuild all vector embeddings from MySQL chunks without losing data:

```bash
uv run python scripts/reindex.py --batch-size 50
```
This queries all `ready` documents and chunks from MySQL, generates embeddings with `all-MiniLM-L6-v2`, and repopulates the Chroma collection.

---

## 8. Verification & Smoke Testing

To verify the deployment in production:
```bash
# Run end-to-end smoke test suite
uv run python scripts/smoke_test.py --base-url https://docchat.yourdomain.com
```
All smoke checks (health, register, upload, poll, vector search, sync chat, streaming chat, and cascade delete) must pass with `ALL TESTS PASSED`.
