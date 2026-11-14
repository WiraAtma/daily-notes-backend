# Daily Notes API

A private notes backend built with FastAPI. Users authenticate with Google, receive an application JWT, and can manage only their own notes. Rich-text HTML is stored in PostgreSQL; image files are uploaded directly to private S3-compatible object storage.

## Features

- Google ID-token verification and application JWT authentication.
- Private notes CRUD with ownership-scoped queries and soft deletion.
- Rich-text content stored as HTML, with backend sanitization.
- Presigned image upload and download URLs scoped to the authenticated user.
- Gemini text generation with optional multiple images read from private object storage.
- An authenticated AI-model list endpoint for model dropdowns.
- PostgreSQL schema managed by Alembic.

## Technology

Python 3.12+, FastAPI, SQLAlchemy 2.x, PostgreSQL, Psycopg 3, Alembic, Pydantic Settings, Google Auth, PyJWT, Boto3, and pytest.

## Project structure

```text
app/
  api/          Authentication, notes, and upload endpoints
  core/         Settings and JWT security
  db/           SQLAlchemy base and session dependency
  models/       User and note tables
  schemas/      Request and response validation
  services/     Authentication, notes, and object storage
  utils/        UTC timestamp helper
migrations/
  versions/     Alembic revisions
tests/          API and service tests
```

## Setup

Use Python 3.12 or newer and create a virtual environment:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the environment variables in `.env`. Never commit this file. `DATABASE_URL`, `GOOGLE_CLIENT_ID`, and a strong `JWT_SECRET_KEY` (at least 32 characters) are required. S3 settings are required to use upload and download URL endpoints. Set `GEMINI_API_KEY` to enable AI text generation.

### Google OAuth

Create a Google OAuth client for the React Native application and set its client ID as `GOOGLE_CLIENT_ID`. The backend accepts only Google ID tokens verified for that audience; it does not use or store Google access tokens or passwords.

### PostgreSQL

Set `DATABASE_URL` to a PostgreSQL connection URL using Psycopg 3, for example:

```text
postgresql+psycopg://user:password@host:5432/database?sslmode=require
```

### Object storage

Configure the S3-compatible endpoint, access key, secret key, bucket, and region. Keep the bucket private. The API returns short-lived presigned URLs and never sends storage credentials to the client.

The client-provided MIME type is used to sign the upload but does not prove the bytes' actual format. Before displaying uploaded content, verify it in a trusted process: inspect the uploaded object's metadata and read its bytes (or use an object-storage event/worker), check the file signature against the allowed image formats, enforce the size limit, and reject or quarantine mismatches. Do not treat a successful presigned upload as content validation.

## Database migrations

Inspect the migration before applying it to the configured database:

```powershell
alembic upgrade head
```

To create a later migration after changing models:

```powershell
alembic revision --autogenerate -m "describe the schema change"
```

Review generated operations, then apply them with `alembic upgrade head`. Roll back one revision with `alembic downgrade -1`. The application does not run migrations at startup.

## Run

```powershell
uvicorn app.main:app --reload
```

The health endpoint is `GET /health`. Interactive endpoint documentation is available at `/docs`.

## API

All note and upload endpoints require `Authorization: Bearer <application-jwt>`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/google` | Verify a Google ID token and issue an application JWT |
| `POST` | `/notes` | Create a note |
| `GET` | `/notes?limit=50&offset=0` | List the current user's notes |
| `GET` | `/notes/{note_id}` | Retrieve an owned, non-deleted note |
| `PUT` | `/notes/{note_id}` | Update an owned, non-deleted note |
| `DELETE` | `/notes/{note_id}` | Soft-delete an owned note |
| `POST` | `/uploads/presigned-url` | Create a user-scoped image upload URL |
| `POST` | `/uploads/presigned-download-url` | Create a download URL for an owned object key |
| `GET` | `/ai/models` | List hardcoded Gemini model values and labels; first model is default |
| `POST` | `/ai/generate` | Generate text from a prompt and optionally up to 10 owned image objects |

`POST /ai/generate` accepts `{"prompt":"Describe this","model":"gemini-3.1-flash-lite","image_object_keys":["users/1/notes/...jpg"]}`. The `model` field is optional and defaults to `gemini-3.1-flash-lite`; use the values returned by `GET /ai/models`, not their display labels. Omit `image_object_keys` for text-only generation. Image object keys must belong to the authenticated user and point to supported JPEG, PNG, or WebP objects no larger than 5 MiB each. The model identifiers are configured as requested and must also be available to the Google Gemini API key's project.

Notes that are missing, deleted, or owned by another user return the same `404` response. Note HTML is sanitized on input, but clients must still sanitize HTML before rendering it in a web view. Do not persist temporary presigned URLs in note content; store stable object references instead.

Uploads accept JPEG, PNG, or WebP images up to 5 MiB. Object keys are generated by the API in `users/{user_id}/notes/{uuid}.{extension}`. Object deletion is available through the storage service only after checking this ownership prefix; no arbitrary object-key deletion endpoint is exposed.

## Tests

Tests use an isolated in-memory SQLite database and mocked Google/S3 integrations:

```powershell
python -m pytest
```

They cover Google login, JWT validation, note CRUD and cross-user isolation, soft deletion, upload validation, and object ownership checks. No cloud services or migrations are invoked by the test suite.
