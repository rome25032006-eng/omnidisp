from typing import Dict

from .disp_logic import process


def handle_message(text: str, is_first_message: bool = False) -> Dict[str, str]:
    """
    Входная точка режима DISP.
    Принимает текст одного сообщения (или переписку),
    возвращает словарь с INTERNAL TRACE и CLIENT ANSWER.
    """
    return process(text=text, is_first_message=is_first_message)
