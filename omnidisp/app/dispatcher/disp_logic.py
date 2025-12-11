from typing import Dict, List

import re

from omnidisp.app.knowledge.loader import (
    FORBIDDEN_TASKS,
    KEYWORD_TO_CATEGORY,
    find_recommend_question,
    get_min_price,
    load_knowledge,
)
from omnidisp.app.llm.llm_client import LLMClient
from omnidisp.app.llm.prompt_builder import build_disp_prompt
from omnidisp.app.utils.text_normalizer import normalize_text

PRICE_QUESTION_PATTERNS = [
    "сколько стоит",
    "какая цена",
    "по цене",
    "стоимость",
]

load_knowledge()


def process(text: str, is_first_message: bool = False) -> Dict[str, str]:
    """Базовая точка обработки входящего сообщения в режиме DISP."""

    tasks = split_to_tasks(text)
    stop_result = check_stop_factors(tasks)
    categories = detect_categories(text, tasks)
    step = detect_dialog_step(
        text=text, is_first_message=is_first_message, categories=categories
    )

    internal_trace = build_trace(
        text=text,
        tasks=tasks,
        step=step,
        stop_result=stop_result,
        categories=categories,
    )

    client_answer = build_client_answer(
        step=step,
        stop_result=stop_result,
        categories=categories,
        text=text,
        is_first_message=is_first_message,
    )

    return {
        "internal_trace": internal_trace,
        "client_answer": client_answer,
    }


def split_to_tasks(text: str) -> List[str]:
    """Разбивает исходное сообщение на подзадачи."""

    parts = re.split(r";|\.|\sи\s|,", text)
    tasks = [part.strip() for part in parts if part and part.strip()]
    return tasks if tasks else [text]


def check_stop_factors(tasks: List[str]) -> Dict[str, object]:
    """Проверяет задачи на наличие стоп-факторов."""

    stop_phrases = (
        FORBIDDEN_TASKS
        or [
            "люстра",
            "люстру",
            "люстры",
            "потолочный светильник",
            "газовая плита",
            "газовая колонка",
            "газовый котел",
            "газ",
            "газовое",
            "сварка",
            "сварочные работы",
            "стояк",
            "стояки",
            "разводка труб",
            "заменить трубы",
            "проложить трубы",
        ]
    )

    forbidden_tasks: List[str] = []
    allowed_tasks: List[str] = []

    greeting_tasks = {
        "здравствуйте",
        "привет",
        "добрый день",
        "добрый",
        "доброе утро",
        "доброе",
        "добрый вечер",
    }

    for task in tasks:
        normalized_task = normalize_text(task)
        if any(stop_phrase in normalized_task for stop_phrase in stop_phrases):
            forbidden_tasks.append(task)
        elif normalized_task in greeting_tasks:
            continue
        else:
            allowed_tasks.append(task)

    full_refuse = len(forbidden_tasks) > 0 and len(allowed_tasks) == 0
    partial_refuse = len(forbidden_tasks) > 0 and len(allowed_tasks) > 0

    return {
        "full_refuse": full_refuse,
        "partial_refuse": partial_refuse,
        "forbidden_tasks": forbidden_tasks,
        "allowed_tasks": allowed_tasks,
    }


def detect_categories(text: str, tasks: List[str]) -> Dict[str, object]:
    fallback_keywords = {
        "холодильник": "fridge",
        "морозилка": "fridge",
        "стиралка": "washing_machine",
        "стиральная машина": "washing_machine",
        "см ": "washing_machine",
        "посудомойка": "dishwasher",
        "пмм": "dishwasher",
        "посудомоечная машина": "dishwasher",
        "телевизор": "tv",
        "тв": "tv",
        "ноутбук": "laptop",
        "ноут": "laptop",
        "моноблок": "laptop",
        "пк": "pc",
        "компьютер": "pc",
        "системный блок": "pc",
    }

    def _detect(mapping: Dict[str, str]) -> Dict[str, object]:
        normalized_text = normalize_text(text)
        detected_main = "unknown"
        for keyword, category in mapping.items():
            if keyword in normalized_text:
                detected_main = category
                break

        detected_tasks: List[str] = []
        for task in tasks:
            normalized_task = normalize_text(task)
            task_category = "unknown"
            for keyword, category in mapping.items():
                if keyword in normalized_task:
                    task_category = category
                    if detected_main == "unknown":
                        detected_main = category
                    break
            detected_tasks.append(task_category)
        return {"main_category": detected_main, "task_categories": detected_tasks}

    knowledge_detection = _detect(KEYWORD_TO_CATEGORY) if KEYWORD_TO_CATEGORY else None
    has_knowledge_match = knowledge_detection and (
        knowledge_detection["main_category"] != "unknown"
        or any(cat != "unknown" for cat in knowledge_detection["task_categories"])
    )

    if has_knowledge_match:
        result = knowledge_detection  # type: ignore[assignment]
    else:
        result = _detect(fallback_keywords)

    if not any(cat != "unknown" for cat in result["task_categories"]):
        result["task_categories"] = ["unknown" for _ in tasks]

    return result


def detect_dialog_step(
    text: str,
    is_first_message: bool,
    categories: Dict[str, object],
) -> str:
    """Определение шага диалога на основе текста и признака первого сообщения."""

    lowered_text = normalize_text(text)
    if any(pattern in lowered_text for pattern in PRICE_QUESTION_PATTERNS):
        return "price_question"
    greeting_patterns = ["здрав", "привет", "добрый", "доброе"]
    address_patterns = ["адрес", "куда подъехать", "куда ехать"]
    time_patterns = ["когда сможете", "во сколько", "сегодня сможете", "завтра сможете"]

    if is_first_message and any(pattern in lowered_text for pattern in greeting_patterns):
        return "first_greeting"
    if any(pattern in lowered_text for pattern in address_patterns):
        return "address"
    if any(pattern in lowered_text for pattern in time_patterns):
        return "visit_time"
    return "clarification"


