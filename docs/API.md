# DocChat REST & Streaming API Documentation

Base URL: `http://localhost:5000/api`

DocChat provides a strictly isolated multi-tenant API for managing document ingestion, chunk vectorization, conversational session tracking, and grounded retrieval-augmented generation (RAG) with real-time SSE streaming.

---

## 1. Authentication & Common Conventions

### Request Headers
- Standard JSON endpoints:
  - `Content-Type: application/json`
  - `Authorization: Bearer <jwt_access_token>`
- Multipart upload endpoint:
  - `Content-Type: multipart/form-data`
  - `Authorization: Bearer <jwt_access_token>`
- SSE streaming endpoint:
  - `Accept: text/event-stream`
  - `Authorization: Bearer <jwt_access_token>`

### Standard Error Response Format
All errors follow a uniform JSON structure:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable explanation of error.",
    "details": {}
  }
}
```

| HTTP Status | Error Code | Description |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Malformed body, missing required fields, or validation failure |
| `401` | `UNAUTHORIZED` | Missing, expired, or invalid JWT token |
| `403` | `FORBIDDEN` | Access not permitted |
| `404` | `NOT_FOUND` | Resource not found (also returned on cross-user access to avoid leaking existence) |
| `409` | `CONFLICT` | Resource conflict (e.g. duplicate email during registration) |
| `413` | `PAYLOAD_TOO_LARGE` | Uploaded file exceeds 20 MB limit |
| `415` | `UNSUPPORTED_MEDIA` | File type is not allowed (must be PDF, TXT, or MD) |
| `429` | `RATE_LIMITED` | Too many requests (auth rate limit or chat turn rate limit) |
| `500` | `INTERNAL` | Unexpected internal server error |
| `503` | `LLM_UNAVAILABLE` | External LLM provider busy, rate-limited, or unreachable |

---

## 2. Health Check

### `GET /api/health`
Verifies backend service health, TiDB database connectivity (`SELECT 1`), and Chroma vector store persistence.

**Request:**
```bash
curl -X GET http://localhost:5000/api/health
```

**Success Response (`200 OK`):**
```json
{
  "status": "ok",
  "db": "ok",
  "vector_store": "ok"
}
```

---

## 3. Authentication Endpoints

### `POST /api/auth/register`
Creates a new user account.

**Request:**
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alex Mercer",
    "email": "alex@example.com",
    "password": "SecurePassword123!"
  }'
```

**Success Response (`201 Created`):**
```json
{
  "user": {
    "id": 1,
    "name": "Alex Mercer",
    "email": "alex@example.com",
    "created_at": "2026-09-29T00:00:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### `POST /api/auth/login`
Authenticates user credentials and returns a JWT access token.

**Request:**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex@example.com",
    "password": "SecurePassword123!"
  }'
```

**Success Response (`200 OK`):**
```json
{
  "user": {
    "id": 1,
    "name": "Alex Mercer",
    "email": "alex@example.com",
    "created_at": "2026-09-29T00:00:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### `GET /api/auth/me`
Fetches the currently authenticated user's profile.

**Request:**
```bash
curl -X GET http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`200 OK`):**
```json
{
  "user": {
    "id": 1,
    "name": "Alex Mercer",
    "email": "alex@example.com",
    "created_at": "2026-09-29T00:00:00Z"
  }
}
```

---

## 4. Document Management Endpoints

### `POST /api/documents`
Uploads a document (PDF, TXT, or MD) up to 20 MB. Validates magic bytes, assigns a secure UUID filename, and immediately schedules background parsing, chunking, and embedding.

**Request:**
```bash
curl -X POST http://localhost:5000/api/documents \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@/path/to/research_paper.pdf"
```

**Success Response (`202 Accepted`):**
```json
{
  "document": {
    "id": 10,
    "user_id": 1,
    "filename": "research_paper.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 1048576,
    "page_count": null,
    "chunk_count": 0,
    "status": "pending",
    "error_message": null,
    "created_at": "2026-09-29T00:05:00Z",
    "updated_at": "2026-09-29T00:05:00Z"
  }
}
```

---

### `GET /api/documents`
Lists all documents owned by the authenticated user, sorted newest first.

**Request:**
```bash
curl -X GET http://localhost:5000/api/documents \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`200 OK`):**
```json
[
  {
    "id": 10,
    "user_id": 1,
    "filename": "research_paper.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 1048576,
    "page_count": 8,
    "chunk_count": 24,
    "status": "ready",
    "error_message": null,
    "created_at": "2026-09-29T00:05:00Z",
    "updated_at": "2026-09-29T00:05:15Z"
  }
]
```

---

### `GET /api/documents/<id>`
Retrieves status, page count, and chunk count for a specific document.

**Request:**
```bash
curl -X GET http://localhost:5000/api/documents/10 \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`200 OK`):**
```json
{
  "id": 10,
  "user_id": 1,
  "filename": "research_paper.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1048576,
  "page_count": 8,
  "chunk_count": 24,
  "status": "ready",
  "error_message": null,
  "created_at": "2026-09-29T00:05:00Z",
  "updated_at": "2026-09-29T00:05:15Z"
}
```

---

