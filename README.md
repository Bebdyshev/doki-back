# Doki-back: FastAPI Knowledge Base & Chatbot Backend

## Features
- User authentication (JWT)
- User profile management
- Document CRUD & export (PDF, DOCX, TXT)
- Full-text search (Postgres)
- AI chat with Groq LLM (default: Llama, user-selectable)
- Web search via Serper.dev
- Knowledge base tool (fetches stored docs)
- Chat history with context window limit

## Requirements
- Python 3.11+
- PostgreSQL
- Groq API key
- Serper.dev API key

## Setup
1. Clone the repo
2. Create and activate a virtualenv
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your secrets
5. Run database migrations (if using Alembic)
6. Start the server:
   ```bash
   uvicorn src.app:app --reload
   ```

## .env.example
See `.env.example` in this repo for required environment variables.

## API Usage
- Auth: `/auth/register`, `/auth/login`, `/auth/logout`
- User: `/users/{user_id}`
- Documents: `/documents/` (CRUD, export)
- Search: `/search/`
- Chat: `/chat/` (POST, see below)

- Optional query param: `model` (Groq model id)

## Environment Variables
See `.env.example` for all required variables.