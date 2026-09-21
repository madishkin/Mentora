# Mentora AI — Backend 🎓🤖

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI" />
  <img src="https://img.shields.io/badge/Flutter-Client-02569B?style=for-the-badge&logo=flutter&logoColor=white" alt="Flutter" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
</p>

> **Mentora AI** is an intelligent educational platform powered by Large Language Models (LLMs) that automatically transforms lecture notes and study documents (PDF, DOCX) into a comprehensive, structured learning ecosystem.

---

## Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Engineering Highlights](#-engineering-highlights)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [API Documentation](#-api-documentation)
- [Project Structure](#-project-structure)
- [Frontend Client](#-frontend-client)
- [License](#-license)

---

## 💡 Overview

Preparing high-quality study materials (summaries, quizzes, flashcards, slides) is time-consuming for educators, while students often struggle with structuring raw lecture materials for efficient self-study.

**Mentora AI** solves this by acting as a digital instructional designer:
1. Ingests lecture notes, textbooks, or documents (PDF, DOCX).
2. Extracts and preprocesses clean text.
3. Concurrently prompts state-of-the-art LLMs to generate 6 distinct educational artifacts.
4. Provides native export capabilities into ready-to-use formats (`.apkg`, `.pptx`).

---

## Key Features

1. ** Adaptive Summaries**: Automatically adjusts depth, analogies, and technical rigor based on the target complexity level (Beginner, Intermediate, Advanced).
2. ** Interactive Quizzes**: Generates comprehensive multiple-choice quizzes with instant answer validation, score calculation, and detailed explanations.
3. ** Anki Flashcards**: Active-recall flashcards with instant export to `.apkg` files, ready for seamless import into Anki (desktop & mobile).
4. ** Hierarchical Mind Maps**: Multi-level conceptual breakdown (up to 3 levels deep) for visual understanding of topic relationships.
5. ** Presentation Slide Decks**: Generates 6 structured slides with key takeaways and comprehensive speaker notes + direct export to PowerPoint (`.pptx`).
6. ** Curated External Sources**: Selects verified external references (Wikipedia articles, books, documentations) for deeper study.

---

## 🏗 System Architecture

The project follows a decoupled client-server architecture: an asynchronous **FastAPI** backend and a cross-platform **Flutter** mobile client.

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Flutter App)
    participant FastAPI as FastAPI Backend
    participant DB as PostgreSQL DB
    participant OpenAI as OpenAI API (LLM)

    User->>FastAPI: POST /documents/upload (PDF / DOCX)
    Note over FastAPI: Format validation & text extraction
    FastAPI->>DB: Create document record (status = UPLOADED)
    FastAPI-->>User: document_id

    User->>FastAPI: POST /generate/{document_id}
    Note over FastAPI: Transaction with FOR UPDATE lock
    FastAPI->>DB: check_quota() — verify token balance
    FastAPI->>DB: Create job record (status = processing)
    
    FastAPI->>OpenAI: Parallel requests (asyncio.gather) to GPT-4o-mini
    OpenAI-->>FastAPI: Structured JSON with study materials
    
    FastAPI->>DB: deduct_tokens() — deduct quota
    FastAPI->>DB: Store result in JSONB, update status -> completed
    FastAPI-->>User: job_id (HTTP 202)

    User->>FastAPI: GET /study/{job_id} / GET /export/{job_id}/apkg
    FastAPI-->>User: Structured materials & binary downloads (.apkg, .pptx)
```

---

## ⚙️ Engineering Highlights

* **Parallel LLM Orchestration (`asyncio.gather`)**: 
  Generation is divided into two independent prompts:
  1. Summary, complexity grading, and quiz generation.
  2. Flashcards, mind map tree, presentation slides, and external sources.  
  Running these concurrently via `asyncio.gather` cuts generation latency by ~50% (from ~30s down to ~12–15s).
* **Race Condition Prevention (Row-Level Locking)**: 
  Token quota checks and deductions utilize PostgreSQL's `SELECT ... FOR UPDATE` (`.with_for_update()`). This guarantees strict atomicity and prevents quota bypass under concurrent requests.
* **Flexible Schema with PostgreSQL JSONB**: 
  Multi-layered generative results (e.g., nested mind map nodes, slide decks with speaker notes) are stored directly in native `JSONB` columns, avoiding relational overhead while preserving query performance.
* **On-the-Fly Binary Packaging**: 
  Compiles `.apkg` flashcard decks (via `genanki`) and `.pptx` presentations (via `python-pptx`) dynamically in memory, using RFC 5987 / UTF-8 encoded `Content-Disposition` headers for seamless international filename downloads.
* **Robust Security & Auth**: 
  JWT-based stateless authentication (access & refresh tokens) paired with `bcrypt` password hashing with explicit 72-byte truncation safeguards.

---

## 🛠 Tech Stack

* **Language**: Python 3.10+
* **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Uvicorn, Starlette)
* **Database & ORM**: PostgreSQL 16, [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Async), [asyncpg](https://github.com/MagicStack/asyncpg)
* **Database Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
* **Caching & Background Queues**: Redis 7
* **AI & Parsing**: [OpenAI Python SDK](https://github.com/openai/openai-python) (`gpt-4o-mini`), [PyMuPDF (fitz)](https://github.com/pymupdf/PyMuPDF), [docx2txt](https://github.com/ankushshah89/python-docx2txt)
* **File Generation**: `python-pptx`, `genanki`
* **Validation**: Pydantic v2, Pydantic-Settings

---

##  Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/madishkin/Mentora.git
cd Mentora
```

### 2. Set up virtual environment
```bash
python -m venv .venv

# On Windows:
.\.venv\Scripts\Activate.ps1

# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```
Key configuration settings:
```env
OPENAI_API_KEY=sk-your-openai-api-key
SECRET_KEY=your-super-secret-jwt-key
DATABASE_URL=postgresql+asyncpg://educraft:educraft_pass@localhost:5433/educraft
```

### 5. Launch PostgreSQL and Redis via Docker Compose
```bash
docker-compose up -d
```

### 6. Apply database migrations
```bash
alembic upgrade head
```

### 7. Run the development server
```bash
python run.py
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

##  API Documentation

Once the server is running, interactive API documentation is available at:
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📂 Project Structure

```text
├── alembic/                  # Database migration scripts
├── app/
│   ├── auth/                 # JWT authentication, password hashing & dependencies
│   ├── billing/              # Token quotas, plans, and rate-limiting
│   ├── common/               # Logging, error handlers, and utilities
│   ├── courses/              # Course models and grouping endpoints
│   ├── documents/            # PDF/DOCX ingestion and text parsing
│   ├── export/               # Anki (.apkg) and PowerPoint (.pptx) file builders
│   ├── generation/           # LLM orchestration and generation pipelines
│   ├── study/                # Study artifacts models, schemas, and endpoints
│   ├── users/                # User profile management
│   ├── config.py             # Pydantic BaseSettings configuration
│   ├── database.py           # Async SQLAlchemy engine and session setup
│   └── main.py               # FastAPI application factory and router mounting
├── tests/                    # Unit and integration test suite
├── docker-compose.yml        # PostgreSQL 16 and Redis 7 service definitions
├── requirements.txt          # Python dependencies
├── run.py                    # Server entry point
└── .env.example              # Environment variable template
```

---

##  Frontend Client

The companion mobile application is built using **Flutter** (Dart):
* **Cross-platform**: Android, iOS, Web, and Desktop support.
* **State Management**: Provider (`ChangeNotifier`).
* **Interactive UI**: Flip-card animations for Anki cards, dynamic expandable MindMap tree, and quiz evaluation with visual feedback.

---

##  License

This project is licensed under the [MIT License](LICENSE).
