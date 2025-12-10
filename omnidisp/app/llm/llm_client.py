from typing import Optional

try:  # noqa: SIM105
    import requests
except ModuleNotFoundError:  # pragma: no cover - fallback when dependency missing
    requests = None  # type: ignore[assignment]

from omnidisp.config.settings import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL, GROQ_TIMEOUT


class LLMClient:
    """
    Клиент для обращения к модели Groq (Llama 3.x) через HTTP API.
    Ключ и модель берутся из config.settings.
    """

    def ask(self, prompt: str) -> str:
        if not GROQ_API_KEY:
            return "Сейчас не получается обратиться к модели, ключ не настроен."

        if requests is None:
            return "Сейчас возникла техническая ошибка при обращении к модели, попробуйте ещё раз."

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=GROQ_TIMEOUT,
            )
            response.raise_for_status()
            data: Optional[dict] = response.json()
        except Exception as exc:  # noqa: BLE001
            print(f"Groq request error: {exc}")
            return "Сейчас возникла техническая ошибка при обращении к модели, попробуйте ещё раз."

        if not isinstance(data, dict) or "choices" not in data:
            print(f"Groq unexpected response format: {data}")
            return "Сейчас возникла техническая ошибка при обращении к модели, попробуйте ещё раз."

        if "error" in data:
            print(f"Groq API returned error: {data.get('error')}")
            return "Сейчас возникла техническая ошибка при обращении к модели, попробуйте ещё раз."

        try:
            raw_text = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            print(f"Groq parsing error: {exc}; data={data}")
            return "Сейчас возникла техническая ошибка при обращении к модели, попробуйте ещё раз."

        return raw_text
