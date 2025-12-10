from typing import Dict, List

import re

from omnidisp.app.llm.llm_client import LLMClient

PRICE_QUESTION_PATTERNS = [
    "сколько стоит",
    "какая цена",
    "по цене",
    "стоимость",
]


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def process(text: str, is_first_message: bool = False) -> Dict[str, str]:
    """
    Базовая точка обработки входящего сообщения в режиме DISP.
    """
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
    """
    Разбивает исходное сообщение на подзадачи.
    """
    parts = re.split(r";|\.|\sи\s|,", text)
    tasks = [part.strip() for part in parts if part and part.strip()]
    return tasks if tasks else [text]


def check_stop_factors(tasks: List[str]) -> Dict[str, object]:
    """
    Проверяет задачи на наличие стоп-факторов.
    """
    stop_phrases = [
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
        normalized_task = _normalize(task)
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
    keyword_to_category = {
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

    normalized_text = _normalize(text)

    main_category = "unknown"
    for keyword, category in keyword_to_category.items():
        if keyword in normalized_text:
            main_category = category
            break

    task_categories: List[str] = []
    for task in tasks:
        normalized_task = _normalize(task)
        task_category = "unknown"
        for keyword, category in keyword_to_category.items():
            if keyword in normalized_task:
                task_category = category
                if main_category == "unknown":
                    main_category = category
                break
        task_categories.append(task_category)

    if not any(cat != "unknown" for cat in task_categories) and main_category == "unknown":
        task_categories = ["unknown" for _ in tasks]

    return {
        "main_category": main_category,
        "task_categories": task_categories,
    }


def detect_dialog_step(
    text: str,
    is_first_message: bool,
    categories: Dict[str, object],
) -> str:
    """
    Определение шага диалога на основе текста и признака первого сообщения.
    """
    lowered_text = _normalize(text)
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
    """
    Формирует строку INTERNAL TRACE для внутренней отладки режима DISP.
    """
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

    plan_line = "План CLIENT ANSWER: "
    if stop_result.get("full_refuse"):
        plan_line += "вежливо отказать по всем задачам и объяснить причину."
    elif stop_result.get("partial_refuse"):
        plan_line += "отказать по запрещённым задачам и предложить помощь по остальным."
    else:
        plan_line += "ответить как мастер, уточнить детали или время визита."

    parts = [
        "INTERNAL TRACE:",
        "Задача: базовая обработка входящего сообщения.",
        "Контекст:",
        "Тип: фраза.",
        "Ответ мастера в предыдущем сообщении: нет.",
        f"Шаг: {step}.",
        "Документы:",
        f"Категория: {categories.get('main_category', 'unknown')}.",
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

    if tasks:
        parts.insert(1, f"Получен текст: {text}")
        parts.insert(2, f"Определены задачи: {len(tasks)}")
    if forbidden_tasks:
        parts.append(f"Запрещённые задачи: {forbidden_tasks}")
    if allowed_tasks:
        parts.append(f"Разрешённые задачи детально: {allowed_tasks}")

    return "\n".join(parts)


def _build_disp_prompt(
    user_text: str,
    step: str,
    stop_result: Dict[str, object],
    categories: Dict[str, object],
    is_first_message: bool,
) -> str:
    if stop_result.get("full_refuse"):
        plan_type = "full_refuse"
    elif stop_result.get("partial_refuse"):
        plan_type = "partial_refuse"
    else:
        plan_type = "allowed"

    price_question = step == "price_question"

    plan_lines = [
        "PLAN:",
        f"- user_text: {user_text}",
        f"- step: {step}",
        f"- type: {plan_type}",
        f"- is_first_message: {'yes' if is_first_message else 'no'}",
        f"- forbidden_tasks: {stop_result.get('forbidden_tasks', [])}",
        f"- allowed_tasks: {stop_result.get('allowed_tasks', [])}",
        f"- main_category: {categories.get('main_category', 'unknown')}",
        f"- price_question: {'yes' if price_question else 'no'}",
    ]

    instructions = [
        "Ты — выездной мастер по ремонту бытовой техники и мелких работ (не бот, не менеджер). Я сам приезжаю к клиенту, не прошу ничего привозить ко мне.",
        "Приветствие допустимо только деловое: 'Здравствуйте', 'Добрый день', 'Добрый вечер'. Не используй разговорные варианты вроде 'Привет' или 'Хай'.",
        "Тон спокойный и вежливый, без панибратства, шуток и смайликов. Не обращайся 'друг' или 'дорогой клиент', просто говори 'вы/вам'.",
        "Ответ мастера на русском, от первого лица, максимум 1–3 очень коротких предложений. Не пиши длинных абзацев.",
        "Не используй английские слова, латиницу и слова: 'список задач', 'разрешённые задачи', 'запрещённые работы', 'специализация', 'категория', 'стоп-фактор', 'регламент', 'правила', 'база знаний', 'прайс'.",
        "Не упоминай ИИ, нейросети, модели, боты, базы знаний, файлы или внутренние правила.",
        "Не давай инструкций по самостоятельному ремонту; без осмотра лучше не советовать чинить самому.",
        "Решение уже принято по PLAN, не меняй тип ответа и не обещай работать с запрещёнными задачами.",
        "Если PLAN.type == 'full_refuse': вежливо полностью откажись от всех работ, объясни, что такими работами не занимаюсь.",
        "Если PLAN.type == 'partial_refuse': откажи по указанным задачам, но обязательно предложи заняться остальными и попроси уточнить разрешённую часть.",
        "Если PLAN.type == 'allowed': веди себя как выездной мастер — задай уместные уточнения, предложи подъехать к клиенту по шагу диалога (не проси привозить технику).",
        "Если это первое сообщение — начинай коротким приветствием из допустимых вариантов.",
        "Если price_question == 'yes' — не называй цену и не используй цифры, поясни, что точную стоимость скажешь после осмотра на месте.",
    ]

    prompt = "\n".join(
        [
            "Ты — мастер по ремонту бытовой техники и мелких работ.",
            "Структурированный план ответа:",
            *plan_lines,
            "Инструкции:",
            *instructions,
            "Сформулируй один короткий ответ мастера, соблюдая план и инструкции.",
        ]
    )
    return prompt


def build_client_answer(
    step: str,
    stop_result: Dict[str, object],
    categories: Dict[str, object],
    text: str,
    is_first_message: bool,
) -> str:
    """
    Формирует ответ мастера для клиента.
    """
    prompt = _build_disp_prompt(
        user_text=text,
        step=step,
        stop_result=stop_result,
        categories=categories,
        is_first_message=is_first_message,
    )
    client = LLMClient()
    core_answer = client.ask(prompt)

    fallback_message = (
        "Сейчас не получается ответить подробно, попробуйте, пожалуйста, написать ещё раз "
        "или переформулировать запрос."
    )
    if not core_answer:
        return fallback_message

    error_prefixes = (
        "Сейчас не получается обратиться к модели",
        "Сейчас возникла техническая ошибка",
    )
    if any(core_answer.startswith(prefix) for prefix in error_prefixes):
        return fallback_message

    answer = core_answer

    if step == "price_question" and re.search(r"\d", answer or ""):
        answer = (
            "Точную стоимость смогу сказать только после осмотра на месте. Я приеду, "
            "посмотрю проблему и уже по факту скажу, что и по какой цене делать."
        )

    if is_first_message and not answer.lower().startswith("здрав"):
        answer = f"Здравствуйте. {answer}" if answer else fallback_message

    if step == "price_question" and re.search(r"\d", answer or ""):
        answer = (
            "Точную стоимость смогу сказать только после осмотра на месте. Я приеду, "
            "посмотрю проблему и уже по факту скажу, что и по какой цене делать."
        )

    return answer or fallback_message
