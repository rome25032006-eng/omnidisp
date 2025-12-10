import os

# Настройки Groq / LLM
GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL: str = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
GROQ_TIMEOUT: int = int(os.environ.get("GROQ_TIMEOUT", "20"))

# Настройки телеграм-бота
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