### `DELETE /api/documents/<id>`
Permanently deletes a document: removes the raw file from storage, removes vector embeddings from ChromaDB, cascades deletion of chunks in MySQL, and sets `chat_sessions.document_id` to NULL.

**Request:**
```bash
curl -X DELETE http://localhost:5000/api/documents/10 \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`204 No Content`)**

---

## 5. Chat Sessions & Messages

### `POST /api/chat/sessions`
Creates a new conversation session. Scope can be global (omit `document_id`) or scoped to a specific ready document.

**Request (Scoped):**
```bash
curl -X POST http://localhost:5000/api/chat/sessions \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": 10,
    "title": "Quantum Mechanics Discussion"
  }'
```

**Success Response (`201 Created`):**
```json
{
  "id": 42,
  "user_id": 1,
  "document_id": 10,
  "title": "Quantum Mechanics Discussion",
  "created_at": "2026-09-29T00:10:00Z",
  "updated_at": "2026-09-29T00:10:00Z"
}
```

---

### `GET /api/chat/sessions`
Lists all conversations belonging to the user, ordered by most recent activity.

**Request:**
```bash
curl -X GET http://localhost:5000/api/chat/sessions \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`200 OK`):**
```json
[
  {
    "id": 42,
    "user_id": 1,
    "document_id": 10,
    "title": "Quantum Mechanics Discussion",
    "created_at": "2026-09-29T00:10:00Z",
    "updated_at": "2026-09-29T00:10:00Z"
  }
]
```

---

### `GET /api/chat/sessions/<id>/messages`
Retrieves message history for a session, in chronological order.

**Request:**
```bash
curl -X GET http://localhost:5000/api/chat/sessions/42/messages \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`200 OK`):**
```json
[
  {
    "id": 101,
    "session_id": 42,
    "role": "user",
    "content": "What is superposition?",
    "sources": [],
    "model": null,
    "created_at": "2026-09-29T00:11:00Z"
  },
  {
    "id": 102,
    "session_id": 42,
    "role": "assistant",
    "content": "Superposition is a fundamental principle of quantum mechanics...",
    "sources": [
      {
        "chunk_id": 55,
        "document_id": 10,
        "filename": "research_paper.pdf",
        "page": 2,
        "snippet": "Superposition allows particles to exist across multiple states simultaneously.",
        "score": 0.88
      }
    ],
    "model": "google/gemma-4-31b-it:free",
    "created_at": "2026-09-29T00:11:04Z"
  }
]
```

---

### `DELETE /api/chat/sessions/<id>`
Deletes a chat session and all its associated messages.

**Request:**
```bash
curl -X DELETE http://localhost:5000/api/chat/sessions/42 \
  -H "Authorization: Bearer <TOKEN>"
```

**Success Response (`204 No Content`)**

---

### `POST /api/chat/sessions/<id>/messages` (Synchronous Turn)
Sends a question to the document knowledge base. Performs semantic vector search, drops chunks beyond distance cutoff (0.55), grounds the prompt with chunk excerpts, and returns the generated answer.

**Request:**
```bash
curl -X POST http://localhost:5000/api/chat/sessions/42/messages \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "What is superposition?"
  }'
```

**Success Response (`200 OK`):**
```json
{
  "user_message": {
    "id": 101,
    "session_id": 42,
    "role": "user",
    "content": "What is superposition?",
    "sources": [],
    "model": null,
    "created_at": "2026-09-29T00:11:00Z"
  },
  "assistant_message": {
    "id": 102,
    "session_id": 42,
    "role": "assistant",
    "content": "Superposition is a fundamental principle where a quantum system exists in multiple states [1].",
    "sources": [
      {
        "chunk_id": 55,
        "document_id": 10,
        "filename": "research_paper.pdf",
        "page": 2,
        "snippet": "Superposition allows particles to exist across multiple states simultaneously.",
        "score": 0.88
      }
    ],
    "model": "google/gemma-4-31b-it:free",
    "created_at": "2026-09-29T00:11:04Z"
  }
}
```

---

### `POST /api/chat/sessions/<id>/messages/stream` (SSE Streaming Turn)
Sends a question and streams the response token by token via Server-Sent Events (SSE).

**Request:**
```bash
curl -N -X POST http://localhost:5000/api/chat/sessions/42/messages/stream \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "What is superposition?"
  }'
```

**Event Sequence:**
1. `event: sources`: Emitted immediately upon chunk retrieval:
   ```
   event: sources
   data: [{"chunk_id":55,"document_id":10,"filename":"research_paper.pdf","page":2,"snippet":"Superposition...","score":0.88}]
   ```
2. `event: token`: Emitted progressively for each generated token:
   ```
   event: token
   data: {"token": "Super"}

   event: token
   data: {"token": "position"}

   event: token
   data: {"token": " is"}
   ```
3. `event: done`: Emitted when generation finishes and messages are committed:
   ```
   event: done
   data: {"user_message_id": 101, "assistant_message_id": 102, "model": "google/gemma-4-31b-it:free"}
   ```
4. `event: error`: Emitted if the LLM encounters a failure (no partial assistant message is saved):
   ```
   event: error
   data: {"code": "LLM_UNAVAILABLE", "message": "Upstream model rate limit reached."}
   ```
