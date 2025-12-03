# File Processing & Analysis API

Service for:
- User authentication (session cookie based) + optional TOTP 2FA
- Secure file storage on AWS S3
- File history, download, deletion
- Asynchronous file conversion
- Asynchronous content parsing (keyword / sentence extraction)
- Asynchronous tonality (sentiment) analysis
- Internal webhooks + SQS queue + caching layer for async task completion

OpenAPI spec: `swagger.yaml` (can be served via FastAPI `/docs` or `/redoc`).

## Table of Contents
1. Features
2. Architecture
3. Tech Stack
4. Security Model
5. Async Flow (Conversion / Parsing / Analysis)
6. Quick Start
7. Environment Variables (.env template)
8. Database & Migrations
9. AWS / S3 / SQS Setup
10. Usage Examples (curl)
11. Submodules
12. Troubleshooting

## 1. Features
- Registration, login, logout, invalidate other sessions
- Password hashing (bcrypt)
- Optional TOTP 2FA (QR enrollment)
- File upload (validated), list, download (presigned URL), delete
- Format conversion (docx->pdf, etc.) via async worker callback
- Parsing (keywords / sentence extraction)
- Tonality analysis (polarity, subjectivity, objective sentiment)
- Webhook endpoints for workers to push results
- Result caching + synchronous wait pattern (server waits for cached async result)
- Strong input validation with Pydantic v2

## 2. Architecture (High-Level)

```
          +---------+
Client -> | FastAPI | --(DB: Users / Files)----+
          +----+----+                          |
               | (enqueue JSON)                |
               v                               |
            +------+      (callback)        +------+
            | SQS  |  <-------------------- |Worker|
            +------+                         +-----+
               |                                 |
               | (after processing)              |
               v                                 |
        +----------------+                       |
        | InternalWebhook| --> Cache/DB Update --+
        +----------------+
               |
               v
         FastAPI returns (cached result or error)
```

Sequence (e.g. convert):
1. Client POST /files/convert
2. Service validates ownership + enqueues message (SQS)
3. Worker processes and calls webhook
4. Webhook stores result (DB/cache)
5. Original request (server-side waiting via `wait_for_cache`) responds with final status

## 3. Tech Stack
- FastAPI / Starlette
- SQLAlchemy 2.0 (async) + PostgreSQL (asyncpg)
- Alembic migrations
- Redis (assumed for caching async results)
- AWS S3 (file storage)
- AWS SQS (task queue)
- pyotp (TOTP 2FA)
- bcrypt (password hashing)
- Pydantic v2
- Uvicorn (ASGI server)
- Logging via project `settings.config.logger`

## 4. Security Model
- Session-based auth (HTTP only cookie `session_id`)
- Login establishes server-side session
- 2FA (enable via `/auth/enable-2fa`, disable via `/auth/disable-2fa`)
- TOTP secret stored per user; code required only if `is_2fa_enabled`
- Sensitive responses use minimal data; presigned URLs limited lifetime
- Ownership enforced on file operations (`check_user_file`)
- NOTE: `/files/parse-file` currently missing auth dependency (recommend adding `Depends(blacklist_check)`)

## 5. Async Flow Notes
- API appears synchronous externally; internally tasks are async via queue + webhook
- Waiting implemented through cache polling (`wait_for_cache(s3_key)`)
- Failure modes: queue send failure, timeout waiting for cache, worker error (status=failed)

## 6. Quick Start

Prerequisites:
- Python 3.11+
- PostgreSQL running
- Redis running
- AWS credentials with S3 + SQS permissions

Clone (with submodules):
```
git clone --recurse-submodules https://github.com/dlcastra/api_file_processing.git
cd api_file_processing
```

Create virtual env & install:
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

Configure `.env` (see template below), then run migrations:
```
alembic upgrade head
```

Run development server:
```
uvicorn src.main:app --reload
```

Access docs: http://localhost:8000/docs

## 7. Environment Variables (.env Template)

```
SECRET_KEY=...
DATABASE_URL=postgresql+asyncpg://postgres:password@db/docker_file_processing

AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=...
AWS_REGION=...
AWS_SQS_QUEUE_URL=...

CONVERTER_WEBHOOK_URL="http://main_app:8000/webhooks/converter-webhook"
FILE_PARSER_WEBHOOK_URL="http://main_app:8000/webhooks/parser-webhook"
ANALYSIS_WEBHOOK_URL="http://main_app:8000/webhooks/analysis-webhook"

FILE_CONVERTER_URL="http://file_converter:8080/converter/convert-file"
FILE_PARSER_URL="http://file_converter:8080/converter/parse-file"
TONALITY_ANALYSIS_URL="http://tonality_analysis:8030/api/analysis/tonality"
```

## 8. Database & Migrations

Initialize (if not already):
```
alembic init migrations
```

Generate migration:
```
alembic revision --autogenerate -m "Add files table"
```

Apply:
```
alembic upgrade head
```

Rollback:
```
alembic downgrade -1
```

## 9. AWS / S3 / SQS Setup
1. Create S3 bucket (block public ACLs as appropriate)
2. Create SQS standard queue
3. Configure IAM user or role with:
   - s3:PutObject, GetObject, DeleteObject
   - sqs:SendMessage, ReceiveMessage, DeleteMessage
4. Export credentials or place in `.env`
5. (Optional) Enable server-side encryption on bucket

## 10. Usage Examples (curl)

Registration:
```
curl -X POST http://localhost:8000/auth/registration \
  -H "Content-Type: application/json" \
  -d '{"username":"alice01","email":"alice@example.com","password":"Str0ng_Pass!","password1":"Str0ng_Pass!"}'
```

Login (stores cookie):
```
curl -i -c cookies.txt -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice01","password":"Str0ng_Pass!","totp_code":"123456"}'
```

Upload:
```
curl -b cookies.txt -F "file=@document.pdf" http://localhost:8000/files/upload
```

Convert:
```
curl -b cookies.txt -H "Content-Type: application/json" \
  -d '{"s3_key":"<your_key>.docx","format_from":"docx","format_to":"pdf"}' \
  http://localhost:8000/files/convert
```

Download (returns presigned URL):
```
curl -b cookies.txt http://localhost:8000/files/download/12
```

Delete:
```
curl -X DELETE -b cookies.txt http://localhost:8000/files/remove/12
```

Tonality:
```
curl -b cookies.txt -H "Content-Type: application/json" \
  -d '{"s3_key":"marketing_summary.txt"}' \
  http://localhost:8000/files/tonality-analysis
```

## 11. Submodules
(Existing guidance retained)

To clone (with submodules):
```
git clone --recurse-submodules https://github.com/dlcastra/api_file_processing.git
```

Update a submodule:
```
git submodule update --remote ./src/external/services/dirname
```

Add a submodule:
```
git submodule add <repo_url> ./src/external/services/dirname
```

## 12. Troubleshooting
- 400 File does not exist: Ensure file ownership; verify `s3_key` matches stored record.
- Conversion/Parsing stuck: Confirm worker posts to correct webhook URL & queue permissions.
- Presigned URL missing: Check AWS credentials + region + bucket name.
- 2FA failures: Ensure system clock is accurate (TOTP window).
- Migration errors: Inspect generated revision & DB connectivity.