def build_trace(
    text: str,
    tasks: List[str],
    step: str,
    stop_result: Dict[str, object],
    categories: Dict[str, object],
) -> str:
    """Формирует строку INTERNAL TRACE для внутренней отладки режима DISP."""

    forbidden_tasks = stop_result.get("forbidden_tasks", [])
    allowed_tasks = stop_result.get("allowed_tasks", [])

    forbidden_present = "да" if forbidden_tasks else "нет"
    allowed_present = "да" if allowed_tasks else "нет"
    if stop_result.get("full_refuse"):
        stop_result_text = "полный отказ"
        decision_text = "отказ"
    elif stop_result.get("partial_refuse"):
        stop_result_text = "частичный отказ"
        decision_text = "частичный отказ"
    else:
        stop_result_text = "разрешено"
        decision_text = "принимаем"

    price_question = step == "price_question"
    knowledge_active = bool(KEYWORD_TO_CATEGORY)

    plan_line = "План CLIENT ANSWER: "
    if stop_result.get("full_refuse"):
        plan_line += "вежливо отказать по всем задачам и объяснить причину."
    elif stop_result.get("partial_refuse"):
        plan_line += "отказать по запрещённым задачам и предложить помощь по остальным."
    else:
        plan_line += "ответить как мастер, уточнить детали или время визита."

    parts = [
        "INTERNAL TRACE:",
        f"Получен текст: {text}",
        f"Определены задачи: {len(tasks)}",
        "Задача: базовая обработка входящего сообщения.",
        "Контекст:",
        "Тип: фраза.",
        "Ответ мастера в предыдущем сообщении: нет.",
        f"Шаг: {step}.",
        "Документы:",
        f"Категория: {categories.get('main_category', 'unknown')}.",
        f"JSON-ключевые слова активны: {'да' if knowledge_active else 'нет'}.",
        "Файл: не используется на этом этапе.",
        "Прайс просмотрен: нет.",
        "Стоп-факторы:",
        "Проверены первыми.",
        f"Запрещённые работы: {forbidden_present}.",
        f"Разрешённые работы: {allowed_present}.",
        f"Результат: {stop_result_text}.",
        "Прайс:",
        "Услуга найдена: не ищем на этом этапе.",
        "Комментарий: прайсы и JSON-БЗ будут подключены позже.",
        "Обязательные вопросы:",
        "Обязательные вопросы: не заданы на этом этапе.",
        "Решение:",
        f"Решение: {decision_text}.",
        "Цена:",
        f"Сообщение содержит вопрос о цене: {'да' if price_question else 'нет'}.",
        "Цена: не называем, прайс ещё не подключён.",
        plan_line,
        "Самопроверка:",
        "Стоп-факторы / категория / прайс / шаг / вопрос о цене / формат ответа — проверены на текущем этапе.",
    ]

    if forbidden_tasks:
        parts.append(f"Запрещённые задачи: {forbidden_tasks}")
    if allowed_tasks:
        parts.append(f"Разрешённые задачи детально: {allowed_tasks}")

    return "\n".join(parts)


def build_client_answer(
    step: str,
    stop_result: Dict[str, object],
    categories: Dict[str, object],
    text: str,
    is_first_message: bool,
) -> str:
    """Формирует ответ мастера для клиента."""

    if stop_result.get("full_refuse"):
        plan_type = "full_refuse"
    elif stop_result.get("partial_refuse"):
        plan_type = "partial_refuse"
    else:
        plan_type = "allowed"

    price_question = step == "price_question"
    main_category = categories.get("main_category", "unknown")
    recommend_question = find_recommend_question(
        main_category, stop_result.get("allowed_tasks", [])
    )

    fallback_message = (
        "Сейчас не получается ответить подробно, попробуйте, пожалуйста, написать ещё раз "
        "или переформулировать запрос."
    )

    min_price = None
    if price_question and not is_first_message:
        min_price = get_min_price(main_category)
        if min_price is not None:
            return (
                f"По опыту, такие работы обычно стоят от {min_price} рублей. "
                "Точную стоимость смогу сказать после диагностики на месте. "
                "Когда вам удобно, чтобы мастер подъехал?"
            )

    prompt = build_disp_prompt(
        user_text=text,
        step=step,
        plan_type=plan_type,
        forbidden_tasks=stop_result.get("forbidden_tasks", []),
        allowed_tasks=stop_result.get("allowed_tasks", []),
        main_category=main_category,
        is_price_question=price_question,
        is_first_message=is_first_message,
        recommend_question=recommend_question,
    )
    client = LLMClient()
    core_answer = client.ask(prompt)

    if not core_answer:
        return fallback_message

    error_prefixes = (
        "Сейчас не получается обратиться к модели",
        "Сейчас возникла техническая ошибка",
    )
    if any(core_answer.startswith(prefix) for prefix in error_prefixes):
        return fallback_message

    answer = core_answer

    if is_first_message and not answer.lower().startswith("здрав"):
        answer = f"Здравствуйте. {answer}" if answer else fallback_message

    if price_question and (min_price is None) and re.search(r"\d", answer or ""):
        answer = (
            "Точную стоимость смогу сказать только после диагностики на месте. "
            "Могу подъехать и после осмотра назвать сумму. Когда вам удобно?"
        )

    return answer or fallback_message
