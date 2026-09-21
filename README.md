# EduCraft AI — Backend 🎓🤖

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI" />
  <img src="https://img.shields.io/badge/Flutter-Client-02569B?style=for-the-badge&logo=flutter&logoColor=white" alt="Flutter" />
</p>

> **EduCraft AI** — интеллектуальная образовательная платформа, использующая большие языковые модели (LLM) для автоматического преобразования лекций и учебных документов (PDF, DOCX) в структурированную экосистему учебных материалов.

---

## 📌 Содержание
- [О проекте](#-о-проекте)
- [Функциональные возможности](#-функциональные-возможности)
- [Архитектура системы](#-архитектура-системы)
- [Ключевые инженерные решения](#-ключевые-инженерные-решения)
- [Стек технологий](#-стек-технологий)
- [Быстрый старт](#-быстрый-старт)
- [Переменные окружения](#-переменные-окружения)
- [Документация API](#-документация-api)
- [Структура проекта](#-структура-проекта)
- [Клиентское приложение (Frontend)](#-клиентское-приложение-frontend)

---

## 💡 О проекте

Платформа решает проблему нехватки времени у преподавателей на подготовку методических материалов и помогает студентам автоматизировать процесс самоподготовки и интервального повторения.

Сервер принимает учебные документы, извлекает текст и с помощью ИИ генерирует 6 типов готовых учебных артефактов, а также предоставляет API для экспорта в нативные форматы (.apkg, .pptx).

---

## ✨ Функциональные возможности

1. **📝 Автоматический конспект (Summary)**: адаптация глубины изложения под целевой уровень сложности лекции (базовый, средний, продвинутый).
2. **🎯 Адаптивные тесты (Quizzes)**: интерактивный квиз с несколькими вариантами ответов, проверкой и объяснениями.
3. **🗂️ Карточки для запоминания (Anki Flashcards)**: генерация карточек по принципу *Active Recall* с возможностью прямой выгрузки в файл `.apkg` для импорта в Anki.
4. **🧠 Ментальные карты (Mind Maps)**: иерархическая структура лекции (до 3 уровней вложенности) для наглядного понимания взаимосвязей.
5. **📊 Презентации (Slides)**: структура из слайдов с тезисами и подробными заметками для спикера + экспорт в PowerPoint (`.pptx`).
6. **🔗 Рекомендации источников**: подбор реальных внешних источников (статьи, книги, справочники) для углубления в тему.

---

## 🏗 Архитектура системы

Проект построен по клиент-серверной архитектуре: асинхронный API-бэкенд на **FastAPI** + мобильный клиент на **Flutter**.

```mermaid
sequenceDiagram
    autonumber
    actor User as Пользователь (Flutter App)
    participant FastAPI as FastAPI Backend
    participant DB as PostgreSQL DB
    participant OpenAI as OpenAI API (LLM)

    User->>FastAPI: POST /documents/upload (PDF / DOCX)
    Note over FastAPI: Валидация формата и извлечение текста
    FastAPI->>DB: Создание документа со статусом UPLOADED
    FastAPI-->>User: document_id

    User->>FastAPI: POST /generate/{document_id}
    Note over FastAPI: Транзакция с блокировкой FOR UPDATE
    FastAPI->>DB: check_quota() — проверка баланса токенов
    FastAPI->>DB: Создание задачи (job, status=processing)
    
    FastAPI->>OpenAI: Параллельные запросы (asyncio.gather) к GPT-4o-mini
    OpenAI-->>FastAPI: Структурированный JSON с материалами
    
    FastAPI->>DB: deduct_tokens() — списание квоты
    FastAPI->>DB: Сохранение результата в JSONB, статус -> completed
    FastAPI-->>User: job_id (HTTP 202)

    User->>FastAPI: GET /study/{job_id} / GET /export/{job_id}/apkg
    FastAPI-->>User: Готовые материалы и бинарные файлы (.apkg, .pptx)
```

---

## ⚙️ Ключевые инженерные решения

* **Параллельная генерация через `asyncio.gather`**: 
  Генерация разбита на два независимых промпта (первый формирует конспект и тест, второй — карточки, ментальную карту и слайды). За счет параллельного выполнения время ответа сокращено с ~30 до ~12-15 секунд.
* **Защита от Race Conditions (Row-level locking)**: 
  При проверке и списании квот токенов пользователя используется `SELECT ... FOR UPDATE` (`.with_for_update()`). Это исключает параллельное превышение суточных/месячных лимитов при конкурентных запросах.
* **Гибкая схема данных на PostgreSQL JSONB**: 
  Результаты генерации сохраняются в нативный тип `JSONB`, что позволяет хранить сложные вложенные структуры (узлы ментальной карты, слайды с заметками) без избыточного усложнения реляционной схемы.
* **Экспорт на лету**: 
  Динамическая сборка бинарных пакетов `.apkg` (с помощью `genanki`) и `.pptx` (с помощью `python-pptx`) с корректной поддержкой UTF-8 заголовков `Content-Disposition`.
* **Безопасная аутентификация**: 
  JWT-токены (access + refresh), хеширование паролей через `bcrypt` с обходом ограничения в 72 байта.

---

## 🛠 Стек технологий

* **Язык**: Python 3.10+
* **Web-фреймворк**: [FastAPI](https://fastapi.tiangolo.com/) (Uvicorn, Starlette)
* **База данных & ORM**: PostgreSQL 16, [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Async), [asyncpg](https://github.com/MagicStack/asyncpg)
* **Миграции**: [Alembic](https://alembic.sqlalchemy.org/)
* **Кэш / Очереди**: Redis
* **AI & NLP**: [OpenAI Python SDK](https://github.com/openai/openai-python) (`gpt-4o-mini`), [PyMuPDF](https://github.com/pymupdf/PyMuPDF), [docx2txt](https://github.com/ankushshah89/python-docx2txt)
* **Генерация файлов**: `python-pptx`, `genanki`
* **Валидация**: Pydantic v2, Pydantic-Settings

---

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/madishkin/diplome.git
cd diplome
```

### 2. Создание виртуального окружения
```bash
python -m venv .venv
# Для Windows:
.\.venv\Scripts\Activate.ps1
# Для Linux/macOS:
source .venv/bin/activate
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
Скопируйте `.env.example` в `.env` и укажите свои параметры:
```bash
cp .env.example .env
```
Минимально необходимые переменные в `.env`:
```env
OPENAI_API_KEY=sk-your-openai-key
SECRET_KEY=your-super-secret-jwt-key
DATABASE_URL=postgresql+asyncpg://educraft:educraft_pass@localhost:5433/educraft
```

### 5. Запуск PostgreSQL и Redis через Docker Compose
```bash
docker-compose up -d
```

### 6. Применение миграций базы данных
```bash
alembic upgrade head
```

### 7. Запуск сервера
```bash
python run.py
# или
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📖 Документация API

После запуска приложения интерактивная документация доступна по адресам:
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📂 Структура проекта

```text
├── alembic/                  # Миграции структуры базы данных
├── app/
│   ├── auth/                 # Аутентификация, JWT, хеширование паролей
│   ├── billing/              # Управление квотами пользователей и токенами
│   ├── common/               # Логирование, ошибки, общие утилиты
│   ├── courses/              # Курсы и группировка материалов
│   ├── documents/            # Загрузка и парсинг PDF/DOCX
│   ├── export/               # Сборщики файлов Anki (.apkg) и PowerPoint (.pptx)
│   ├── generation/           # Модели и роуты генерации материалов
│   ├── study/                # Модели и роуты учебных материалов
│   ├── users/                # Управление пользователями
│   ├── config.py             # Конфигурация приложения и Pydantic-Settings
│   ├── database.py           # Инициализация асинхронного движка SQLAlchemy
│   └── main.py               # Точка сборки FastAPI приложения
├── tests/                    # Unit и интеграционные тесты
├── docker-compose.yml        # Контейнеры PostgreSQL 16 и Redis 7
├── requirements.txt          # Зависимости Python
├── run.py                    # Скрипт запуска
└── .env.example              # Шаблон конфигурации окружения
```

---

## 📱 Клиентское приложение (Frontend)

Мобильное приложение разработано на **Flutter** и находится в отдельном репозитории:
* **Кроссплатформенный клиент**: поддержка Android / iOS / Web / Desktop.
* **State Management**: Provider (`ChangeNotifier`).
* **Интерактивные виджеты**: Flip-карточки Anki, дерево MindMap, интерактивное прохождение тестов с подсветкой ошибок.

---

## 📄 Лицензия

Проект распространяется под лицензией [MIT](LICENSE).
