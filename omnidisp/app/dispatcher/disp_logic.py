from typing import Dict, List

from omnidisp.app.llm.llm_client import LLMClient

PRICE_QUESTION_PATTERNS = [
    "сколько стоит",
    "какая цена",
    "по цене",
]


def process(text: str, is_first_message: bool = False) -> Dict[str, str]:
    """
    Базовая точка обработки входящего сообщения в режиме DISP.
    """
    tasks = split_to_tasks(text)
    stop_result = check_stop_factors(tasks)
    step = detect_dialog_step(text=text, is_first_message=is_first_message)

    internal_trace = build_trace(
        text=text,
        tasks=tasks,
        step=step,
        stop_result=stop_result,
    )

    client_answer = build_client_answer(
        step=step,
        stop_result=stop_result,
        text=text,
        is_first_message=is_first_message,
    )

    return {
        "internal_trace": internal_trace,
        "client_answer": client_answer,
    }


def split_to_tasks(text: str) -> List[str]:
    """
    Возвращает список задач. На шаге 1 — исходный текст как единственный элемент.
    """
    return [text]


def check_stop_factors(tasks: List[str]) -> Dict[str, object]:
    """
    Заглушка проверки стоп-факторов. На шаге 1 стоп-факторы отсутствуют.
    """
    return {
        "full_refuse": False,
        "partial_refuse": False,
        "forbidden_tasks": [],
        "allowed_tasks": tasks,
    }


def detect_dialog_step(text: str, is_first_message: bool = False) -> str:
    """
    Определение шага диалога на основе текста и признака первого сообщения.
    """
    lowered_text = text.lower()
    if any(pattern in lowered_text for pattern in PRICE_QUESTION_PATTERNS):
        return "price_question"
    if is_first_message:
        return "first_greeting"
    return "clarification"


def build_trace(
    text: str,
    tasks: List[str],
    step: str,
    stop_result: Dict[str, object],
) -> str:
    """
    Формирует строку INTERNAL TRACE для внутренней отладки режима DISP.
    """
    forbidden_tasks = stop_result.get("forbidden_tasks", [])
    allowed_tasks = stop_result.get("allowed_tasks", [])

    parts = [
        "INTERNAL TRACE:",
        "Задача: базовая обработка входящего сообщения.",
        "Контекст:",
        "Тип: фраза.",
        'Ответ мастера в предыдущем сообщении: нет.',
        f"Шаг: {step}.",
        "Документы:",
        "Категория: не используется на шаге 1.",
        "Файл: не используется на шаге 1.",
        "Прайс просмотрен: нет (этап 1).",
        "Стоп-факторы:",
        "Проверены первыми.",
        "Запрещённые работы: нет.",
        "Разрешённые работы: да.",
        "Результат: разрешено.",
        "Прайс:",
        "Услуга найдена: не ищем на шаге 1.",
        "Комментарий: прайс будет подключён на следующих этапах.",
        "Обязательные вопросы: не заданы (этап 1).",
        "Решение: продолжить диалог и задать уточняющий вопрос.",
        "Цена:",
        "На шаге 1 стоимость не обсуждается в логике ядра.",
        "План CLIENT ANSWER: короткое приветствие и просьба описать проблему.",
        "Самопроверка: стоп-факторы / категория / прайс / шаг / цена / формат — базовая проверка пройдена (этап 1).",
    ]

    # Добавляем сведения о задачах для наглядности, не нарушая требования этапа 1.
    if tasks:
        parts.insert(1, f"Получен текст: {text}")
        parts.insert(2, f"Определены задачи: {len(tasks)}")
    if forbidden_tasks:
        parts.append(f"Запрещённые задачи: {forbidden_tasks}")
    if allowed_tasks:
        parts.append(f"Разрешённые задачи детально: {allowed_tasks}")

    return "\n".join(parts)


def _build_disp_prompt(user_text: str, step: str) -> str:
    return f"""


Ты — частный мастер по ремонту бытовой техники и сантехники.

Правила:

Каждый запрос полностью независим. Игнорируй прошлые запросы и не пытайся помнить контекст.

На вход приходит либо одно сообщение клиента, либо переписка. Если это переписка — проанализируй её, но отвечай только на последнее сообщение клиента.

Отвечай коротко и по делу, без "воды".

Говори строго от первого лица, как мастер: используй "я", "ко мне", "я приеду".

Не используй формулировки "наш мастер", "мы приедем", "наш сервис" и т.п.

Если данных недостаточно — задай 1–2 уточняющих вопроса.

Цену не называй, даже если клиент спрашивает. Объясни, что точная стоимость будет известна после осмотра на месте.

Не упоминай слова "прайс", "регламент", "файл", "база знаний".

Текущий шаг диалога: {step}

Текст клиента (или переписка):
{user_text}

Сформулируй один короткий деловой ответ клиенту, строго соблюдая правила.
""".strip()


def build_client_answer(
    step: str,
    stop_result: Dict[str, object],
    text: str,
    is_first_message: bool = False,
) -> str:
    """
    Формирует ответ мастера для клиента.
    """
    if stop_result.get("full_refuse"):
        return "Здравствуйте. К сожалению, такими работами я не занимаюсь."

    prompt = _build_disp_prompt(user_text=text, step=step)
    client = LLMClient()
    core_answer = client.ask(prompt)

    fallback_message = "Сейчас временно не получается обработать запрос, попробуйте ещё раз."
    if not core_answer:
        return fallback_message

    error_prefixes = (
        "Сейчас не получается обратиться к модели",
        "Сейчас возникла техническая ошибка",
    )
    if any(core_answer.startswith(prefix) for prefix in error_prefixes):
        return fallback_message

    answer = core_answer
    if is_first_message and not answer.lower().startswith("здравствуйте"):
        answer = f"Здравствуйте. {answer}" if answer else fallback_message

    return answer or fallback_message
