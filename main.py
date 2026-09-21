from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services import FileProcessor, FastAIService
from models import (
    ExtendedLectureResponse, Question, AnkiCard,
    ExternalSource, MindMapNode, PresentationSlide
)
from typing import Optional
import tempfile
import os

app = FastAPI(
    title="Mentora Extended API",
    description="Extended API for study plans, courses, and flashcards",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Mentora API",
        "status": "active"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Server is running",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY"))
    }


@app.post("/process-lecture", response_model=ExtendedLectureResponse)
async def process_lecture(
        file: UploadFile = File(...),
        generate_all: bool = True,
        target_difficulty: Optional[str] = None
):
    """
    Обрабатывает файл лекции и генерирует все материалы

    Args:
        file: PDF или DOCX файл
        generate_all: генерировать ли все материалы (игнорируется, всегда True)
        target_difficulty: beginner | intermediate | advanced (пока не используется)

    Returns:
        JSON с конспектом, тестами, карточками, источниками, mindmap, презентацией
    """

    # 1. ПРОВЕРКА ФАЙЛА
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не предоставлен")

    file_extension = file.filename.lower().split('.')[-1]
    if file_extension not in ['pdf', 'docx']:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только PDF и DOCX файлы"
        )

    # 2. временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    try:
        print(f"обработка файла: {file.filename}")

        # 3.
        print("извлечение текста...")
        if file_extension == 'pdf':
            lecture_text = FileProcessor.extract_text_from_pdf(temp_file_path)
        else:
            lecture_text = FileProcessor.extract_text_from_docx(temp_file_path)

        if not lecture_text or len(lecture_text.strip()) < 100:
            raise HTTPException(
                status_code=400,
                detail="Не удалось извлечь текст из файла или текст слишком короткий"
            )

        lecture_text = lecture_text[:15000]

        # 4.
        print("обработка...")

        raw_results = await FastAIService.process_all_features(
            lecture_text,
            target_difficulty=target_difficulty
        )
        # 5
        print("Парсинг результатов...")
        parsed_results = FastAIService.parse_results(raw_results, lecture_text)

        # 6.
        print("Формирование ответа...")
        response = ExtendedLectureResponse(
            summary=parsed_results['summary'],
            difficulty_level=parsed_results['difficulty_level'],
            test=[Question(**q) for q in parsed_results['test']],
            anki_cards=[AnkiCard(**c) for c in parsed_results['anki_cards']],
            external_sources=[ExternalSource(**s) for s in parsed_results['external_sources']],
            mindmap=MindMapNode(**parsed_results['mindmap']),
            presentation=[PresentationSlide(**s) for s in parsed_results['presentation']]
        )

        print("обработка завершена успешно!")
        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f" ошибка: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки: {str(e)}"
        )
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print("временный файл удалён")


if __name__ == "__main__":
    import uvicorn


    print("url: http://0.0.0.0:8000")
    print("документация: http://0.0.0.0:8000/docs")
    print("health check: http://0.0.0.0:8000/health")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )