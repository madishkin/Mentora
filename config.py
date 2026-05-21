from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    max_text_length: int = 15000
    max_tokens_summary: int = 1500
    max_tokens_test: int = 2000

    min_questions: int = 5
    max_questions: int = 15

    api_title: str = "Lecture Processing API"
    api_description: str = "API для обработки лекций и генерации конспектов и тестов"
    api_version: str = "1.0.0"

settings = Settings()
