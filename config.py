from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# КРИТИЧНО: Загружаем .env файл ПЕРЕД созданием Settings
load_dotenv()


class Settings(BaseSettings):
    # Убираем os.getenv() - pydantic сам загрузит из .env
    openai_api_key: str  # БЕЗ значения по умолчанию
    openai_model: str = "gpt-4o-mini"

    max_text_length: int = 15000
    max_tokens_summary: int = 1500
    max_tokens_test: int = 2000

    min_questions: int = 5
    max_questions: int = 15

    api_title: str = "Lecture Processing API"
    api_description: str = "API для обработки лекций и генерации конспектов и тестов"
    api_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # Не чувствительно к регистру


settings = Settings()
