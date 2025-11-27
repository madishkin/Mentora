import asyncio
import openai
import json
import pymupdf
import docx2txt
from typing import List, Dict
from fastapi import HTTPException
from config import settings
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=settings.openai_api_key)

openai.api_key = settings.openai_api_key

class FileProcessor:
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        try:
            doc = pymupdf.open(file_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                text += page.get_text()
            doc.close()
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка при чтении PDF: {str(e)}")

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        try:
            text = docx2txt.process(file_path)
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка при чтении DOCX: {str(e)}")



class OpenAIService:
    @staticmethod
    async def generate_summary(lecture_text: str) -> str:
        try:
            prompt = f"""Создай структурированный конспект лекции. Используй понятный человеческий язык и четкую структуру.

Формат конспекта:

ВВЕДЕНИЕ
Кратко опиши основную тему лекции и ее цель (2-3 предложения).

ОСНОВНЫЕ ИДЕИ

Идея 1: [Название]
Подробное объяснение первой ключевой идеи. Включи определения, примеры и важные детали.

Идея 2: [Название]
Подробное объяснение второй ключевой идеи. Раскрой концепции и их взаимосвязи.

Идея 3: [Название]
Подробное объяснение третьей ключевой идеи.

[И так далее для 4-6 основных идей]

ЗАКЛЮЧЕНИЕ
Кратко подведи итоги и выдели ключевые выводы.

ВАЖНО:
- Пиши простым языком без воды
- Каждый блок должен быть 3-5 предложений
- НЕ используй markdown разметку (##, **, -, *)
- Используй абзацы и переносы строк для структуры
- Не используй нумерованные или маркированные списки

Материал лекции:
{lecture_text[:4000]}

Конспект:"""

            response = await openai.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "Ты профессиональный методист, который создаёт качественные конспекты лекций. Пиши понятным языком, структурируй материал логично. Используй только обычный текст с абзацами, БЕЗ markdown разметки."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка генерации конспекта: {str(e)}")

    @staticmethod
    def generate_test(lecture_text: str) -> List[Dict]:
        try:
            prompt = f"""Создай тест из вопросов по материалу лекции.

Требования к тесту:
1. Вопросы должны покрывать все ключевые темы лекции
2. Используй разные типы вопросов: на знание определений, понимание концепций, применение знаний
3. Варианты ответов должны быть правдоподобными (не очевидные неправильные)
4. Правильный ответ указывай индексом от 0 до 3
5. Каждый вопрос должен быть четким и однозначным

Верни ТОЛЬКО JSON массив в таком формате (без markdown):
[
  {{
    "question": "Полный текст вопроса?",
    "options": [
      "Вариант ответа 1",
      "Вариант ответа 2", 
      "Вариант ответа 3",
      "Вариант ответа 4"
    ],
    "correct_answer": 0
  }}
]

Материал лекции:
{lecture_text[:4000]}

JSON:"""

            response = openai.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "Ты эксперт по созданию образовательных тестов. Создавай качественные вопросы с правдоподобными вариантами ответов. Отвечай только в формате JSON массива, без markdown разметки."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            questions_data = json.loads(content)
            return questions_data

        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка парсинга теста: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка генерации теста: {str(e)}")



class FastAIService:


    @staticmethod
    async def _async_openai_call(prompt: str, system_prompt: str, max_tokens: int = 3000) -> str:
        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=max_tokens
            )
            content = response.choices[0].message.content.strip()


            if content.startswith("```json"):
                content = content[7:].lstrip()
            elif content.startswith("```"):
                content = content[3:].lstrip()

            # Удаляем ``` в конце
            if content.endswith("```"):
                content = content[:-3].rstrip()

            # Удаляем возможные пробелы и переносы
            content = content.strip()

            return content

        except Exception as e:
            print(f"OpenAI API Error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"AI API Error: {str(e)}")

    @staticmethod
    async def process_all_features(lecture_text: str, target_difficulty: str = None) -> Dict:
        truncated_text = lecture_text[:5000]

        if target_difficulty == 'beginner':
            summary_length = "800-1000 слов"
            summary_style = "простым языком с примерами и аналогиями"
            test_complexity = "простые вопросы на определения и базовое понимание"
        elif target_difficulty == 'advanced':
            summary_length = "1200-1500 слов"
            summary_style = "с глубоким анализом, техническими деталями и сложными концепциями"
            test_complexity = "сложные вопросы на применение знаний и анализ"
        else:
            summary_length = "1000-1200 слов"
            summary_style = "со сбалансированным уровнем детализации"
            test_complexity = "вопросы среднего уровня на понимание и применение"

        diff_instruction = f'\nОБЯЗАТЕЛЬНО: Уровень сложности должен быть "{target_difficulty}"!' if target_difficulty else ''

        prompt1 = f"""Создай основные учебные материалы по лекции.{diff_instruction}
    
    Верни JSON:
    {{
      "difficulty": {{
        "level": "{target_difficulty or 'intermediate'}",
        "reasons": ["причина 1", "причина 2", "причина 3"]
      }},
      "summary": "ОЧЕНЬ ПОДРОБНЫЙ конспект {summary_length}, написанный {summary_style}. 
    
    СТРУКТУРА:
    
    ВВЕДЕНИЕ
    [2-3 абзаца]
    
    РАЗДЕЛ 1: [Название]
    [3-5 абзацев]
    
    РАЗДЕЛ 2: [Название]
    [3-5 абзацев]
    
    ЗАКЛЮЧЕНИЕ
    [2-3 абзаца]
    
    Используй \\n\\n между разделами. БЕЗ markdown.",
      "test": [
        {{
          "question": "Полный текст вопроса?",
          "options": ["вариант 1", "вариант 2", "вариант 3", "вариант 4"],
          "correct_answer": 0
        }}
      ]
    }}
    
    Требования:
    - summary: {summary_length}, {summary_style}
    - test: 10 {test_complexity}
    - Только валидный JSON
    
    Лекция:
    {truncated_text}"""

        system1 = f"""Ты опытный методист. 
    Создаёшь учебные материалы уровня {target_difficulty or 'intermediate'}.
    Отвечай ТОЛЬКО валидным JSON без markdown."""

        prompt2 = f"""Создай дополнительные учебные материалы по лекции.
    
    Верни JSON:
    {{
      "anki_cards": [
        {{
          "front": "Термин или вопрос",
          "back": "Подробное объяснение",
          "tags": ["тег1", "тег2"]
        }}
      ],
      "sources": [
        {{
          "topic": "Название темы",
          "url": "https://ru.wikipedia.org/wiki/Тема",
          "description": "Описание источника",
          "source_type": "article"
        }}
      ],
      "mindmap": {{
        "title": "Главная тема",
        "children": [
          {{
            "title": "Подтема",
            "description": "Описание",
            "children": []
          }}
        ]
      }},
      "presentation": [
        {{
          "title": "Заголовок слайда",
          "points": ["Пункт 1", "Пункт 2", "Пункт 3"],
          "notes": "Заметки"
        }}
      ]
    }}
    
    Требования:
    - anki_cards: 10 карточек
    - sources: 5 РЕАЛЬНЫХ источников (wikipedia, учебники)
    - mindmap: 2-3 уровня
    - presentation: 6 слайдов
    
    Лекция:
    {truncated_text[:2000]}"""

        system2 = "Ты методист. Создаёшь учебные материалы. Отвечай ТОЛЬКО валидным JSON без markdown."

        try:
            print("запуск 2 параллельных запросов к OpenAI...")

            results = await asyncio.gather(
                FastAIService._async_openai_call(prompt1, system1, max_tokens=8000),
                FastAIService._async_openai_call(prompt2, system2, max_tokens=5000),
                return_exceptions=True
            )

            if isinstance(results[0], Exception):
                print(f"Ошибка в запросе 1: {results[0]}")
                raise results[0]
            if isinstance(results[1], Exception):
                print(f"Ошибка в запросе 2: {results[1]}")
                raise results[1]

            response1, response2 = results

            result1 = json.loads(response1)
            print("запрос 1 выполнен: summary, test, difficulty")

            result2 = json.loads(response2)
            print("запрос 2 выполнен: anki, sources, mindmap, presentation")

            return {
                'summary': result1.get('summary', 'Конспект не создан'),
                'difficulty_level': result1.get('difficulty', {}).get('level', target_difficulty or 'intermediate'),
                'simplified_summary': None,
                'advanced_summary': None,
                'test': result1.get('test', [])[:10],
                'anki_cards': result2.get('anki_cards', [])[:10],
                'external_sources': result2.get('sources', [])[:5],
                'mindmap': result2.get('mindmap', {'title': 'Лекция', 'children': []}),
                'presentation': result2.get('presentation', [])[:6]
            }

        except json.JSONDecodeError as je:
            print(f"JSON ERROR: {je}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка парсинга ответа. Попробуйте загрузить файл заново."
            )
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

    @staticmethod
    async def generate_difficulty(lecture_text: str) -> Dict:
        prompt = f"""Оцени уровень сложности лекции: beginner, intermediate или advanced.

Критерии:
- BEGINNER: базовые концепции, простой язык, минимум терминов
- INTERMEDIATE: требует базовых знаний, умеренная терминология
- ADVANCED: сложные концепции, специализированная терминология, требует глубоких знаний

Верни JSON:
{{
  "level": "beginner/intermediate/advanced",
  "reasons": ["причина 1", "причина 2", "причина 3"]
}}

Лекция:
{lecture_text[:2000]}"""

        system = "Ты эксперт по оценке учебных материалов. Анализируй сложность объективно."

        response = await FastAIService._async_openai_call(prompt, system)
        return json.loads(response)

    @staticmethod
    async def generate_anki_cards(lecture_text: str) -> List[Dict]:
        prompt = f"""Создай 10-12 карточек Anki для запоминания материала.

Принципы создания карточек:
1. Front: краткий вопрос или термин
2. Back: подробный ответ с объяснением
3. Одна карточка = одна идея
4. Используй активное вспоминание
5. Добавляй релевантные теги

Верни JSON:
{{
  "cards": [
    {{
      "front": "Что такое X?",
      "back": "X — это... [подробное объяснение]",
      "tags": ["тема1", "тема2"]
    }}
  ]
}}

Лекция:
{lecture_text[:3000]}"""

        system = "Ты эксперт по созданию карточек для интервального повторения. Создавай эффективные карточки по принципам Anki."

        response = await FastAIService._async_openai_call(prompt, system)
        result = json.loads(response)
        return result.get('cards', [])

    @staticmethod
    async def generate_external_sources(lecture_text: str) -> List[Dict]:
        prompt = f"""Найди 5-7 внешних источников для углубленного изучения тем из лекции.

Типы источников:
- article: статьи и блоги
- video: образовательные видео
- book: учебники и книги
- wiki: википедия и справочники
- course: онлайн курсы

Верни JSON:
{{
  "sources": [
    {{
      "topic": "Название темы",
      "url": "https://real-url.com/article",
      "description": "Краткое описание (1-2 предложения)",
      "source_type": "article"
    }}
  ]
}}

ВАЖНО: Используй только РЕАЛЬНЫЕ существующие URL!

Лекция:
{lecture_text[:2000]}"""

        system = "Ты помощник для поиска образовательных ресурсов. Рекомендуй только проверенные и релевантные источники с реальными URL."

        response = await FastAIService._async_openai_call(prompt, system)
        result = json.loads(response)
        return result.get('sources', [])

    @staticmethod
    async def generate_mindmap(lecture_text: str) -> Dict:
        """Создает структуру mindmap"""
        prompt = f"""Создай структуру mindmap (интеллект-карту) для лекции.

Требования:
- 3 уровня вложенности
- Главная тема → Основные разделы → Детали
- Каждый узел с кратким описанием
- Логическая структура

Верни JSON:
{{
  "title": "Главная тема лекции",
  "children": [
    {{
      "title": "Основной раздел 1",
      "description": "Краткое описание",
      "children": [
        {{
          "title": "Подраздел 1.1",
          "description": "Детали"
        }}
      ]
    }}
  ]
}}

Лекция:
{lecture_text[:3000]}"""

        system = "Ты эксперт по структурированию информации. Создавай логичные и понятные интеллект-карты."

        response = await FastAIService._async_openai_call(prompt, system)
        return json.loads(response)

    @staticmethod
    async def generate_presentation(lecture_text: str) -> List[Dict]:
        prompt = f"""Создай презентацию из 6-8 слайдов по материалу лекции.

Структура презентации:
1. Титульный слайд
2. Введение/Проблема
3-6. Основные идеи (по одной на слайд)
7. Выводы
8. Вопросы/Обсуждение (опционально)

Каждый слайд:
- Заголовок (краткий и ёмкий)
- 3-5 ключевых пунктов
- Заметки для выступающего

Верни JSON:
{{
  "slides": [
    {{
      "title": "Заголовок слайда",
      "points": [
        "Ключевой пункт 1",
        "Ключевой пункт 2",
        "Ключевой пункт 3"
      ],
      "notes": "Заметки для выступающего: что говорить, какие примеры привести"
    }}
  ]
}}

Лекция:
{lecture_text[:3000]}"""

        system = "Ты эксперт по созданию презентаций. Создавай структурированные и визуально понятные слайды."

        response = await FastAIService._async_openai_call(prompt, system, max_tokens=3000)
        result = json.loads(response)
        return result.get('slides', [])


    @staticmethod
    def parse_results(raw_results: Dict, lecture_text: str) -> Dict:
        """
        этот метод больше не нужен при использовании process_all_features
        оставлен для обратной совместимости
        """
        return raw_results